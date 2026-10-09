# ==========================================================
# 评审打分服务：按任务评分标准对变体输出给出 1-10 分 + 理由
# ==========================================================
import json

from app.llm.client import LLMClient, get_llm_client


def _build_judge_messages(task: object, prompt: str, input_text: str,
                          output: str, reference: str | None,
                          anchors: list[str] | None = None) -> list[dict]:
    """构造评审对话消息。要求输出 {score, reason}。

    :param anchors: 需强制保留的主体词，缺失时忽略
    """
    system = (
        "你是严格的任务评审员。请根据评分标准，对模型在给定输入下产生的输出进行打分。"
        "打分范围 1-10 分整数：9-10优秀、7-8良好、5-6及格、3-4较差、1-2很差。"
        "输出必须为JSON对象：{\"score\": 1-10, \"reason\": \"<简短理由，说明扣分点>\"}。"
    )
    if anchors:
        # 主体锚定评审规则：候选提示词丢失强制主体词并改写为无关内容 => 明显低分
        system += (
            f"此外，任务存在以下强制保留主体词：{'、'.join(anchors)}。"
            "若【任务提示词】丢失其中任意一个主体词并将其改写为无关内容，请给 1-3 分的明显低分，"
            "并在 reason 中明确指出丢失了哪个主体词。"
        )
    user_parts = [
        f"【任务类型】{task.task_type}",
        f"【评分标准】\n{task.criteria}",
        f"【任务提示词】\n{prompt}",
        f"【输入】\n{input_text}",
        f"【模型输出】\n{output}",
    ]
    if reference:
        user_parts.append(f"【参考输出】\n{reference}")
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": "\n\n".join(user_parts)},
    ]


async def judge_output(task: object, prompt: str, input_text: str, output: str,
                       reference: str | None, client: LLMClient | None = None,
                       anchors: list[str] | None = None) -> tuple[int, str]:
    """对单个输出评审打分，返回 (score 1-10, reason)。

    :param anchors: 需强制保留的主体词，缺失时忽略
    失败时作保守处理：格式不合规给 1 分，其余情况给中间分并附失败说明。
    """
    client = client or get_llm_client()
    try:
        data = await client.chat_json(
            messages=_build_judge_messages(task, prompt, input_text, output, reference, anchors),
            model=(task.judge_model or task.execution_model or ""),
            temperature=0.2,
            max_tokens=800,
            json_mode=True,
        )
        if isinstance(data, str):
            data = json.loads(data)
        score = int(data.get("score", 5))
        score = max(1, min(10, score))
        reason = str(data.get("reason", ""))[:500]
        return score, reason
    except Exception as exc:  # noqa: BLE001
        # 输出违规判 1 分（严重缺陷），否则给 5 分中间值
        low = (output is None) or (not str(output).strip())
        return (1 if low else 5), f"评审调用失败，暂给保守分：{exc}"