# ==========================================================
# 报告分享服务：创建/列表/撤销分享链接 + 免登录公开只读数据
# 支持报告类型：benchmark(多模型对比评测)/optimization(工作流步骤优化)/task(任务迭代)
# 公开数据直接复用各报告构建函数 build_report(db, entity)，保证口径一致
# ==========================================================
import secrets
from datetime import datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.exceptions import not_found, state_error
from app.models import BenchmarkRun, ReportShare, Task, User, Workflow, WorkflowStepOptimization

# 允许的报告类型集合
REPORT_TYPES = ("benchmark", "optimization", "task")
# 允许选择的限时时长（小时）；0 或不传表示永不过期
ALLOWED_EXPIRY_HOURS = (0, 1, 12, 24, 168, 720)


def _assert_target_owned(db: Session, user_id: int, report_type: str, target_id: int) -> str:
    """校验报告目标属于当前用户，返回分享标题；不合法则抛业务异常。

    归属规则（与各模块读取鉴权一致，防越权分享他人资产）：
      benchmark    → BenchmarkRun.user_id
      optimization → 优化记录经 workflow_id 关联到 Workflow.user_id
      task         → Task.user_id
    """
    if report_type == "benchmark":
        run = db.get(BenchmarkRun, target_id)
        if run is None or run.user_id != user_id:
            raise not_found("评测记录不存在或无权访问")
        return run.name or f"评测#{run.id}"
    if report_type == "optimization":
        opt = db.get(WorkflowStepOptimization, target_id)
        if opt is None:
            raise not_found("优化记录不存在")
        wf = db.get(Workflow, opt.workflow_id)
        if wf is None or wf.user_id != user_id:
            raise not_found("优化记录不存在或无权访问")
        return f"工作流步骤{opt.step_seq}优化"
    # task
    task = db.get(Task, target_id)
    if task is None or task.user_id != user_id:
        raise not_found("任务不存在或无权访问")
    return f"任务-{task.name}"


def create_share(db: Session, user: User, report_type: str, target_id: int,
                 expires_hours: int | None = None) -> dict:
    """创建一条分享链接。

    expires_hours：0/None=永久；否则必须是 ALLOWED_EXPIRY_HOURS 中的值。
    """
    if report_type not in REPORT_TYPES:
        raise state_error(f"不支持的报告类型：{report_type}，可选 {', '.join(REPORT_TYPES)}")
    if expires_hours is not None and expires_hours not in ALLOWED_EXPIRY_HOURS:
        raise state_error("expires_hours 仅支持 0(永久)/1/12/24/168/720 小时")

    title = _assert_target_owned(db, user.id, report_type, target_id)

    token = secrets.token_urlsafe(24)
    expires_at = None
    if expires_hours:
        expires_at = (datetime.now() + timedelta(hours=int(expires_hours))).strftime("%Y-%m-%dT%H:%M:%S")

    share = ReportShare(
        user_id=user.id, report_type=report_type, target_id=target_id,
        title=title, token=token, status="active", expires_at=expires_at,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return _to_dict(share)


def list_shares(db: Session, user: User) -> list[dict]:
    """当前用户全部分享记录（含已撤销，便于追溯）。"""
    rows = db.query(ReportShare).filter(ReportShare.user_id == user.id) \
        .order_by(ReportShare.id.desc()).all()
    return [_to_dict(r) for r in rows]


def revoke_share(db: Session, user: User, share_id: int) -> None:
    """撤销分享：仅属主可操作；撤销后公开访问返回失效。"""
    share = db.get(ReportShare, share_id)
    if share is None or share.user_id != user.id:
        raise not_found("分享记录不存在或无权访问")
    share.status = "revoked"
    db.commit()


def get_public_meta(db: Session, token: str) -> dict:
    """免登录获取分享元信息（不触发访问计数）。"""
    share = _lookup_by_token(db, token)
    return _public_meta(share)


def get_public_data(db: Session, token: str) -> dict:
    """免登录获取分享报告数据；生效且未过期则原子累加访问计数。

    :raises BizError: 链接不存在/已被撤销/已过期时抛出 404/410。
    """
    share = _lookup_by_token(db, token)
    _validate_active(share)

    # 原子自增访问计数，避免并发访问 lost update
    db.execute(
        update(ReportShare)
        .where(ReportShare.id == share.id)
        .values(view_count=ReportShare.view_count + 1)
    )
    db.commit()
    db.refresh(share)

    payload = _build_payload(db, share)
    return {"meta": _public_meta(share), "payload": payload}


def _lookup_by_token(db: Session, token: str) -> ReportShare:
    share = db.query(ReportShare).filter(ReportShare.token == token).first()
    if share is None:
        raise not_found("分享链接不存在或已失效")
    return share


def _validate_active(share: ReportShare) -> None:
    """校验分享处于生效态且未过期；否则抛 410。"""
    if share.status != "active" or _is_expired(share.expires_at):
        raise not_found("分享链接已失效（已撤销或已过期）")


def _is_expired(expires_at: str | None) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.now() > datetime.fromisoformat(expires_at)
    except ValueError:  # 异常格式一律视为已过期，避免绕过校验
        return True


def _build_payload(db: Session, share: ReportShare) -> dict:
    """按报告类型复用对应构建函数生成只读数据。"""
    if share.report_type == "benchmark":
        from app.services import benchmark_service
        run = db.get(BenchmarkRun, share.target_id)
        return benchmark_service.build_report(db, run) if run else {}
    if share.report_type == "optimization":
        from app.services import workflow_step_optimizer
        opt = db.get(WorkflowStepOptimization, share.target_id)
        return workflow_step_optimizer.build_report(db, opt) if opt else {}
    from app.services import report_service
    task = db.get(Task, share.target_id)
    return report_service.build_report(db, task) if task else {}


def _public_meta(share: ReportShare) -> dict:
    valid = share.status == "active" and not _is_expired(share.expires_at)
    return {
        "token": share.token,
        "report_type": share.report_type,
        "title": share.title,
        "status": share.status,
        "expires_at": share.expires_at,
        "valid": valid,
        "view_count": share.view_count,
        "created_at": share.created_at,
    }


def _to_dict(share: ReportShare) -> dict:
    return {
        "id": share.id,
        "report_type": share.report_type,
        "target_id": share.target_id,
        "title": share.title,
        "token": share.token,
        "status": share.status,
        "expires_at": share.expires_at,
        "view_count": share.view_count,
        "created_at": share.created_at,
        "url": f"/share/{share.token}",
    }