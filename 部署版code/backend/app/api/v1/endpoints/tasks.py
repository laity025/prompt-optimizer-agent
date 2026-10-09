# ==========================================================
# 任务接口：创建/列表/详情/更新/删除/模板
# ==========================================================
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import BizError
from app.db.base import get_db
from app.models import User
from app.schemas.task import TaskCreate, TaskOut, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["任务"])


@router.post("", summary="创建任务")
def create_task(body: TaskCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.create_task(db, user.id, body)
    return {"code": 0, "message": "success", "data": TaskOut.model_validate(task).model_dump()}


@router.get("", summary="任务列表")
def list_tasks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    status: str | None = None,
    keyword: str | None = None,
):
    data = task_service.list_tasks(db, user.id, page, page_size, status, keyword)
    return {"code": 0, "message": "success", "data": data}


@router.get("/{task_id}", summary="任务详情")
def get_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    return {"code": 0, "message": "success", "data": TaskOut.model_validate(task).model_dump()}


@router.get("/{task_id}/best", summary="获取最优提示词")
def get_best_prompt(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    return {"code": 0, "message": "success", "data": {
        "task_id": task.id,
        "best_prompt": task.best_prompt,
        "best_score": task.best_score,
    }}


@router.put("/{task_id}", summary="更新任务")
def update_task(task_id: int, body: TaskUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    task = task_service.update_task(db, task, body)
    return {"code": 0, "message": "success", "data": TaskOut.model_validate(task).model_dump()}


@router.delete("/{task_id}", summary="删除任务")
def delete_task(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    task_service.delete_task(db, task)
    return {"code": 0, "message": "success", "data": None}


# 模板独立于任务资源，放在任务前缀下不会冲突；此处另提供 /task-templates 在 api.py 挂载
TEMPLATES_ROUTER_PREFIX = "/task-templates"