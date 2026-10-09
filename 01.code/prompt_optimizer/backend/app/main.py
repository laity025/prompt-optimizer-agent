# ==========================================================
# FastAPI 应用入口：初始化建表、挂载路由、统一异常处理
# dev 启动：uvicorn app.main:app --reload --port 8000
# ==========================================================
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.exceptions import BizError
from app.db.init_db import init_db

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 启动时建表
init_db()


# ---------- 安全响应头（CSP 等） ----------
# 说明：仅对后端返回的响应生效；生产静态托管时 index.html 由 FastAPI 返回，CSP 随之生效。
# dev 模式前端页面由 vite dev server 返回，不受本头影响。
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "   # antd 大量内联 style，必须保留 unsafe-inline
    "img-src 'self' data:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """为所有响应附加安全头：CSP 限制脚本/连接来源，配合 HttpOnly cookie 缓解 XSS 与点击劫持。"""
    response = await call_next(request)
    response.headers.setdefault("Content-Security-Policy", _CSP)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


# ---------- 统一成功响应包装 ----------
def _ok(data):
    return {"code": 0, "message": "success", "data": data}


# ---------- 统一异常处理 ----------
@app.exception_handler(BizError)
async def biz_error_handler(request: Request, exc: BizError):
    """业务异常 → {code, message, data}。"""
    return JSONResponse(status_code=200, content={
        "code": exc.code, "message": exc.message, "data": exc.data
    })


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """参数校验失败 → code=1001。"""
    return JSONResponse(status_code=200, content={
        "code": 1001, "message": "参数校验失败", "data": {"errors": exc.errors()}
    })


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    """兜底异常 → code=1006。"""
    return JSONResponse(status_code=200, content={
        "code": 1006, "message": "内部错误", "data": None
    })


# ---------- 健康检查 ----------
@app.get("/health", tags=["系统"])
def health():
    return _ok({"status": "ok", "version": settings.APP_VERSION})


# ---------- 挂载业务路由 ----------
from app.api.v1.api import api_router  # noqa: E402

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

# ---------- 生产静态托管（部署时将前端构建产物放入 backend/static） ----------
from app.core.static_host import setup_static_host  # noqa: E402

setup_static_host(app)