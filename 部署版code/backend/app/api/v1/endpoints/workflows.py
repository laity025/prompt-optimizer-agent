# ==========================================================
# 多步工作流接口：工作流 CRUD / 步骤编排 / 执行评测 / 报告
# 前缀 /tasks/{task_id}/workflows，复用任务归属校验
# ==========================================================
import asyncio
import time

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import not_found, state_error
from app.db.base import get_db
from app.models import (
    User,
    Workflow,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepOptimization,
)
from app.services import task_service, workflow_executor, workflow_step_optimizer

router = APIRouter(prefix="/tasks", tags=["工作流"])

# 记录正在运行的工作流评测后台句柄（与迭代/评测的并发防护同思路）
_running_workflows: dict[int, asyncio.Task] = {}
# 记录正在运行的步骤优化后台句柄
_running_opts: dict[int, asyncio.Task] = {}
# 按工作流粒度的启动互斥锁：串行化「running 检查 + 创建 run + 后台启动」临界区，
# 消除并发请求下同工作流双开的 TOCTOU 竞态（数据库 running 计数 + 内存 Task 双保险）。
# 锁条目带最后使用时间，空闲超时且未被持有即回收，防止字典随工作流数量无限增长。
_start_locks: dict[int, dict] = {}
_start_locks_guard = asyncio.Lock()
_LOCK_IDLE_TIMEOUT = 30 * 60


async def _get_start_lock(wf_id: int) -> asyncio.Lock:
    """取（或惰性创建）某工作流的启动互斥锁，避免并发创建重复锁。

    惰性回收：仅删除「空闲超时且当前未被持有」的锁——被持有的锁删除会引入
    新请求与新锁的竞态，因此 locked() 为 True 时跳过。
    """
    now = time.monotonic()
    async with _start_locks_guard:
        for key, item in list(_start_locks.items()):
            if now - item["last_used"] > _LOCK_IDLE_TIMEOUT and not item["lock"].locked():
                _start_locks.pop(key, None)
        item = _start_locks.get(wf_id)
        if item is None:
            item = {"lock": asyncio.Lock(), "last_used": now}
            _start_locks[wf_id] = item
        item["last_used"] = now
        return item["lock"]


class StepIn(BaseModel):
    """单步入参：顺序即 seq。"""
    name: str = Field(default="", max_length=255)
    prompt_template: str = Field(min_length=1, max_length=20000, description="支持 {{input}}/{{stepN.out}}")
    model: str = Field(default="", max_length=128, description="留空用任务执行模型")
    output_var: str = Field(default="", max_length=64)


class WorkflowCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    steps: list[StepIn] = Field(default_factory=list, description="初始步骤，按数组顺序编排")


class WorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    steps: list[StepIn] | None = Field(default=None, description="提供则整体替换步骤")


class RunRequest(BaseModel):
    run_baseline: bool = Field(default=True, description="是否同时跑单 prompt 基线对照")


def _get_task(db, task_id: int, user: User):
    """取任务并校验属主。"""
    return task_service.get_task_owned(db, task_id, user.id)


def _get_wf(db, task_id: int, wf_id: int, user: User) -> Workflow:
    """取工作流并校验：属于该任务且属主为当前用户。"""
    wf = db.get(Workflow, wf_id)
    if wf is None or wf.user_id != user.id or wf.task_id != task_id:
        raise not_found("工作流不存在或无权访问")
    return wf


def _apply_steps(db, wf: Workflow, steps: list[StepIn]) -> None:
    """整体替换工作流步骤（按数组顺序生成 seq）。

    校验：工作流至少保留一个含有效指令的步骤，且每个步骤的指令模板非空白
    （与前端 handleSave 的过滤规则一致，防止空白模板步骤进入执行期空跑）。
    """
    cleaned = []
    for st in steps:
        tpl = st.prompt_template.strip()
        if not tpl:
            raise state_error("每个步骤都需要填写指令模板")
        cleaned.append(st)
    if not cleaned:
        raise state_error("工作流至少需要一个步骤")
    for old in list(wf.steps):
        db.delete(old)
    for i, st in enumerate(cleaned, start=1):
        db.add(WorkflowStep(
            workflow_id=wf.id, seq=i, name=st.name,
            prompt_template=st.prompt_template.strip(),
            model=st.model.strip(), output_var=st.output_var.strip(),
        ))
    db.flush()


def _wf_view(wf: Workflow, with_steps: bool = False) -> dict:
    steps = [{
        "id": s.id, "seq": s.seq, "name": s.name, "prompt_template": s.prompt_template,
        "model": s.model, "output_var": s.output_var,
    } for s in wf.steps]
    return {
        "id": wf.id, "task_id": wf.task_id, "name": wf.name, "description": wf.description,
        "created_at": wf.created_at, "steps": steps if with_steps else None,
        "step_count": len(steps),
    }


# ---------- 工作流 CRUD ----------
@router.post("/{task_id}/workflows", summary="创建工作流")
def create_workflow(task_id: int, body: WorkflowCreate,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = _get_task(db, task_id, user)
    wf = Workflow(user_id=user.id, task_id=task.id, name=body.name.strip(),
                  description=body.description.strip())
    db.add(wf)
    db.flush()
    _apply_steps(db, wf, body.steps)
    db.commit()
    db.refresh(wf)
    return {"code": 0, "message": "success", "data": _wf_view(wf, with_steps=True)}


@router.get("/{task_id}/workflows", summary="任务的工作流列表")
def list_workflows(task_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    _get_task(db, task_id, user)
    rows = db.query(Workflow).filter(
        Workflow.task_id == task_id, Workflow.user_id == user.id,
    ).order_by(Workflow.id.desc()).all()
    return {"code": 0, "message": "success", "data": {
        "items": [_wf_view(w) for w in rows], "total": len(rows),
    }}


@router.get("/{task_id}/workflows/{wf_id}", summary="工作流详情（含步骤）")
def get_workflow(task_id: int, wf_id: int, user: User = Depends(get_current_user),
                 db: Session = Depends(get_db)):
    wf = _get_wf(db, task_id, wf_id, user)
    return {"code": 0, "message": "success", "data": _wf_view(wf, with_steps=True)}


@router.put("/{task_id}/workflows/{wf_id}", summary="更新工作流（可整体替换步骤）")
def update_workflow(task_id: int, wf_id: int, body: WorkflowUpdate,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wf = _get_wf(db, task_id, wf_id, user)
    if body.name is not None:
        if not body.name.strip():
            raise state_error("工作流名称不能为空")
        wf.name = body.name.strip()
    if body.description is not None:
        wf.description = body.description.strip()
    if body.steps is not None:
        _apply_steps(db, wf, body.steps)
    db.commit()
    db.refresh(wf)
    return {"code": 0, "message": "success", "data": _wf_view(wf, with_steps=True)}


@router.delete("/{task_id}/workflows/{wf_id}", summary="删除工作流")
def delete_workflow(task_id: int, wf_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    wf = _get_wf(db, task_id, wf_id, user)
    db.delete(wf)  # 级联删除步骤与运行记录
    db.commit()
    return {"code": 0, "message": "success", "data": {"id": wf_id}}


# ---------- 执行与报告 ----------
@router.post("/{task_id}/workflows/{wf_id}/run", summary="执行工作流并评测（异步）")
async def run_workflow(task_id: int, wf_id: int, body: RunRequest,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wf = _get_wf(db, task_id, wf_id, user)
    if not wf.steps:
        raise state_error("工作流没有步骤，无法执行")
    # 获取本工作流的启动互斥锁，串行化「running 计数检查 + 创建 run」，
    # 防止并发双击产生双开的 TOCTOU 竞态。
    lock = await _get_start_lock(wf.id)
    async with lock:
        # 并发防护：同一工作流已有运行中评测则拒绝（避免并发抢占 LLM 额度）
        running = db.query(WorkflowRun).filter(
            WorkflowRun.workflow_id == wf.id, WorkflowRun.status == "running").count()
        if running > 0:
            raise state_error("该工作流已有评测正在运行，请等待其完成")

        run = WorkflowRun(
            workflow_id=wf.id, task_id=wf.task_id,
            name=f"{wf.name}", run_baseline=1 if body.run_baseline else 0,
            status="running",
        )
        db.add(run)
        db.commit()
        db.refresh(run)

    bg = asyncio.create_task(workflow_executor.run_workflow(run.id))
    _running_workflows[run.id] = bg
    bg.add_done_callback(lambda _t, _rid=run.id: _running_workflows.pop(_rid, None))
    return {"code": 0, "message": "success", "data": {"run_id": run.id, "status": "running"}}


@router.get("/{task_id}/workflows/{wf_id}/runs", summary="工作流运行历史")
def list_runs(task_id: int, wf_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    _get_wf(db, task_id, wf_id, user)
    rows = db.query(WorkflowRun).filter(WorkflowRun.workflow_id == wf_id)\
        .order_by(WorkflowRun.id.desc()).all()
    return {"code": 0, "message": "success", "data": {
        "items": [{
            "id": r.id, "name": r.name, "status": r.status,
            "run_baseline": r.run_baseline, "avg_score": r.avg_score,
            "baseline_avg_score": r.baseline_avg_score,
            "created_at": r.created_at, "finished_at": r.finished_at,
        } for r in rows], "total": len(rows),
    }}


@router.get("/{task_id}/workflows/{wf_id}/runs/{run_id}", summary="工作流运行报告")
def run_report(task_id: int, wf_id: int, run_id: int,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wf = _get_wf(db, task_id, wf_id, user)
    run = db.get(WorkflowRun, run_id)
    if run is None or run.workflow_id != wf.id:
        raise not_found("运行记录不存在")
    return {"code": 0, "message": "success", "data": workflow_executor.build_report(db, run)}


# ---------- 步骤自动迭代优化（Phase 5） ----------

class StepOptRequest(BaseModel):
    """启动对工作流某步骤的自动迭代优化。

    终止条件固定为：达到 max_rounds，或整链分连续 2 轮无提升（滞涨提前终止）。
    """
    max_rounds: int = Field(default=3, ge=1, le=10)  # 优化轮数


@router.post("/{task_id}/workflows/{wf_id}/steps/{seq}/optimize", summary="优化工作流某步骤（异步）")
async def opt_step(task_id: int, wf_id: int, seq: int, body: StepOptRequest,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wf = _get_wf(db, task_id, wf_id, user)
    if not wf.steps:
        raise state_error("工作流没有步骤，无法优化")
    step = next((s for s in wf.steps if s.seq == seq), None)
    if step is None:
        raise not_found("目标步骤不存在")
    if not step.prompt_template.strip():
        raise state_error("目标步骤指令模板为空，无法优化")
    # 并发防护：同一工作流已有运行中的优化则拒绝
    running = db.query(WorkflowStepOptimization).filter(
        WorkflowStepOptimization.workflow_id == wf.id,
        WorkflowStepOptimization.status == "running").count()
    if running > 0:
        raise state_error("该工作流已有步骤优化正在运行，请等待其完成")
    lock = await _get_start_lock(wf.id)
    async with lock:
        running = db.query(WorkflowStepOptimization).filter(
            WorkflowStepOptimization.workflow_id == wf.id,
            WorkflowStepOptimization.status == "running").count()
        if running > 0:
            raise state_error("该工作流已有步骤优化正在运行，请等待其完成")
        opt = WorkflowStepOptimization(
            workflow_id=wf.id, task_id=wf.task_id, step_seq=seq,
            base_prompt=step.prompt_template, status="running",
            max_rounds=body.max_rounds,
        )
        db.add(opt)
        db.commit()
        db.refresh(opt)

    bg = asyncio.create_task(workflow_step_optimizer.run_step_optimization(opt.id))
    _running_opts[opt.id] = bg
    bg.add_done_callback(lambda _t, _oid=opt.id: _running_opts.pop(_oid, None))
    return {"code": 0, "message": "success", "data": {"opt_id": opt.id, "status": "running"}}


@router.get("/{task_id}/workflows/{wf_id}/optimizations", summary="工作流步骤优化历史")
def list_opts(task_id: int, wf_id: int, user: User = Depends(get_current_user),
              db: Session = Depends(get_db)):
    _get_wf(db, task_id, wf_id, user)
    rows = db.query(WorkflowStepOptimization).filter(
        WorkflowStepOptimization.workflow_id == wf_id
    ).order_by(WorkflowStepOptimization.id.desc()).all()
    return {"code": 0, "message": "success", "data": {
        "items": [{
            "id": o.id, "step_seq": o.step_seq, "status": o.status,
            "base_score": o.base_score, "best_score": o.best_score,
            "improved": o.improved, "current_round": o.current_round,
            "max_rounds": o.max_rounds, "created_at": o.created_at, "finished_at": o.finished_at,
        } for o in rows], "total": len(rows),
    }}


@router.get("/{task_id}/workflows/{wf_id}/optimizations/{opt_id}", summary="步骤优化报告")
def opt_report(task_id: int, wf_id: int, opt_id: int,
               user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    wf = _get_wf(db, task_id, wf_id, user)
    opt = db.get(WorkflowStepOptimization, opt_id)
    if opt is None or opt.workflow_id != wf.id:
        raise not_found("优化记录不存在")
    return {"code": 0, "message": "success",
            "data": workflow_step_optimizer.build_report(db, opt)}