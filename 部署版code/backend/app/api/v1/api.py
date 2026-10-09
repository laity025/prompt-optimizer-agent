# ==========================================================
# API 路由汇总：挂载各端点
# ==========================================================
from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    benchmarks,
    cases,
    dashboard,
    iterations,
    knowledge,
    online,
    report,
    report_shares,
    templates,
    tasks,
    versions,
    workflows,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(tasks.router)
api_router.include_router(cases.router)
api_router.include_router(iterations.router)
api_router.include_router(versions.router)
api_router.include_router(workflows.router)
api_router.include_router(benchmarks.router)
api_router.include_router(benchmarks.global_router)
api_router.include_router(online.router)
api_router.include_router(knowledge.router)
api_router.include_router(report.router)
api_router.include_router(templates.router)
api_router.include_router(dashboard.router)
api_router.include_router(report_shares.auth_router)
api_router.include_router(report_shares.public_router)
api_router.include_router(admin.router)