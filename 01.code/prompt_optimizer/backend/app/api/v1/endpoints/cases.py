# ==========================================================
# 测试用例接口：添加/导入/列表/删除
# ==========================================================
from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.schemas.task import CaseCreate
from app.services import case_service, task_service

router = APIRouter(prefix="/tasks", tags=["用例"])


@router.post("/{task_id}/cases", summary="添加单条用例")
def add_case(task_id: int, body: CaseCreate,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    case = case_service.add_case(db, task, body)
    return {"code": 0, "message": "success", "data": {
        "id": case.id, "task_id": case.task_id, "input_text": case.input_text,
        "reference_output": case.reference_output, "keywords": case.keywords,
        "run_test": case.run_test, "sort_order": case.sort_order, "created_at": case.created_at,
    }}


@router.post("/{task_id}/cases/import", summary="批量导入用例")
async def import_cases(task_id: int, file: UploadFile = File(...),
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    raw = await file.read()
    data = case_service.import_cases(db, task, file.filename or "import.json", raw)
    return {"code": 0, "message": "success", "data": data}


@router.get("/{task_id}/cases", summary="用例列表")
def list_cases(task_id: int,
               user: User = Depends(get_current_user), db: Session = Depends(get_db),
               page: int = Query(1, ge=1), page_size: int = Query(100, ge=1, le=200)):
    task = task_service.get_task_owned(db, task_id, user.id)
    data = case_service.list_cases(db, task, page, page_size)
    return {"code": 0, "message": "success", "data": data}


@router.delete("/{task_id}/cases/{case_id}", summary="删除用例")
def delete_case(task_id: int, case_id: int,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    case_service.delete_case(db, task, case_id)
    return {"code": 0, "message": "success", "data": None}