# ==========================================================
# 多模型横向对比评测接口：start / list / detail / export
# 位于 /tasks/{task_id}/benchmarks 命名空间下，复用任务归属校验
# ==========================================================
import asyncio
import json
from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import not_found, state_error
from app.db.base import get_db
from app.models import BenchmarkRun, Task, User
from app.services import benchmark_service, task_service

router = APIRouter(prefix="/tasks", tags=["模型评测"])

# 独立前缀的全局评测列表：挂载为 /benchmarks，供评测页“无需先选任务”查看全部历史
global_router = APIRouter(prefix="/benchmarks", tags=["模型评测"])

# 记录正在运行的评测后台句柄，供「停止/前台等待」使用（与迭代的并发防护同思路）
_running_benchmarks: dict[int, asyncio.Task] = {}


class BenchmarkStartRequest(BaseModel):
    """发起一次对比评测的请求体：选择参与对比的模型与评测提示词来源。"""

    models: list[str] = Field(default_factory=list, description="参与对比的模型ID列表")
    prompt_mode: str = Field(default="best", description="best=当前最优/initial=初始/custom=自定义")
    prompt: str | None = Field(default=None, description="custom 模式下手动提供的评测提示词")
    name: str = Field(default="", description="本次评测命名")


def _pick_snapshot_prompt(task, mode: str, custom: str | None) -> str:
    """按模式解析评测所用的提示词快照。custom 提供则直接采用。"""
    if mode == "custom" and custom:
        return custom
    if mode == "initial":
        return task.initial_prompt or task.best_prompt or ""
    return task.best_prompt or task.initial_prompt or ""


@router.post("/{task_id}/benchmarks/start", summary="发起多模型对比评测")
async def start_benchmark(task_id: int, body: BenchmarkStartRequest,
                          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    if body.prompt_mode not in ("best", "initial", "custom"):
        raise state_error("prompt_mode 仅支持 best/initial/custom")
    # 去重并保持顺序，前端多选一般不会重复，此处做防御性过滤
    models = list(dict.fromkeys(m for m in body.models if m))
    if not models:
        raise state_error("请至少选择 1 个参与对比的模型")

    # 并发防护：同一任务已有运行中的评测则拒绝再次发起，避免多个后台评测并发抢占 LLM 额度
    running = db.query(BenchmarkRun).filter(
        BenchmarkRun.task_id == task_id, BenchmarkRun.status == "running").count()
    if running > 0:
        raise state_error("该任务已有评测正在运行，请等待其完成")

    snapshot = _pick_snapshot_prompt(task, body.prompt_mode, body.prompt)
    if not snapshot:
        raise state_error("评测提示词为空，请先设置初始/最优提示词或选择自定义")

    run = BenchmarkRun(
        user_id=user.id, task_id=task.id, name=body.name or f"对比评测-{task.name}",
        prompt_mode=body.prompt_mode, prompt_snapshot=snapshot,
        models_json=json.dumps(models, ensure_ascii=False),
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    bg = asyncio.create_task(benchmark_service.run_benchmark(run.id))
    _running_benchmarks[run.id] = bg

    def _clean(_t, _rid=run.id):
        if _running_benchmarks.get(_rid) is _t:
            _running_benchmarks.pop(_rid, None)

    bg.add_done_callback(_clean)
    return {"code": 0, "message": "success", "data": {
        "run_id": run.id, "task_id": task.id, "status": "running",
        "models": models, "models_count": len(models),
        "prompt_mode": body.prompt_mode,
    }}


@router.get("/{task_id}/benchmarks", summary="评测历史列表")
def list_benchmarks(task_id: int,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task_service.get_task_owned(db, task_id, user.id)
    runs = db.query(BenchmarkRun).filter(BenchmarkRun.task_id == task_id)\
        .order_by(BenchmarkRun.id.desc()).all()
    items = [{
        "id": r.id, "name": r.name, "prompt_mode": r.prompt_mode,
        "models": json.loads(r.models_json) if r.models_json else [],
        "status": r.status, "best_model": r.best_model, "best_score": r.best_score,
        "created_at": r.created_at, "finished_at": r.finished_at,
    } for r in runs]
    return {"code": 0, "message": "success", "data": {"items": items, "total": len(items)}}


@global_router.get("", summary="我的全部评测历史（跨任务）")
def list_my_benchmarks(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """返回当前用户在所有任务下的评测记录，每条附带所属任务名，供评测首页直接展示。"""
    runs = db.query(BenchmarkRun).filter(BenchmarkRun.user_id == user.id)\
        .order_by(BenchmarkRun.id.desc()).all()
    task_ids = {r.task_id for r in runs}
    names = dict(db.query(Task.id, Task.name).filter(Task.id.in_(task_ids)).all()) if task_ids else {}
    items = [{
        "id": r.id, "task_id": r.task_id, "task_name": names.get(r.task_id, ""),
        "name": r.name, "prompt_mode": r.prompt_mode,
        "models": json.loads(r.models_json) if r.models_json else [],
        "status": r.status, "best_model": r.best_model, "best_score": r.best_score,
        "created_at": r.created_at, "finished_at": r.finished_at,
    } for r in runs]
    return {"code": 0, "message": "success", "data": {"items": items, "total": len(items)}}


@router.get("/{task_id}/benchmarks/{run_id}", summary="评测结果详情")
def benchmark_detail(task_id: int, run_id: int,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task_service.get_task_owned(db, task_id, user.id)
    # 归属校验：run 必须同时属于该任务与当前用户（任务校验为主，user_id 双保险防跨租户）
    run = db.get(BenchmarkRun, run_id)
    if run is None or run.task_id != task_id or run.user_id != user.id:
        raise not_found("评测记录不存在")
    report = benchmark_service.build_report(db, run)
    return {"code": 0, "message": "success", "data": report}


@router.get("/{task_id}/benchmarks/{run_id}/report", summary="导出评测报告")
def export_benchmark(task_id: int, run_id: int,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi.responses import PlainTextResponse

    task_service.get_task_owned(db, task_id, user.id)
    # 归属校验：与 benchmark_detail 一致的 任务+属主 双条件
    run = db.get(BenchmarkRun, run_id)
    if run is None or run.task_id != task_id or run.user_id != user.id:
        raise not_found("评测记录不存在")
    report = benchmark_service.build_report(db, run)

    lines = [
        "# 多模型对比评测报告",
        "",
        f"- 任务ID：{report['run']['task_id']}",
        f"- 评测名称：{report['run']['name']}",
        f"- 状态：{report['run']['status']}",
        f"- 最优模型：{report['run']['best_model'] or '（无）'}",
        f"- 最优得分：{report['run']['best_score'] or '（无）'}",
        "",
        "## 评测提示词",
        "",
        report["run"]["prompt_snapshot"] or "（无）",
        "",
        "## 各模型平均得分",
        "",
    ]
    for m in report["models"]:
        lines.append(
            f"- {m['model']}：{m['avg_score'] or '—'} 分"
            f"（成功 {m['success_cases']} / 失败 {m['failed_cases']}）")
    lines += ["", "## 用例×模型得分矩阵", ""]
    if report["cases"]:
        # 表头
        header = "| 用例 | " + " | ".join(report["models_order"]) + " |"
        sep = "| --- | " + " | ".join(["---"] * len(report["models_order"])) + " |"
        rows = [header, sep]
        for row in report["matrix"]:
            cells = {c["model"]: (str(c["score"]) if c["score"] is not None else "—")
                     for c in row["models"]}
            inputs = next((c["input_text"] for c in report["cases"]
                           if c["case_id"] == row["case_id"]), "")
            # 转义竖线，避免用例文本中的 `|` 破坏 markdown 表格结构
            escaped = inputs.replace("|", "\\|").replace("\n", " ")[:24]
            rows.append(f"| {str(row['case_id'])}({escaped}) | "
                        + " | ".join(cells.get(m, "—") for m in report["models_order"]) + " |")
        lines += rows
    else:
        lines.append("（无用例数据）")

    body = "\n".join(lines)
    filename = f"benchmark_task_{task_id}_run_{run_id}_{datetime.now():%Y%m%d}.md"
    return PlainTextResponse(body, media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})