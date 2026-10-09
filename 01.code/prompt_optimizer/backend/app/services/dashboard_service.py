# ==========================================================
# 资产管理门户/汇总仪表盘服务
# 聚合当前用户跨模块的资产数据：任务/版本/端点/评测/工作流/知识库
# 所有计数与求和一律用 SQL 聚合函数（func.count/func.sum），
# 严禁在 ORM 对象上内存累加，避免并发/大数据下计数丢失
# ==========================================================
from collections import defaultdict
from datetime import date, timedelta

from sqlalchemy import case, func, or_
from sqlalchemy.orm import Session

from app.models import (
    BenchmarkRun,
    Endpoint,
    EndpointCallLog,
    Iteration,
    KnowledgeBase,
    PromptVersion,
    Task,
    User,
    Workflow,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepOptimization,
)
from app.models.test_case import TestCase


def _task_ids_of(db: Session, user_id: int) -> list[int]:
    """当前用户全部任务 id（仪表盘各聚合都以此为归属边界）。"""
    return [tid for (tid,) in db.query(Task.id).filter(Task.user_id == user_id).all()]


def get_overview(db: Session, user: User) -> dict:
    """资产总览：任务/用例/版本/端点/调用/评测/工作流/知识库数量 + 最优分均值。"""
    uid = user.id
    tids = _task_ids_of(db, uid)

    # 端点调用聚合（跨表 join，SQL 聚合避免并发丢计数）
    call_agg = (
        db.query(
            func.count(EndpointCallLog.id),
            func.sum(EndpointCallLog.latency_ms),
        )
        .join(Endpoint, EndpointCallLog.endpoint_id == Endpoint.id)
        .filter(Endpoint.user_id == uid)
        .one()
    )
    call_total = call_agg[0] or 0
    call_latency = call_agg[1] or 0

    scored = (
        db.query(Task.best_score)
        .filter(Task.user_id == uid, Task.best_score.isnot(None))
        .all()
    )
    scored_vals = [s[0] for s in scored]

    return {
        "tasks": db.query(func.count(Task.id)).filter(Task.user_id == uid).scalar(),
        "cases": _count_cases(db, tids),
        "versions": _count_versions(db, tids),
        "endpoints": db.query(func.count(Endpoint.id)).filter(Endpoint.user_id == uid).scalar(),
        "calls": call_total,
        "avg_latency_ms": round(call_latency / call_total, 1) if call_total else 0,
        "benchmarks": db.query(func.count(BenchmarkRun.id)).filter(BenchmarkRun.user_id == uid).scalar(),
        "workflows": db.query(func.count(Workflow.id)).filter(Workflow.user_id == uid).scalar(),
        "knowledge_bases": db.query(func.count(KnowledgeBase.id)).filter(KnowledgeBase.user_id == uid).scalar(),
        "best_score_avg": round(sum(scored_vals) / len(scored_vals), 1) if scored_vals else 0,
    }


def _count_cases(db: Session, task_ids: list[int]) -> int:
    """按任务 id 集合统计用例总数（SQL 聚合）。"""
    if not task_ids:
        return 0
    return db.query(func.count(TestCase.id)).filter(TestCase.task_id.in_(task_ids)).scalar()


def _count_versions(db: Session, task_ids: list[int]) -> int:
    """按任务 id 集合统计版本总数。"""
    if not task_ids:
        return 0
    return db.query(func.count(PromptVersion.id)).filter(PromptVersion.task_id.in_(task_ids)).scalar()


def get_trend(db: Session, user: User, days: int = 30) -> dict:
    """近 N 天活动趋势：按创建日（YYYY-MM-DD）分组计数各实体。

    :return: {"days": N, "series": {"task": {date: count}, "benchmark": ..., ...}}
    """
    uid = user.id
    # 窗口起点：含当天在内共 days 天（created_at 为 "YYYY-MM-DD ..." 字符串，可直接字典序比较）
    start = (date.today() - timedelta(days=days - 1)).isoformat()
    # (key, model) 列表：每个模型按 created_at 前 10 字符分组计数
    entities = (
        ("task", Task),
        ("benchmark", BenchmarkRun),
        ("endpoint", Endpoint),
        ("call", EndpointCallLog),
        ("workflow", Workflow),
        ("workflow_run", WorkflowRun),
        ("optimization", WorkflowStepOptimization),
        ("kb", KnowledgeBase),
    )
    series: dict[str, dict[str, int]] = defaultdict(dict)
    for key, model in entities:
        table = model.__table__
        date_expr = func.substr(table.c.created_at, 1, 10)
        q = db.query(date_expr.label("d"), func.count(table.c.id)).group_by(date_expr)
        if "user_id" in table.columns:
            q = q.filter(table.c.user_id == uid)
        elif key == "call":
            # 调用日志无 user_id 列，必须经端点表归属到当前用户，防跨租户计数
            q = q.join(Endpoint, EndpointCallLog.endpoint_id == Endpoint.id) \
                 .filter(Endpoint.user_id == uid)
        elif key in ("workflow_run", "optimization"):
            # 工作流运行/步骤优化无 user_id，必须经工作流表归属当前用户，防跨租户计数
            q = q.join(Workflow, table.c.workflow_id == Workflow.id) \
                 .filter(Workflow.user_id == uid)
        q = q.filter(table.c.created_at >= start)
        series[key] = {d: int(c) for d, c in q.all()}
    return {"days": days, "series": {k: dict(v) for k, v in series.items()}}


def get_tasks(db: Session, user: User, keyword: str = "") -> dict:
    """任务资产表：每个任务的用例数/版本数/评测次数/工作流数/最新最优分，可按名称搜索。"""
    uid = user.id
    q = db.query(Task).filter(Task.user_id == uid)
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        q = q.filter(Task.name.like(like))
    tasks = q.order_by(Task.updated_at.desc()).all()

    items = []
    for t in tasks:
        tids = [t.id]
        items.append({
            "id": t.id,
            "name": t.name,
            "task_type": t.task_type,
            "status": t.status,
            "case_count": _count_cases(db, tids),
            "version_count": _count_versions(db, tids),
            "benchmark_count": db.query(func.count(BenchmarkRun.id))
                .filter(BenchmarkRun.task_id == t.id).scalar(),
            "workflow_count": db.query(func.count(Workflow.id))
                .filter(Workflow.task_id == t.id).scalar(),
            "best_score": t.best_score,
            "current_round": t.current_round,
            "max_rounds": t.max_rounds,
            "updated_at": t.updated_at,
            "created_at": t.created_at,
        })
    return {"items": items, "total": len(items)}


def get_models(db: Session, user: User) -> dict:
    """模型统计：端点调用各模型次数/成功率/平均耗时 + 评测最优模型分布。"""
    uid = user.id
    # 端点调用按模型聚合（join 端点取 model）
    call_rows = (
        db.query(
            Endpoint.model,
            func.count(EndpointCallLog.id),
            func.sum(case((EndpointCallLog.status == "success", 1), else_=0)),
            func.avg(EndpointCallLog.latency_ms),
        )
        .join(Endpoint, EndpointCallLog.endpoint_id == Endpoint.id)
        .filter(Endpoint.user_id == uid)
        .group_by(Endpoint.model)
        .all()
    )
    calls = []
    for model, total, ok, avg in call_rows:
        calls.append({
            "model": model,
            "calls": int(total or 0),
            "success_rate": round(100.0 * (ok or 0) / total, 1) if total else 0,
            "avg_latency_ms": round(avg, 1) if avg else 0,
        })
    # 评测最优模型分布（benchmark_runs.best_model）
    best_rows = (
        db.query(BenchmarkRun.best_model, func.count(BenchmarkRun.id))
        .filter(BenchmarkRun.user_id == uid, BenchmarkRun.best_model.isnot(None))
        .group_by(BenchmarkRun.best_model)
        .all()
    )
    best_dist = [{"model": m, "count": int(c)} for m, c in best_rows]
    return {"calls": calls, "best_dist": best_dist}


def search_versions(db: Session, user: User, keyword: str = "", task_id: int | None = None,
                    limit: int = 50) -> dict:
    """Prompt 版本库检索：跨任务搜索冻结/任意版本，可按任务过滤。"""
    uid = user.id
    # 归属校验：只允许搜索当前用户任务下的版本
    own_tids = _task_ids_of(db, uid)
    if not own_tids:
        return {"items": [], "total": 0}
    q = (
        db.query(PromptVersion, Task.name)
        .join(Task, PromptVersion.task_id == Task.id)
        .filter(PromptVersion.task_id.in_(own_tids))
    )
    if task_id is not None:
        q = q.filter(PromptVersion.task_id == task_id)
    if keyword.strip():
        like = f"%{keyword.strip()}%"
        q = q.filter(or_(PromptVersion.prompt_text.like(like), Task.name.like(like)))
    total = q.count()  # 过滤后的真实匹配总数（不含排序/分页）
    rows = q.order_by(PromptVersion.id.desc()).limit(limit).all()
    items = [{
        "id": pv.id,
        "task_id": pv.task_id,
        "task_name": tname,
        "version_no": pv.version_no,
        "prompt_text": pv.prompt_text,
        "is_best": pv.is_best,
        "score": pv.score,
        "frozen": pv.frozen,
        "created_at": pv.created_at,
    } for pv, tname in rows]
    return {"items": items, "total": total}
