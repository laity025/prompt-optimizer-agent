# ==========================================================
# 批量执行服务：用提示词变体执行全部测试用例，支持并发与重试
# ==========================================================
import asyncio
import json

from app.core.exceptions import llm_error
from app.core.config import get_settings
from app.llm.client import LLMClient, get_llm_client

_rag_settings = get_settings()


def _build_messages(prompt: str, input_text: str, task_type: str,
                    context: str | None = None) -> list[dict]:
    """根据任务类型构造执行对话消息。

    :param context: RAG 检索到的知识库上下文，非空时注入并提示优先依据其作答
    """
    system = "你是本任务的执行器，严格遵循给定提示词完成对输入的处理并给出最终结果。"
    if task_type == "extraction":
        system += " 若需输出JSON，请直接返回合法的JSON对象，不要额外解释。"
    elif task_type == "code":
        system += " 请只返回Python代码，不要包含多余解释。"
    elif task_type == "summary":
        system += " 请只返回摘要正文。"
    user = f"【任务提示词】\n{prompt}\n\n【输入】\n{input_text}"
    if context:
        user += (
            "\n\n【检索到的知识库上下文】\n" + context +
            "\n（请优先依据上述知识库上下文作答，仅当其中能找到支撑时引用其内容；"
            "知识不足时如实说明，不得编造知识库之外的信息。）"
        )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def execute_single(client: LLMClient, prompt: str, input_text: str, model: str,
                         task_type: str, timeout: int, retries: int,
                         context: str | None = None) -> tuple[str, str]:
    """执行单条用例，返回 (output, error_reason)。

    :param context: RAG 检索上下文，非空时注入执行消息
    处理成功返回 (output, "")；失败返回 ("", error_reason)。
    """
    last_err = ""
    for attempt in range(retries + 1):
        try:
            out = await client.chat(
                messages=_build_messages(prompt, input_text, task_type, context),
                model=model,
                temperature=0.7,
                max_tokens=2000,
                timeout=timeout,
            )
            return out, ""
        except Exception as exc:  # noqa: BLE001
            last_err = f"{type(exc).__name__}: {exc}"
            if attempt < retries:
                await asyncio.sleep(0.5)
    return "", last_err


async def execute_cases(prompt: str, inputs: list[dict], task: object,
                        concurrency: int, client: LLMClient | None = None,
                        model: str | None = None) -> list[dict]:
    """并发执行多个用例。

    :param prompt: 变体提示词
    :param inputs: [{case_id, input_text, ...}]
    :param task: 任务对象（取 execution_model / task_type / concurrency）
    :param model: 显式指定执行模型；传入时覆盖 task.execution_model，
                  用于【多模型横向对比评测】对同一任务切换不同模型执行
    :return: [{case_id, output, error_reason}]
    """
    client = client or get_llm_client()
    # 显式 model 优先；缺省回退到任务配置的执行模型
    model = model or task.execution_model or task.judge_model or ""
    sem = asyncio.Semaphore(concurrency or 2)

    # RAG 检索注入：任务开启 RAG 并绑定知识库时，为每个用例按输入检索并注入上下文。
    # 检索器在进入并发前一次性载入知识库全量块到内存，避免逐用例查询数据库。
    rag_retrieve = None
    rag_context_of = getattr(task, "enable_rag", 0) and getattr(task, "kb_id", None)
    if rag_context_of:
        from app.db.base import SessionLocal
        from app.services import rag_service

        _rs = SessionLocal()
        try:
            rag_retrieve = rag_service.build_retriever(_rs, task.kb_id)
        finally:
            _rs.close()

    async def _one(item: dict) -> dict:
        async with sem:
            context = None
            if rag_retrieve is not None:
                from app.services import rag_service

                hits = await rag_retrieve(
                    item["input_text"], top_k=_rag_settings.RAG_EVAL_TOP_K)
                if hits:
                    context = rag_service.compose_context(hits)
            out, err = await execute_single(
                client=client,
                prompt=prompt,
                input_text=item["input_text"],
                model=model,
                task_type=task.task_type,
                timeout=60,
                retries=2,
                context=context,
            )
            return {"case_id": item["case_id"], "output": out, "error_reason": err}

    results = await asyncio.gather(*(_one(item) for item in inputs))
    return list(results)