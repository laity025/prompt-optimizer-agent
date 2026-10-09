# ==========================================================
# 认证接口：注册 / 登录 / 登出 / 当前用户
#   token 通过 HttpOnly + SameSite=Lax cookie 下发（防 XSS 窃取）
#   同时响应体仍返回 token，兼容 curl / 脚本等外部调用方走 Bearer 头
# ==========================================================
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.deps import AUTH_COOKIE_NAME, get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.auth import LoginRequest, LoginResponse, RegisterRequest, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["认证"])

# JWT 有效期 24h，cookie 有效期保持一致
_AUTH_COOKIE_MAX_AGE = 24 * 60 * 60


def _set_auth_cookie(response: Response, token: str) -> None:
    """写入登录态 cookie：HttpOnly 防 XSS 读取；SameSite=Lax 使跨站 POST 不携带（防 CSRF）。

    说明：CSRF 双保险——写操作均要求 application/json（跨站表单发不出），
    且未配置跨域白名单，跨站请求会被浏览器 CORS 预检拦截。
    secure 由配置 COOKIE_SECURE 控制：本机/内网 HTTP 默认 False，公网 HTTPS 生产置 True。
    """
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=_AUTH_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=get_settings().COOKIE_SECURE,
        path="/",
    )


def _client_ip(request: Request) -> str:
    """取客户端 IP：优先 X-Forwarded-For（Nginx 反代场景），回退直连地址。"""
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


@router.post("/register", summary="注册")
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register(db, body.email, body.password, body.full_name)
    return {"code": 0, "message": "success", "data": UserOut.model_validate(user).model_dump()}


@router.post("/login", summary="登录")
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    # 携带客户端 IP 供登录失败计数与锁定（防暴力破解）
    user, token = auth_service.login(db, body.email, body.password, _client_ip(request))
    data = LoginResponse(token=token, user=UserOut.model_validate(user)).model_dump()
    # 登录态写入 HttpOnly cookie（浏览器自动携带），响应体 token 供外部调用方使用
    resp = JSONResponse({"code": 0, "message": "success", "data": data})
    _set_auth_cookie(resp, token)
    return resp


@router.post("/logout", summary="退出登录")
def logout(response: Response):
    """清除登录态 cookie。cookie 不存在也返回成功（幂等）。"""
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    return {"code": 0, "message": "success", "data": None}


@router.get("/me", summary="当前用户信息")
def me(user: User = Depends(get_current_user)):
    return {"code": 0, "message": "success", "data": UserOut.model_validate(user).model_dump()}