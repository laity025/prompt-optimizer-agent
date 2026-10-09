# ==========================================================
# 管理员接口：系统日志 / 用户列表 / 用户启停与角色
# ==========================================================
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.deps import get_current_admin
from app.core.exceptions import not_found, param_error, state_error
from app.db.base import get_db
from app.models import OperationLog, User
from app.schemas.extra import AdminUserUpdate

router = APIRouter(prefix="/admin", tags=["管理员"], dependencies=[Depends(get_current_admin)])


@router.get("/logs", summary="系统日志")
def admin_logs(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    user_id: int | None = None,
    result: str | None = None,
):
    q = select(OperationLog)
    conds = []
    if user_id:
        conds.append(OperationLog.user_id == user_id)
    if result:
        conds.append(OperationLog.result == result)
    total = db.scalar(select(func.count()).select_from(OperationLog).where(*conds)) or 0
    rows = db.scalars(
        q.where(*conds).order_by(OperationLog.created_at.desc())
        .offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        {"id": r.id, "user_id": r.user_id, "task_id": r.task_id, "action": r.action,
         "result": r.result, "detail": r.detail, "duration_ms": r.duration_ms, "created_at": r.created_at}
        for r in rows
    ]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.get("/users", summary="用户列表")
def admin_users(
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    total = db.scalar(select(func.count()).select_from(User)) or 0
    rows = db.scalars(select(User).order_by(User.id).offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        {"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role,
         "is_active": u.is_active, "created_at": u.created_at}
        for u in rows
    ]
    return {"code": 0, "message": "success", "data": {"items": items, "total": total, "page": page, "page_size": page_size}}


@router.put("/users/{user_id}", summary="修改用户角色/启停")
def admin_update_user(user_id: int, body: AdminUserUpdate, db: Session = Depends(get_db),
                      admin: User = Depends(get_current_admin)):
    user = db.get(User, user_id)
    if user is None:
        raise not_found("用户不存在")
    if body.role is not None:
        if body.role not in ("user", "admin"):
            raise param_error("role 仅支持 user/admin")
        user.role = body.role
    if body.is_active is not None:
        # 不能对自身执行禁用，防止锁定唯一管理员
        if admin.id == user.id and body.is_active == 0:
            raise state_error("不能禁用当前登录账号")
        user.is_active = body.is_active
    db.commit()
    return {"code": 0, "message": "success", "data": {"id": user.id, "role": user.role, "is_active": user.is_active}}