# ==========================================================
# 报告、模板、管理员相关 Schema
# ==========================================================
from typing import Any, Optional

from pydantic import BaseModel


class TaskTemplate(BaseModel):
    """任务类型模板：供新建任务时预填描述/标准。"""

    task_type: str
    name: str
    description_template: str
    criteria_template: str
    recommended_metrics: list[str]
    example_cases: list[dict[str, Any]]


class ModelInfo(BaseModel):
    """可用模型描述。"""

    id: str
    name: str
    description: str


class ReportData(BaseModel):
    task_id: int
    task_name: str
    best_prompt: Optional[str] = None
    initial_prompt: Optional[str] = None
    score_curve: list[dict[str, Any]] = []
    version_diffs: list[dict[str, Any]] = []
    judge_summary: list[dict[str, Any]] = []
    suggestions: list[str] = []


class AdminUserUpdate(BaseModel):
    role: Optional[str] = None
    is_active: Optional[int] = None