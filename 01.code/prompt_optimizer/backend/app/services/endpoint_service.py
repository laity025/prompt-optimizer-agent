# ==========================================================
# 在线调用服务：把任务的最优/冻结提示词封装为可对外调用的端点
#   - create_endpoint：绑定提示词快照 + 执行模型，生成唯一 api_key
#   - invoke：用 api_key 鉴权后单次调用，记录日志/耗时/调用次数
#   - rotate_api_key：轮换密钥（不改变 prompt，保留历史日志）
# ==========================================================
import hmac
import secrets
import time

from app.core.exceptions import not_found, state_error
from app.llm.client import get_llm_client
from app.models import Endpoint, EndpointCallLog, PromptVersion
from app.services.executor import execute_single


def _generate_key() -> str:
    """生成随机 API 密钥，33 字节 urlsafe 编码，不可逆安全。"""
    return "sk-" + secrets.token_urlsafe(32)


def unique_api_key(db) -> str:
    """生成并保证不冲突的密钥（极低概率冲突，重试兜底）。"""
    for _ in range(200):
        key = _generate_key()
        if not db.query(Endpoint).filter(Endpoint.api_key == key).first():
            return key
    raise state_error("密钥生成失败，请重试")


def verify_api_key(endpoint: Endpoint | None, key: str | None) -> bool:
    """常量时间比较密钥，避免时序侧信道。"""
    if endpoint is None or not key:
        return False
    return hmac.compare_digest(endpoint.api_key, key)


def create_endpoint(db, user_id: int, task, *, name: str,
                    description: str = "", version_id: int | None = None,
                    model: str | None = None) -> Endpoint:
    """创建端点。

    :param version_id: 可选；指定冻结版本的提示词作为发布快照；缺省用任务最优/初始提示词
    :param model: 可选；指定执行模型；缺省用任务配置的执行模型
    """
    if version_id:
        ver = db.get(PromptVersion, version_id)
        if ver is None or ver.task_id != task.id:
            raise not_found("所选版本不存在")
        prompt = ver.prompt_text
    else:
        prompt = task.best_prompt or task.initial_prompt or ""
    if not prompt:
        raise state_error("该任务无可发布的提示词，请先设置初始/最优提示词或选择冻结版本")

    exec_model = model or task.execution_model or task.judge_model or ""
    if not exec_model:
        raise state_error("任务未配置执行模型，无法发布在线服务")

    return Endpoint(
        user_id=user_id, task_id=task.id, name=name or f"在线服务-{task.name}",
        description=description, prompt=prompt, task_type=task.task_type,
        model=exec_model, api_key=unique_api_key(db), active=1, call_count=0,
    )


async def invoke(endpoint: Endpoint, input_text: str) -> tuple[str, str, int]:
    """单次在线调用。

    :return: (output, error_reason, latency_ms)；成功时 error_reason 为空
    """
    client = get_llm_client()
    start = time.monotonic()
    output, err = await execute_single(
        client=client, prompt=endpoint.prompt, input_text=input_text,
        model=endpoint.model, task_type=endpoint.task_type,
        timeout=60, retries=1,
    )
    latency_ms = int((time.monotonic() - start) * 1000)
    return output, err, latency_ms


def rotate_api_key(db, endpoint: Endpoint) -> str:
    """轮换密钥并立即生效。"""
    endpoint.api_key = unique_api_key(db)
    return endpoint.api_key


def build_call_log(endpoint: Endpoint, input_text: str, output: str, err: str,
                   latency_ms: int) -> EndpointCallLog:
    """根据调用结果构造日志行（由接口层统一提交）。"""
    return EndpointCallLog(
        endpoint_id=endpoint.id,
        input_text=input_text,
        output=output if not err else None,
        error_reason=err or None,
        status="failed" if err else "success",
        latency_ms=latency_ms,
    )