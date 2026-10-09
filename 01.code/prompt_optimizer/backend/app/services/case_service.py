# ==========================================================
# 用例服务：增、删、查、批量导入、分页
# ==========================================================
import csv
import io
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import not_found, state_error
from app.models import Task, TestCase
from app.schemas.task import CaseCreate


def get_case_owned(db: Session, task: Task, case_id: int) -> TestCase:
    """按任务属主获取用例。"""
    case = db.get(TestCase, case_id)
    if case is None or case.task_id != task.id:
        raise not_found("用例不存在")
    return case


def add_case(db: Session, task: Task, data: CaseCreate) -> TestCase:
    """添加单条用例。运行中任务禁止改写用例。"""
    if task.status == "running":
        raise state_error("任务运行中，禁止修改用例")
    keywords_json = json.dumps(data.keywords, ensure_ascii=False) if data.keywords else None
    case = TestCase(
        task_id=task.id,
        input_text=data.input_text.strip(),
        reference_output=data.reference_output,
        keywords=keywords_json,
        run_test=data.run_test,
        sort_order=0,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def import_cases(db: Session, task: Task, filename: str, raw: bytes) -> dict:
    """批量导入用例（.json 或 .csv），返回导入统计与错误列表。"""
    errors: list[str] = []
    records: list[dict] = []
    # 解析
    try:
        if filename.endswith(".csv"):
            text = raw.decode("utf-8-sig")
            reader = csv.DictReader(io.StringIO(text))
            for row in reader:
                records.append(dict(row))
        else:  # json
            data = json.loads(raw.decode("utf-8"))
            if isinstance(data, dict) and "cases" in data:
                items = data["cases"]
            elif isinstance(data, list):
                items = data
            else:
                raise ValueError("无法识别的 JSON 结构，应为列表或含 cases 字段")
            records = [dict(r) for r in items]
    except Exception as exc:  # noqa: BLE001
        errors.append(f"文件解析失败：{exc}")

    success = 0
    for i, rec in enumerate(records, start=1):
        input_text = (rec.get("input_text") or "").strip()
        if not input_text:
            errors.append(f"第{i}行缺少input_text")
            continue
        try:
            add_case(db, task, CaseCreate(
                input_text=input_text,
                reference_output=rec.get("reference_output"),
                keywords=rec.get("keywords"),
                run_test=rec.get("run_test"),
            ))
            success += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"第{i}行导入失败：{exc}")
    return {"total": len(records), "success": success, "failed": len(records) - success, "errors": errors}


def list_cases(db: Session, task: Task, page: int, page_size: int) -> dict:
    """分页返回用例列表。"""
    cond = select(func.count()).select_from(TestCase).where(TestCase.task_id == task.id)
    total = db.scalar(cond) or 0
    rows = db.scalars(
        select(TestCase)
        .where(TestCase.task_id == task.id)
        .order_by(TestCase.sort_order, TestCase.id)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    items = [
        {
            "id": c.id,
            "task_id": c.task_id,
            "input_text": c.input_text,
            "reference_output": c.reference_output,
            "keywords": c.keywords,
            "run_test": c.run_test,
            "sort_order": c.sort_order,
            "created_at": c.created_at,
        }
        for c in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def delete_case(db: Session, task: Task, case_id: int) -> None:
    """删除用例。运行中任务禁止删除。"""
    if task.status == "running":
        raise state_error("任务运行中，禁止删除用例")
    case = get_case_owned(db, task, case_id)
    db.delete(case)
    db.commit()