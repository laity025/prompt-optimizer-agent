# ==========================================================
# 报告接口：获取报告 / 导出 Markdown/JSON
# ==========================================================
import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.base import get_db
from app.models import User
from app.services import report_service, task_service

router = APIRouter(prefix="/tasks", tags=["报告"])


@router.get("/{task_id}/report", summary="获取优化报告")
def get_report(task_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    return {"code": 0, "message": "success", "data": report_service.build_report(db, task)}


@router.get("/{task_id}/report/export", summary="导出报告")
def export_report(task_id: int, format: str = Query("markdown"),
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    task = task_service.get_task_owned(db, task_id, user.id)
    report = report_service.build_report(db, task)
    date_str = datetime.now().strftime("%Y%m%d")

    if format == "json":
        body = json.dumps(report, ensure_ascii=False, indent=2)
        filename = f"report_task_{task.id}_{date_str}.json"
        return PlainTextResponse(body, media_type="application/json",
                                 headers={"Content-Disposition": f'attachment; filename="{filename}"'})

    # 默认 markdown
    lines = [
        f"# 提示词优化报告 - {task.name}",
        "",
        f"- 任务ID：{task.id}",
        f"- 任务类型：{task.task_type}",
        f"- 当前最优得分：{task.best_score}",
        "",
        "## 最优提示词",
        "",
        task.best_prompt or "（无）",
        "",
        "## 得分曲线",
        "",
    ]
    for pt in report["score_curve"]:
        lines.append(f"- 第{pt['round']}轮：{pt['best_score']} 分")
    lines += ["", "## 评审总结", ""]
    for j in report["judge_summary"]:
        lines.append(f"- 第{j['round']}轮（{j['best_score']}分）：{j['reason']}")
    lines += ["", "## 优化建议", ""]
    for s in report["suggestions"]:
        lines.append(f"- {s}")
    body = "\n".join(lines)
    filename = f"report_task_{task.id}_{date_str}.md"
    return PlainTextResponse(body, media_type="text/markdown",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})