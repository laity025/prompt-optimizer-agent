# ==========================================================
# 变体生成服务：基于当前最优提示词 + 失败案例生成多变体
# 策略：failure_inject / rewrite / constraint
# ==========================================================
import json

from app.llm.client import LLMClient, get_llm_client


# 可用的改进策略池：每轮从中取前 count 个，强制每个变体使用不同策略以保障多样性
STRATEGY_POOL = ["rewrite", "constraint", "failure_inject", "cot", "few_shot", "simplify", "structure"]


def _build_variant_prompt(base_prompt: str, task: object, fail_cases: list[dict], count: int,
                          anchors: list[str] | None = None) -> list[dict]:
    """构造变体生成的对话消息。

    :param fail_cases: [{case_id, input, output, reason}] 上一轮低分案例
    :param anchors: 需强制保留的主体词（如 橘猫、猫窝），缺失时忽略
    """
    strategies = STRATEGY_POOL[:max(1, count)]
    labels = {
        "rewrite": "重写/润色现有提示词",
        "constraint": "强化约束与边界条件",
        "failure_inject": "针对失败案例定向改进",
        "cot": "引入思维链(CoT)引导推理",
        "few_shot": "加入示例/少样本引导",
        "simplify": "精简冗长、去除噪音指令",
        "structure": "结构化输出/分节布排",
    }
    strategy_desc = "；".join(f"{s}({labels[s]})" for s in strategies)
    system = (
        "你是提示词工程专家。请基于给定的当前提示词，为任务生成多个改进提示词变体。"
        "所有变体必须围绕给定策略逐一改进，不能改变任务目标。"
        "必须为每个变体各使用一种策略，且策略之间互不重复，以最大化候选多样性。"
        '请只返回JSON数组，形如 [{"strategy_tag":"rewrite","prompt":"<改进后的完整提示词>"}]。'
    )
    user_parts = [
        f"【任务类型】{task.task_type}",
        f"【任务描述】{task.description}",
        f"【优化目标】{task.objective}",
        f"【评分标准】{task.criteria}",
        f"【当前提示词】\n{base_prompt}",
    ]
    if fail_cases:
        user_parts.append(f"【上一轮失败案例（需重点改进）】\n{json.dumps(fail_cases[:5], ensure_ascii=False)}")
    if anchors:
        user_parts.append(
            f"【强制保留要素】所有变体必须保留以下主体词，不得删除或替换为无关内容：{'、'.join(anchors)}。"
        )
    user_parts.append(f"【需按顺序各使用一种的策略列表】{strategy_desc}")
    user_parts.append(f"【需要生成的变体数量】{count}，其中策略 tag 从上述列表中选择且不重复")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


def _normalize(prompt: str) -> str:
    """归一化：折叠空白供相似度比对。"""
    return " ".join(str(prompt).split())


def _similar(a: str, b: str) -> float:
    """基于 SequenceMatcher 的文本相似度（0-1），用于去重判定。"""
    from difflib import SequenceMatcher

    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


def _dedup(variants: list[dict], threshold: float = 0.92) -> list[dict]:
    """去重：丢弃与已保留变体高度相似的后续变体。"""
    kept: list[dict] = []
    for v in variants:
        if any(_similar(v["prompt"], k["prompt"]) >= threshold for k in kept):
            continue
        kept.append(v)
    return kept


async def generate_variants(base_prompt: str, task: object, fail_cases: list[dict],
                            count: int, client: LLMClient | None = None,
                            anchors: list[str] | None = None) -> list[dict]:
    """生成 count 个多样化的变体，返回 [{strategy_tag, prompt}]。

    :param task: 任务对象（取 execution_model / task 描述）
    :param anchors: 需强制保留的主体词列表，用于约束变体不丢掉核心主体
    """
    client = client or get_llm_client()
    try:
        data = await client.chat_json(
            messages=_build_variant_prompt(base_prompt, task, fail_cases, count, anchors),
            model=task.execution_model or task.judge_model or "",
            temperature=0.8,
            max_tokens=3000,
            json_mode=True,
            timeout=180,  # 一次性生成多个完整提示词，需更宽超时避免 ReadTimeout
        )
    except Exception as exc:  # noqa: BLE001
        # 带原始异常类型，避免空消息异常(如 asyncio.TimeoutError)导致 last_error 只留下空串、无法定位
        raise ValueError(f"变体生成失败：{type(exc).__name__}: {exc}")

    # data 可能是 {"variants":[...]} 或直接是数组（防御）
    items = data.get("variants") if isinstance(data, dict) else data
    if isinstance(items, str):
        items = json.loads(items)
    if not isinstance(items, list):
        items = [data]

    variants = []
    # 首个变体固定为基准提示词（作为控制对照，衡量各策略是否带来提升）
    variants.append({"strategy_tag": "baseline", "prompt": base_prompt})
    for item in items:
        if isinstance(item, dict) and item.get("prompt"):
            variants.append({
                "strategy_tag": item.get("strategy_tag", "rewrite"),
                "prompt": item["prompt"],
            })

    # 相似度去重（保留基准，去掉 LLM 生成的重复/雷同项），避免雷同变体浪费 token
    variants = _dedup(variants)
    # 至少保证 1 条；可能因去重而少于 count，属合理行为（宁缺毋滥，不再用基准占位充数）
    return variants[: max(1, count)]