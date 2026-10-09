# ==========================================================
# LLM 客户端重试回归测试：瞬时超时应自动重试而非直接失败
# ==========================================================
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend 目录，供 app

import pytest

from app.llm.client import LLMClient

# EXEC_MAX_RETRIES 来自真实配置（默认 2）
from app.core.config import get_settings

_SETTINGS = get_settings()


class _FlakyTransport:
    """模拟一个前 fail_n 次抛 ReadTimeout、随后成功的 httpx 客户端。"""

    def __init__(self, fail_n: int):
        self._calls = 0
        self._fail_n = fail_n

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, url, headers=None, json=None):
        import httpx
        self._calls += 1
        if self._calls <= self._fail_n:
            raise httpx.ReadTimeout("模拟网络超时")
        return FakeResponse()


class FakeResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {"choices": [{"message": {"content": '{"ok": true}'}}]}


@pytest.mark.anyio
async def test_chat_retries_then_succeeds():
    """前 2 次 ReadTimeout，重试后应成功返回内容。"""
    transport = _FlakyTransport(fail_n=2)
    client = LLMClient("http://x", "k")

    with patch("app.llm.client.httpx.AsyncClient", side_effect=lambda *a, **k: transport):
        out = await client.chat([{"role": "user", "content": "hi"}], timeout=1)
    assert out == '{"ok": true}'
    assert transport._calls == 3  # 1 次失败 + 2 次重试 = 3


@pytest.mark.anyio
async def test_chat_raises_after_max_retries():
    """失败次数超过重试上限后仍应抛错，而不是死循环。"""
    transport = _FlakyTransport(fail_n=settings_max_retries() + 5)
    client = LLMClient("http://x", "k")

    import httpx
    with patch("app.llm.client.httpx.AsyncClient", side_effect=lambda *a, **k: transport):
        with pytest.raises(httpx.ReadTimeout):
            await client.chat([{"role": "user", "content": "hi"}], timeout=1)
    # 调用次数 = 首次 + 重试次数
    assert transport._calls == settings_max_retries() + 1


def settings_max_retries():
    return _SETTINGS.EXEC_MAX_RETRIES