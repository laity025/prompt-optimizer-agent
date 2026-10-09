# ==========================================================
# 生产静态托管：将前端构建产物(static/)交给 FastAPI 统一提供服务
# 实现 SPA history fallback，使单端口访问整个应用
# 仅在 backend/static/index.html 存在时生效（开发环境不启用）
# ==========================================================
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings

settings = get_settings()

# 前端静态目录：部署时将 frontend/dist 内容复制到 backend/static
# 注：config.base_dir 实际指向 app/，故须用其父级取到 backend 目录
BACKEND_DIR = settings.base_dir.parent
STATIC_DIR = BACKEND_DIR / "static"
ASSETS_DIR = STATIC_DIR / "assets"


def setup_static_host(app: FastAPI) -> bool:
    """挂载静态资源与 SPA 回退；目录不存在返回 False 表示未启用。"""
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return False

    # 静态资源（构建后的 JS/CSS/图片，访问路径 /assets/...）
    if ASSETS_DIR.exists():
        app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

    # SPA history 回退：非 API 路径统一返回 index.html，交给前端路由处理
    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str):
        # 未匹配的 /api/... 路径返回 JSON 404，避免被吞成前端页面，便于客户端排错
        if full_path == "api" or full_path.startswith("api/"):
            return JSONResponse({"code": 404, "message": "接口不存在", "data": None})
        return FileResponse(index)

    return True