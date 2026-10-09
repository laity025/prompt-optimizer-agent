# ==========================================================
# 迭代执行接口：start/stop/status/variants/scores/eval-results/review
# ==========================================================
import asyncio
import json
from contextlib import suppress

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import state_error
from app.core.progress import progress_tracker
from app.db.base import get_db
from app.models import EvalResult, Iteration, PromptVersion, TestCase, User, Variant
from app.schemas.task import ReviewRequest
from app.services import task_service
from app.services.optimizer_orchestrator import run_iteration_task

router = APIRouter(prefix="/tasks", tags=["迭代"])

# 记录每个任务正在运行的后台迭代句柄，用于并发防护：
# stop 只会把任务状态置为 stopped（正在执行的 LLM 调用无法即时打断），
# 若不加防护就在 resume 时直接启动新线程，旧线程会与新线程并发写同一任务，
# 造成轮次交错、同轮变体重复、数据库残留。启动下一段前必须确保旧线程真正结束。
_running_tasks: dict[int, asyncio.Task] = {}


def _cancel_running(task_id: int) -> None:
    """取消并等待某个任务的后台迭代句柄真正结束（已结束则跳过）。"""
    t = _running_tasks.get(task_id)
    if t is None or t.done():
        return
    t.cancel()
    with suppress(asyncio.CancelledError):
        # 同步入口无法 await，仅触发取消；真正等待由下一段 start 的 async 等待完成
        pass


@router.post("/{task_id}/iterations/start", summary="开始迭代")
async def start_iteration(task_id: int,
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    # 前提校验：至少一条用例
    case_count = db.query(TestCase.id).filter(TestCase.task_id == task_id).count()
    if case_count == 0:
        raise state_error("请先添加至少一条测试用例")
    if task.status == "running":
        raise state_error("任务已在运行中")

    # 并发防护：上一段迭代线程可能仍在后台运行（stop 只置状态，正在执行的 LLM
    # 调用无法即时打断）。若不等它就启动新线程，两者会并发写同一任务，导致轮次
    # 交错/变体重复。这里先等待旧线程真正结束，超时则强制取消。
    old = _running_tasks.get(task_id)
    if old is not None and not old.done():
        try:
            await asyncio.wait_for(old, timeout=60)
        except asyncio.TimeoutError:
            old.cancel()
            with suppress(asyncio.CancelledError):
                await old
        _running_tasks.pop(task_id, None)

    # 断点续跑：stopped 从 current_round+1 继续；completed 从第1轮重新开始
    resume = task.status == "stopped"
    # “重新迭代”（completed 状态）：清空上一轮全部迭代产物，回到最初的初始提示词，
    # 开启一段完全新的优化。否则会以旧 best 为基准、且旧 best_score 未重置，
    # 基准变体永远追平旧分却不新高，导致提示词永远不变。
    if task.status == "completed":
        variant_pks = select(Variant.id).join(Iteration, Iteration.id == Variant.iteration_id)\
            .where(Iteration.task_id == task_id)
        db.query(EvalResult).filter(EvalResult.variant_id.in_(variant_pks)).delete(synchronize_session=False)
        db.query(Variant).filter(
            Variant.iteration_id.in_(select(Iteration.id).where(Iteration.task_id == task_id))
        ).delete(synchronize_session=False)
        db.query(Iteration).filter(Iteration.task_id == task_id).delete(synchronize_session=False)
        db.query(PromptVersion).filter(PromptVersion.task_id == task_id).delete(synchronize_session=False)
        task.current_round = 0
        task.best_score = None
        task.best_prompt = None
        db.flush()
    start_round = task.current_round + 1 if resume else 1

    progress_tracker.create(task_id, task.max_rounds)
    task.status = "running"
    db.commit()

    # 用可追踪句柄创建后台任务，替代 BackgroundTasks，便于后续等待/取消
    new_task = asyncio.create_task(run_iteration_task(task_id, start_round, resume))
    _running_tasks[task_id] = new_task

    def _clean(_t, _tid=task_id):
        if _running_tasks.get(_tid) is _t:
            _running_tasks.pop(_tid, None)

    new_task.add_done_callback(_clean)
    return {"code": 0, "message": "success", "data": {
        "task_id": task.id, "task_status": "running", "total_rounds": task.max_rounds,
        "start_round": start_round, "resume": resume,
    }}


@router.post("/{task_id}/iterations/stop", summary="停止迭代")
def stop_iteration(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    # 立即取消后台迭代线程，使其在下一个 await 点抛 CancelledError 退出；
    # 配合并发防护，resume 前会等待该线程真正结束，避免与旧线程并发写库。
    _cancel_running(task_id)
    # 内存中置停止标记
    progress_tracker.update(task_id, status="stopping")
    if task.status == "running":
        task.status = "stopped"
        db.commit()
    return {"code": 0, "message": "success", "data": {"task_id": task.id, "task_status": task.status}}


@router.get("/{task_id}/iterations/status", summary="迭代进度")
def iteration_status(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    prog = progress_tracker.get(task_id)
    base = {
        "task_id": task.id,
        "task_status": task.status,
        "current_round": task.current_round if task.current_round else 0,
        "max_rounds": task.max_rounds,
        "current_best_score": task.best_score,
        "variants_done": 0, "variants_total": 0,
        "cases_done": 0, "cases_total": 0, "cases_success": 0, "cases_failed": 0,
        "message": None,
    }
    if prog:
        # 内存进度只补充分类执行进度（运行中）。
        # task_status / current_round / current_best_score 一律以数据库为准：
        # 避免任务已完成(completed/stopped)时被内存残留的 running / 旧分值覆盖，
        # 导致前端无法感知结束、得分显示停滞。
        d = prog.to_dict()
        if task.status == "running":
            base["current_best_score"] = d["current_best_score"]
        for k in ("variants_done", "variants_total", "cases_done", "cases_total",
                  "cases_success", "cases_failed", "message"):
            base[k] = d[k]
    # 若内存进度为空但任务已 completed，则回填 current_best_score
    if prog is None:
        base["current_best_score"] = task.best_score
    return {"code": 0, "message": "success", "data": base}


@router.get("/{task_id}/iterations/{round_no}/variants", summary="某轮变体列表")
def round_variants(task_id: int, round_no: int,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    from app.models import Iteration
    iteration = db.query(Iteration).filter(
        Iteration.task_id == task_id, Iteration.round_no == round_no).first()
    if iteration is None:
        return {"code": 0, "message": "success", "data": []}
    items = [
        {"id": v.id, "variant_no": v.variant_no, "prompt_text": v.prompt_text,
         "strategy_tag": v.strategy_tag, "score": v.score, "status": v.status}
        for v in db.query(Variant).filter(Variant.iteration_id == iteration.id).order_by(Variant.variant_no).all()
    ]
    return {"code": 0, "message": "success", "data": items}


@router.get("/{task_id}/iterations/{round_no}/scores", summary="得分曲线")
def round_scores(task_id: int, round_no: int,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    from app.models import Iteration
    its = db.query(Iteration).filter(Iteration.task_id == task_id).order_by(Iteration.round_no).all()
    rounds = [{"round": it.round_no, "best_score": it.best_score}
              for it in its if it.best_score is not None]
    return {"code": 0, "message": "success", "data": {"rounds": rounds, "target_score": task.target_score}}


@router.get("/{task_id}/iterations/{round_no}/eval-results", summary="评估结果明细")
def round_eval_results(task_id: int, round_no: int,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    from app.models import Iteration
    iteration = db.query(Iteration).filter(
        Iteration.task_id == task_id, Iteration.round_no == round_no).first()
    if iteration is None:
        return {"code": 0, "message": "success", "data": {"items": [], "total": 0}}
    items = []
    for v in db.query(Variant).filter(Variant.iteration_id == iteration.id).all():
        for e in db.query(EvalResult).filter(EvalResult.variant_id == v.id).all():
            items.append({
                "id": e.id, "variant_no": v.variant_no, "test_case_id": e.test_case_id,
                "model_output": e.model_output, "outcome": e.outcome, "error_reason": e.error_reason,
                "bleu": e.bleu, "rouge": e.rouge, "keyword_hit": e.keyword_hit, "format_ok": e.format_ok,
                "judge_score": e.judge_score, "judge_reason": e.judge_reason, "total_score": e.total_score,
                "manual_score": e.manual_score, "manual_checked": e.manual_checked, "manual_note": e.manual_note,
            })
    return {"code": 0, "message": "success", "data": {"items": items, "total": len(items)}}


@router.post("/{task_id}/eval-results/{eval_id}/review", summary="人工抽检评分")
def review_eval(task_id: int, eval_id: int, body: ReviewRequest,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    # 归属校验：评估记录必须经 变体→迭代 关联到当前任务才能被查到，
    # 阻断用他人 eval_id 对非本任务评估记录写入人工评分（防跨租户越权写）
    ev = (
        db.query(EvalResult)
        .join(Variant, Variant.id == EvalResult.variant_id)
        .join(Iteration, Iteration.id == Variant.iteration_id)
        .filter(EvalResult.id == eval_id, Iteration.task_id == task_id)
        .first()
    )
    if ev is None:
        from app.core.exceptions import not_found
        raise not_found("评估记录不存在")
    ev.manual_score = body.manual_score
    ev.manual_note = body.manual_note
    ev.manual_checked = 1
    db.commit()
    return {"code": 0, "message": "success", "data": {"id": ev.id, "manual_score": body.manual_score}}