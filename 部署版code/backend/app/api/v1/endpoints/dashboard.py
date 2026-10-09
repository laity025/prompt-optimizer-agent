# ==========================================================
# 资产管理门户/汇总仪表盘接口
# 前缀 /dashboard，全部只读聚合查询，权限：登录用户（仅本人数据）
# ==========================================================
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["资产门户"])


def _ok(data):
    """统一成功响应封装（与其它端点一致）。"""
    return {"code": 0, "message": "success", "data": data}


@router.get("/overview", summary="资产总览")
def overview(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """跨模块资产统计卡片数据。"""
    return _ok(dashboard_service.get_overview(db, user))


@router.get("/trend", summary="近 N 天活动趋势")
def trend(days: int = Query(default=30, ge=7, le=90),
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """按创建日分组的各实体活动计数（任务/评测/端点/调用/工作流/知识库等）。"""
    return _ok(dashboard_service.get_trend(db, user, days))


@router.get("/tasks", summary="任务资产表")
def tasks(keyword: str = Query(default="", max_length=100),
          user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """任务资产列表：用例/版本/评测次数/工作流数/最新最优分，可按名称搜索。"""
    return _ok(dashboard_service.get_tasks(db, user, keyword))


@router.get("/models", summary="模型统计")
def models(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """端点调用各模型统计 + 评测最优模型分布。"""
    return _ok(dashboard_service.get_models(db, user))


@router.get("/versions", summary="Prompt 版本库检索")
def versions(keyword: str = Query(default="", max_length=100),
             task_id: int | None = Query(default=None, ge=1),
             limit: int = Query(default=50, ge=1, le=200),
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """跨任务检索提示词版本（冻结/最优/历史），可按任务过滤。"""
    return _ok(dashboard_service.search_versions(db, user, keyword, task_id, limit))
