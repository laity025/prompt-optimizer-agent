# ==========================================================
# 版本接口：版本历史 / 冻结 / 回退
# ==========================================================
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import not_found, state_error
from app.db.base import get_db
from app.models import PromptVersion, User
from app.services import task_service

router = APIRouter(prefix="/tasks", tags=["版本"])


@router.get("/{task_id}/versions", summary="版本历史")
def version_history(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    items = [
        {"id": v.id, "version_no": v.version_no, "prompt_text": v.prompt_text,
         "is_best": v.is_best, "score": v.score, "frozen": v.frozen, "created_at": v.created_at}
        for v in db.query(PromptVersion).filter(PromptVersion.task_id == task_id).order_by(PromptVersion.version_no).all()
    ]
    return {"code": 0, "message": "success", "data": items}


@router.post("/{task_id}/versions/{version_id}/freeze", summary="冻结/回退版本")
def freeze_revert(task_id: int, version_id: int,
                  action: str = "freeze",
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    ver = db.get(PromptVersion, version_id)
    if ver is None or ver.task_id != task_id:
        raise not_found("版本不存在")

    if action == "freeze":
        ver.frozen = 1
        db.commit()
        return {"code": 0, "message": "success", "data": {"version_id": ver.id, "action": "freeze", "frozen": 1}}

    if action == "revert":
        # 回退前提：任务已停止或已完成
        if task.status not in ("stopped", "completed", "pending"):
            raise state_error("仅已停止或已完成的任务可回退")
        task.best_prompt = ver.prompt_text
        task.best_score = ver.score
        task.status = "pending"
        db.commit()
        return {"code": 0, "message": "success",
                "data": {"version_id": ver.id, "action": "revert", "prompt": ver.prompt_text}}

    raise state_error("action 参数仅支持 freeze 或 revert")