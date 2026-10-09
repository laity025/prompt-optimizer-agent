# ==========================================================
# 工作流瓶颈步骤自动迭代优化服务
#   - 对工作流中某个单一步骤，复用优化器的变体生成思路，多轮贪心迭代：
#       每轮以该步骤当前 prompt 为基准生成多个变体，把目标步骤替换为该变体重跑整条链，
#       按任务标准评测末步输出得到各变体整链平均分；取最优变体为下一轮基准，最终回写。
#   - 评测口径与 workflow_executor.chain_execute_and_score 完全一致（自动指标+评审+权重）。
# ==========================================================
import logging
from datetime import datetime

from sqlalchemy import update

from app.db.base import SessionLocal
from app.models import (
    Task,
    TestCase,
    Workflow,
    WorkflowStep,
    WorkflowStepOptVariant,
    WorkflowStepOptimization,
)
from app.services.optimizer_orchestrator import extract_anchors
from app.services.variant_generator import generate_variants
from app.services.workflow_executor import chain_execute_and_score

logger = logging.getLogger("workflow_opt")


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def build_report(db, opt: WorkflowStepOptimization) -> dict:
    """由已落库的优化运行与变体记录生成优化报告。"""
    variants = db.query(WorkflowStepOptVariant).filter(
        WorkflowStepOptVariant.optimization_id == opt.id
    ).order_by(WorkflowStepOptVariant.round_no, WorkflowStepOptVariant.variant_no).all()
    wf = db.get(Workflow, opt.workflow_id)
    step = None
    if wf:
        step = next((s for s in wf.steps if s.seq == opt.step_seq), None)
    return {
        "opt": {
            "id": opt.id, "workflow_id": opt.workflow_id, "task_id": opt.task_id,
            "step_seq": opt.step_seq, "status": opt.status,
            "base_prompt": opt.base_prompt, "best_prompt": opt.best_prompt,
            "base_score": opt.base_score, "best_score": opt.best_score,
            "improved": opt.improved, "current_round": opt.current_round,
            "max_rounds": opt.max_rounds, "created_at": opt.created_at,
            "finished_at": opt.finished_at,
        },
        "workflow": {"id": wf.id, "name": wf.name} if wf else None,
        "step": {"seq": opt.step_seq, "name": step.name if step else ""} if step else None,
        "variants": [{
            "id": v.id, "round_no": v.round_no, "variant_no": v.variant_no,
            "strategy_tag": v.strategy_tag, "prompt_text": v.prompt_text,
            "avg_score": v.avg_score, "status": v.status,
            "error_reason": v.error_reason, "is_best": v.is_best,
        } for v in variants],
    }


async def _score_variant(task, wf, step_defs, c: TestCase, anchors, rag_retrieve,
                         variant_prompt: str) -> dict:
    """把目标步骤替换为变体 prompt 后重跑整条链，返回该用例的综合分与输出明细。

    :return: {total_score, final_output, judge_reason}
    ⚠ step_defs 的元素是共享 dict，必须先逐个浅拷贝再替换目标步骤 prompt，
      否则会污染调用方持有的步骤定义，影响基准/其它变体的评测。
    """
    overridden = [dict(sd) for sd in step_defs]
    for sd in overridden:
        if sd["seq"] == wf.get("target_seq"):
            sd["prompt_template"] = variant_prompt
    res = await chain_execute_and_score(
        task, wf.get("name", ""), overridden, c, anchors,
        rag_retrieve=rag_retrieve, run_baseline=False,
    )
    return {
        "total_score": float(res.get("total_score") or 0.0),
        "final_output": res.get("final_output") or "",
        "judge_reason": res.get("judge_reason") or "",
    }


async def run_step_optimization(opt_id: int) -> None:
    """后台执行一次步骤优化：多轮贪心迭代 + 变体评测 + 择优回写目标步骤。

    终止条件：达到 max_rounds，或整链得分连续 2 轮无提升（滞涨）。
    """
    db = SessionLocal()
    try:
        opt = db.get(WorkflowStepOptimization, opt_id)
        if opt is None:
            return
        wf = db.get(Workflow, opt.workflow_id)
        task = db.get(Task, opt.task_id)
        if wf is None or task is None:
            opt.status = "failed"; opt.finished_at = _now(); db.commit(); return

        steps = sorted(wf.steps, key=lambda s: s.seq)
        target = next((s for s in steps if s.seq == opt.step_seq), None)
        if target is None:
            opt.status = "failed"; opt.finished_at = _now()
            db.execute(update(WorkflowStepOptimization).where(
                WorkflowStepOptimization.id == opt.id
            ).values(status="failed", finished_at=_now()))
            db.commit(); return

        opt.status = "running"
        opt.finished_at = None
        db.commit()

        cases = db.query(TestCase).filter(TestCase.task_id == task.id).order_by(TestCase.id).all()
        if not cases:
            opt.status = "failed"; opt.finished_at = _now(); db.commit(); return

        anchors = extract_anchors(task, cases)
        rag_retrieve = None
        if getattr(task, "enable_rag", 0) and getattr(task, "kb_id", None):
            from app.services import rag_service

            rag_retrieve = rag_service.build_retriever(db, task.kb_id)

        step_defs = [{"seq": s.seq, "name": s.name, "prompt_template": s.prompt_template,
                      "model": s.model, "output_var": s.output_var} for s in steps]
        wf_ctx = {"name": wf.name, "target_seq": opt.step_seq}

        best_prompt = opt.base_prompt
        best_score, stale = 0.0, 0

        # 优化前基准整链分（用于判定 improved）
        base_scores = []
        for c in cases:
            r = await _score_variant(task, wf_ctx, step_defs, c, anchors, rag_retrieve, opt.base_prompt)
            base_scores.append(r["total_score"])
        base_score = round(sum(base_scores) / len(base_scores), 2) if base_scores else 0.0
        opt.base_score = base_score
        best_score = base_score
        db.commit()

        # 上一轮失败案例反馈（复用主优化器口径）：供变体生成器定向改进
        prev_fail_cases: list[dict] = []

        for round_no in range(1, opt.max_rounds + 1):
            opt.current_round = round_no
            db.commit()
            try:
                # 与主优化器一致：anchors 约束变体不丢强制主体词；fail_cases 提供低分信号
                variants = await generate_variants(
                    best_prompt, task, prev_fail_cases, count=3, anchors=anchors)
            except Exception as exc:  # noqa: BLE001
                logger.warning("步骤优化 %s 第 %s 轮变体生成失败：%s", opt_id, round_no, exc)
                break

            round_best, round_best_score = None, -1.0
            round_best_cases: list[dict] = []
            var_no = 0
            for v in variants:
                var_no += 1
                rec = WorkflowStepOptVariant(
                    optimization_id=opt.id, round_no=round_no, variant_no=var_no,
                    strategy_tag=v.get("strategy_tag", "rewrite"),
                    prompt_text=v.get("prompt", ""), status="running",
                )
                db.add(rec); db.commit(); db.refresh(rec)
                try:
                    case_results, err = [], ""
                    for c in cases:
                        r = await _score_variant(
                            task, wf_ctx, step_defs, c, anchors, rag_retrieve, rec.prompt_text)
                        case_results.append({
                            "case_id": c.id, "input": c.input_text,
                            "output": r["final_output"], "reason": r["judge_reason"],
                            "score": r["total_score"],
                        })
                    score = round(sum(x["score"] for x in case_results) / len(case_results), 2) \
                        if case_results else 0.0
                except Exception as exc:  # noqa: BLE001
                    err = f"{type(exc).__name__}: {exc}"
                rec.avg_score = score if not err else None
                rec.status = "failed" if err else "completed"
                rec.error_reason = err or None
                db.commit()
                if not err and score > round_best_score:
                    round_best_score, round_best = score, rec
                    round_best_cases = case_results

            # 失败案例反馈（下一轮用）：取本轮最优变体整链分 <60 的用例，至多 5 条
            if round_best is not None:
                prev_fail_cases = [
                    {"case_id": x["case_id"], "input": x["input"],
                     "output": x["output"], "reason": x["reason"]}
                    for x in round_best_cases if x["score"] < 60
                ][:5]
            else:
                prev_fail_cases = []

            # 该轮最优变体作为下一轮基准；按 (workflow_id, seq) 回写目标步骤，
            # 避免优化期间步骤被整体替换后 target.id 指向已删除行导致回写静默失效
            if round_best is not None and round_best_score > best_score:
                best_prompt, best_score = round_best.prompt_text, round_best_score
                opt.best_prompt = best_prompt
                opt.best_score = best_score
                stale = 0
                db.execute(update(WorkflowStep).where(
                    WorkflowStep.workflow_id == wf.id,
                    WorkflowStep.seq == opt.step_seq,
                ).values(prompt_template=best_prompt))
                db.execute(update(WorkflowStepOptVariant).where(
                    WorkflowStepOptVariant.id == round_best.id
                ).values(is_best=1))
            else:
                stale += 1
                if round_best is not None:
                    db.execute(update(WorkflowStepOptVariant).where(
                        WorkflowStepOptVariant.id == round_best.id).values(is_best=1))
                if stale >= 2:
                    logger.info("步骤优化 %s 第 %s 轮滞涨，提前终止", opt_id, round_no)
                    break

        # 完成：始终回填最优 prompt/分数（未提升时即基准值），保证报告完整
        opt.best_prompt = best_prompt
        opt.best_score = best_score
        opt.improved = 1 if best_score and opt.base_score is not None \
            and best_score > opt.base_score else 0
        opt.finished_at = _now()
        opt.status = "completed"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        logger.exception("步骤优化 %s 失败", opt_id)
        db.rollback()
        try:
            db.execute(update(WorkflowStepOptimization).where(
                WorkflowStepOptimization.id == opt_id
            ).values(status="failed", finished_at=_now()))
            db.commit()
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        db.close()