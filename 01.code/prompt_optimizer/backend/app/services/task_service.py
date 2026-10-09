# ==========================================================
# 任务服务：创建/查询/更新/删除/模板
# ==========================================================
import math

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import not_found, state_error
from app.models import PromptVersion, Task
from app.schemas.task import TaskCreate, TaskUpdate

settings = get_settings()

# 内置任务类型模板
TASK_TEMPLATES = {
    "text_gen": {
        "name": "文案生成",
        "description_template": "根据{输入的商品信息或主题描述}生成吸引人的营销文案",
        "criteria_template": "文案需覆盖核心卖点、结构完整（标题/卖点/行动号召）、语言简练有感染力，且不编造输入中不存在的数据",
        "recommended_metrics": ["关键词命中", "格式合规", "评审打分"],
        "example_cases": ["商品：无线蓝牙耳机，卖点：降噪、长续航24小时、防水"],
    },
    "summary": {
        "name": "文本摘要",
        "description_template": "对{输入的较原文段}生成忠实、简洁的摘要",
        "criteria_template": "摘要须忠于原文、覆盖关键信息、简洁精炼、通顺连贯，不得出现原文不存在的信息",
        "recommended_metrics": ["ROUGE-L", "BLEU", "关键词命中", "评审打分"],
        "example_cases": ["（一段新闻或说明文）请用3句话概括主要内容"],
    },
    "extraction": {
        "name": "信息抽取",
        "description_template": "从{输入的非结构化文本}中抽取{指定的实体与字段}并输出JSON",
        "criteria_template": "抽取须严格按schema输出合法JSON，字段值准确、完整；原文不存在的字段置空，不得臆造",
        "recommended_metrics": ["字段完整率", "格式合规", "关键词命中", "评审打分"],
        "example_cases": ["您好，我是XX公司YY职位的张三，电话138xxxx，邮箱 a@b.com"],
    },
    "code": {
        "name": "代码生成",
        "description_template": "根据{函数需求描述}生成符合要求的Python代码",
        "criteria_template": "函数签名与需求一致、逻辑正确可运行、不含语法错误、含必要注释、对边界输入有合理处理",
        "recommended_metrics": ["单元测试通过率", "格式合规", "评审打分"],
        "example_cases": ["编写函数 is_palindrome(s) 判断回文串"],
    },
    "custom": {
        "name": "自定义任务",
        "description_template": "自定义任务描述",
        "criteria_template": "自定义评分标准",
        "recommended_metrics": ["评审打分"],
        "example_cases": [],
    },
}


def get_task_owned(db: Session, task_id: int, user_id: int) -> Task:
    """按属主获取任务，非属主或不存在返回资源不存在。"""
    task = db.get(Task, task_id)
    if task is None or task.user_id != user_id:
        raise not_found("任务不存在或无权访问")
    return task


def create_task(db: Session, user_id: int, data: TaskCreate) -> Task:
    """创建优化任务。

    注：目标分数(target_score)遵循"未填即不设达标线"语义——
    前端留空时 data.target_score 为 None，这里保存为 None，
    让迭代只由"收敛判定/最大轮次"决定何时停止，而不被 85 分默认值提前截停。
    """
    task = Task(
        user_id=user_id,
        name=data.name.strip(),
        task_type=data.task_type,
        description=data.description.strip(),
        objective=data.objective.strip(),
        criteria=data.criteria.strip(),
        execution_model=data.execution_model,
        judge_model=data.judge_model,
        auto_weight=data.auto_weight,
        judge_weight=data.judge_weight,
        initial_prompt=data.initial_prompt,
        target_score=data.target_score,  # None 表示不设达标线
        max_rounds=data.max_rounds,
        variants_per_round=data.variants_per_round,
        concurrency=data.concurrency,
        stagnant_rounds=data.stagnant_rounds,
        kb_id=data.kb_id,
        enable_rag=data.enable_rag if data.enable_rag else 0,
        status="pending",
        current_round=0,
    )
    db.add(task)
    db.flush()
    # 绑定知识库时校验属主，防止越权绑定他人知识库
    if task.kb_id:
        _validate_kb_owned(db, task.kb_id, user_id)
    db.commit()
    db.refresh(task)
    return task


def _validate_kb_owned(db: Session, kb_id: int, user_id: int) -> None:
    """校验知识库存在且属主为当前用户；非法则抛业务异常。"""
    from app.services import rag_service

    rag_service.get_kb_owned(db, kb_id, user_id)


def list_tasks(db: Session, user_id: int, page: int, page_size: int,
               status: str | None = None, keyword: str | None = None) -> dict:
    """分页查询任务列表，附带用例数（用于前端列表直观展示）。"""
    conditions = [Task.user_id == user_id]
    if status:
        conditions.append(Task.status == status)
    if keyword:
        conditions.append(Task.name.contains(keyword))

    total = db.scalar(select(func.count()).select_from(Task).where(*conditions)) or 0
    rows = db.scalars(
        select(Task)
        .where(*conditions)
        .order_by(Task.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for t in rows:
        items.append({
            "id": t.id,
            "name": t.name,
            "task_type": t.task_type,
            "case_count": len(t.cases) if t.cases is not None else 0,
            "best_score": t.best_score,
            "status": t.status,
            "current_round": t.current_round,
            "created_at": t.created_at,
        })
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def update_task(db: Session, task: Task, data: TaskUpdate, allow_iteration_params: bool = True) -> Task:
    """更新任务字段。运行中任务禁止修改迭代相关参数。"""
    fields = data.model_dump(exclude_unset=True)
    iteration_params = {
        "max_rounds", "variants_per_round", "concurrency",
        "stagnant_rounds", "target_score",
    }
    if task.status == "running" and (iteration_params & set(fields.keys())):
        raise state_error("任务运行中，禁止修改迭代相关参数")

    for key, value in fields.items():
        setattr(task, key, value)
    # 绑定/更换知识库时校验属主，防止越权
    if "kb_id" in fields and fields["kb_id"]:
        _validate_kb_owned(db, fields["kb_id"], task.user_id)
    db.commit()
    db.refresh(task)
    return task


def delete_task(db: Session, task: Task) -> None:
    """删除任务（级联删除其用例/版本/迭代/评估结果）。运行中禁止删除。"""
    if task.status == "running":
        raise state_error("任务运行中，请先停止再删除")
    db.delete(task)
    db.commit()


def get_task_templates() -> list[dict]:
    """返回任务类型模板列表。"""
    return [{"task_type": k, **v} for k, v in TASK_TEMPLATES.items()]


def write_initial_version(db: Session, task: Task, prompt_text: str) -> PromptVersion:
    """写入初始提示词版本（version_no=0）。"""
    existed = db.scalar(select(PromptVersion).where(
        PromptVersion.task_id == task.id, PromptVersion.version_no == 0))
    if existed:
        return existed
    ver = PromptVersion(task_id=task.id, version_no=0, prompt_text=prompt_text,
                        is_best=1, score=task.best_score)
    db.add(ver)
    db.commit()
    db.refresh(ver)
    return ver