# ==========================================================
# 依赖注入：get_current_user / get_current_admin
# ==========================================================
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.exceptions import forbidden
from app.core.security import decode_access_token
from app.db.base import get_db
from app.models import User

# Bearer token 提取器
bearer_scheme = HTTPBearer(auto_error=False)

# HttpOnly cookie 名：登录时由后端写入（前端 JS 不可读，防 XSS 窃取）
AUTH_COOKIE_NAME = "access_token"


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """从请求头（Authorization: Bearer）或 HttpOnly cookie 解析 JWT 并加载当前用户。

    优先取 Authorization 头（兼容 curl / 脚本等外部调用方），
    其次取 cookie（浏览器 SPA 登录态）；均缺失返回 401。

    说明：鉴权失败统一抛 401（由全局 handler 转响应，见 main.py）。
    """
    from app.core.exceptions import BizError

    token = credentials.credentials if credentials is not None else None
    if not token:
        token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        raise BizError(401, "未登录或登录已过期")
    payload = decode_access_token(token)
    if payload is None or "sub" not in payload:
        raise BizError(401, "未登录或登录已过期")
    user = db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        raise BizError(401, "账号不存在或已被禁用")
    return user


def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """仅允许 admin 角色访问；否则返回 403（code=1003）。"""
    if user.role != "admin":
        raise forbidden("无管理员权限")
    return user