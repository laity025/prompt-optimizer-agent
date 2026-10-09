# ==========================================================
# 报告分享接口。
# auth_router  ：登录态管理（创建/列表/撤销），前缀 /reports/shares
# public_router：免登录只读访问，前缀 /public/reports（仅令牌可用，无 JWT 依赖）
# ==========================================================
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.services import share_service

# 登录态管理：/api/v1/reports/shares
auth_router = APIRouter(prefix="/reports/shares", tags=["报告分享"])

# 免登录只读：/api/v1/public/reports
public_router = APIRouter(prefix="/public/reports", tags=["报告分享-公开"])


class ShareCreate(BaseModel):
    """创建分享链接的请求体。"""

    report_type: str = Field(description="benchmark/optimization/task")
    target_id: int = Field(ge=1, description="目标报告实体 id")
    expires_hours: int | None = Field(default=None, ge=0, description="限时时长(小时)，0/缺省=永久")


def _ok(data):
    return {"code": 0, "message": "success", "data": data}


@auth_router.post("", summary="创建分享链接")
def create_share(body: ShareCreate,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    share = share_service.create_share(db, user, body.report_type, body.target_id, body.expires_hours)
    return _ok(share)


@auth_router.get("", summary="我的分享列表")
def list_shares(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _ok({"items": share_service.list_shares(db, user)})


@auth_router.delete("/{share_id}", summary="撤销分享")
def revoke_share(share_id: int,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    share_service.revoke_share(db, user, share_id)
    return _ok({"id": share_id})


@public_router.get("/{token}", summary="公开：链接元信息")
def public_meta(token: str, db: Session = Depends(get_db)):
    return _ok(share_service.get_public_meta(db, token))


@public_router.get("/{token}/data", summary="公开：读取报告数据（无鉴权）")
def public_data(token: str, db: Session = Depends(get_db)):
    return _ok(share_service.get_public_data(db, token))