# ==========================================================
# 报告服务：生成优化报告（得分曲线、版本差异、评审总结、建议）
# ==========================================================
from sqlalchemy.orm import Session

from app.models import EvalResult, Iteration, PromptVersion, Task, Variant


def build_report(db: Session, task: Task) -> dict:
    """基于任务已产生的迭代记录生成报告数据。"""
    iterations = db.query(Iteration).filter(Iteration.task_id == task.id).order_by(Iteration.round_no).all()
    versions = db.query(PromptVersion).filter(PromptVersion.task_id == task.id).order_by(PromptVersion.version_no).all()

    score_curve = []
    for it in iterations:
        if it.best_score is not None:
            score_curve.append({"round": it.round_no, "best_score": it.best_score})

    # 版本差异：相邻版本提示词 diff
    version_diffs = []
    if len(versions) >= 2:
        prev = versions[0]
        for cur in versions[1:]:
            version_diffs.append({
                "from_no": prev.version_no,
                "to_no": cur.version_no,
                "added": _diff_added(prev.prompt_text, cur.prompt_text),
                "removed": _diff_removed(prev.prompt_text, cur.prompt_text),
                "changed": "yes" if (cur.prompt_text != prev.prompt_text) else "no",
            })
            prev = cur

    # 评审总结：每轮最优变体的评审理由摘要
    judge_summary = []
    for it in iterations:
        if it.best_variant_id:
            variant = db.get(Variant, it.best_variant_id)
            evals = db.query(EvalResult).filter(EvalResult.variant_id == variant.id).all()
            reason = evals[0].judge_reason if evals else ""
            judge_summary.append({
                "round": it.round_no,
                "best_score": it.best_score,
                "reason": reason or "（该轮无评审理由）",
            })

    # 建议：基于滞涨与失败案例生成粗略建议
    suggestions = []
    if len(score_curve) >= 2 and max(score_curve, key=lambda x: x["best_score"])["best_score"] == score_curve[-1]["best_score"]:
        suggestions.append("最近一轮得分未见提升，建议补充更多失败用例供下次迭代针对改进")
    suggestions.append("建议定期对评估记录进行人工抽检，校验自动评审与人工评分的一致率")
    if len(suggestions) == 0:
        suggestions.append("当前迭代记录较少，可增加轮数以观察收敛趋势")

    return {
        "task_id": task.id,
        "task_name": task.name,
        "best_prompt": task.best_prompt,
        "initial_prompt": task.initial_prompt,
        "score_curve": score_curve,
        "version_diffs": version_diffs,
        "judge_summary": judge_summary,
        "suggestions": suggestions,
    }


def _diff_added(a: str, b: str) -> str:
    """简单的增改文本提取。"""
    if b.find(a) >= 0:
        return ""
    return _diff_lines_b(b, a)


def _diff_removed(a: str, b: str) -> str:
    if b.find(a) >= 0:
        return ""
    return _diff_lines_a(a, b)


def _diff_lines_a(a: str, b: str) -> str:
    """返回 a 中存在但 b 中不存在的行。"""
    sa, sb = set(a.splitlines()), set(b.splitlines())
    return "\n".join([l for l in a.splitlines() if l not in sb])[:300]


def _diff_lines_b(a: str, b: str) -> str:
    """返回 b 中新增的行。"""
    import difflib

    lines = difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="")
    # 只保留新增行 (+ 前缀，单 +)
    added = [l[2:] for l in lines if l.startswith("+") and not l.startswith("+++")]
    return "\n".join(added)[:300]