# ==========================================================
# LLM 客户端封装：统一 OpenAI 兼容调用
# 支持文本对话/结构化输出、超时、重试、敏感字段脱敏
# ==========================================================
import asyncio
import json
import re
from typing import Any, Optional

import httpx

from app.core.config import get_settings

settings = get_settings()

# 常见敏感字段模式，调用外部时做占位替换
_SENSITIVE_PATTERN = re.compile(
    r"(?i)(api[_-]?key|secret|token|password|authorization)\s*[:=]\s*[\"']?[^\s\"',;]+"
)


class LLMClient:
    """大模型客户端，使用 OpenAI Chat Completions 兼容协议。"""

    def __init__(self, base_url: str, api_key: str):
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key or ""

    @classmethod
    def from_settings(cls) -> "LLMClient":
        return cls(settings.LLM_BASE_URL, settings.LLM_API_KEY)

    def _url(self) -> str:
        return f"{self._base_url}/chat/completions"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _sanitize(text: str) -> str:
        """将文本中的敏感字段脱敏后再返回。"""
        return _SENSITIVE_PATTERN.sub(r"\1: ***", text)

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        timeout: int = 60,
    ) -> str:
        """调用对话接口，返回模型文本输出。

        :param messages: [{role, content}, ...]
        :param model: 模型 id，缺省用配置默认模型
        :param json_mode: 请求响应 JSON 对象
        :return: 模型输出文本
        """
        payload: dict[str, Any] = {
            "model": model or settings.LLM_DEFAULT_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        # 调用前脱敏，防止敏感字段泄露到外部
        safe_payload = json.loads(json.dumps(payload))
        for msg in safe_payload.get("messages", []):
            msg["content"] = self._sanitize(msg.get("content", ""))

        # 可自动重试的异常集合：超时/断连等瞬时故障，加 HTTPStatusError（5xx/限流429）
        retry_excs: tuple[type[Exception], ...] = (
            httpx.TimeoutException,
            httpx.NetworkError,
            httpx.ReadError,
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.HTTPStatusError,
        )
        async with httpx.AsyncClient(timeout=timeout) as client:
            # 对瞬时超时/连接/服务端错误做有限重试，避免单次抖动直接击穿整轮迭代
            last_exc: Exception | None = None
            for attempt in range(settings.EXEC_MAX_RETRIES + 1):
                try:
                    resp = await client.post(self._url(), headers=self._headers(), json=safe_payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                except retry_excs as exc:
                    last_exc = exc
                    # 4xx 客户端错误（除限流 429 外）重试无意义，立即抛出；仅 5xx/429 走重试
                    if isinstance(exc, httpx.HTTPStatusError):
                        code = exc.response.status_code
                        if code != 429 and code < 500:
                            raise
                    if attempt < settings.EXEC_MAX_RETRIES:
                        # 限流(429)采用更重的退避等待，其余按线性退避
                        is_ratelimit = isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429
                        delay = (2.0 + attempt) if is_ratelimit else (1.0 + attempt)
                        await asyncio.sleep(delay)
            # 空消息异常（如 asyncio.TimeoutError）直接 re-raise 会让上游只能看到空串，
            # 这里改抛带类型说明的 RuntimeError，保证错误可定位
            if last_exc is not None and not str(last_exc):
                raise RuntimeError(f"{type(last_exc).__name__}: LLM 调用失败（无响应内容）")
            raise last_exc if last_exc else RuntimeError("LLM 调用失败")

    async def chat_json(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        timeout: int = 60,
        json_mode: bool = True,
    ) -> dict[str, Any]:
        """调用接口并要求返回 JSON 对象，尽力解析为 dict。"""
        text = await self.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            json_mode=json_mode,
            timeout=timeout,
        )
        # 去除可能的 ```json 包裹再解析
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # 保守回退：截取首个 { 到末尾
            idx = cleaned.find("{")
            if idx == -1:
                # 附带响应片段，便于事后定位是超时/限流残留，还是模型返回了非 JSON
                raise ValueError(f"模型未返回有效 JSON，响应片段: {text[:200]!r}")
            try:
                parsed = json.loads(cleaned[idx:].rstrip().rstrip("`").strip())
            except json.JSONDecodeError as exc:
                # 截取后仍无法解析：附带原始响应片段，说明问题出在模型返回内容而非网络
                raise ValueError(f"JSON 解析失败，响应片段: {text[:200]!r}") from exc
        return parsed


_default_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """返回全局默认 LLM 客户端（未配置 API key 时可替换为 mock）。"""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient.from_settings()
    return _default_client


def set_mock_client(client: LLMClient) -> None:
    """测试用：注入模拟客户端。"""
    global _default_client
    _default_client = client