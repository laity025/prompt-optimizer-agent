# -*- coding: utf-8 -*-
# ==========================================================
# 任务、用例、迭代等相关 Pydantic Schema
# ==========================================================
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

TASK_TYPES = ["text_gen", "summary", "extraction", "code", "custom"]


# ---------- 任务 ----------
class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    task_type: str = Field(pattern="^(text_gen|summary|extraction|code|custom)$")
    description: str
    objective: str
    criteria: str
    execution_model: str = ""
    judge_model: str = ""
    auto_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    judge_weight: float = Field(default=0.5, ge=0.0, le=1.0)
    initial_prompt: Optional[str] = None
    target_score: Optional[float] = Field(default=None, ge=0.0, le=100.0)
    max_rounds: int = Field(default=10, ge=1, le=100)
    variants_per_round: int = Field(default=4, ge=1, le=20)
    concurrency: int = Field(default=2, ge=1, le=10)
    stagnant_rounds: int = Field(default=3, ge=1, le=20)
    # RAG 检索增强
    kb_id: Optional[int] = None
    enable_rag: int = Field(default=0, ge=0, le=1)


class TaskUpdate(BaseModel):
    """运行中任务仅可更新基础信息；迭代参数受限。"""

    name: Optional[str] = None
    description: Optional[str] = None
    objective: Optional[str] = None
    criteria: Optional[str] = None
    execution_model: Optional[str] = None
    judge_model: Optional[str] = None
    auto_weight: Optional[float] = None
    judge_weight: Optional[float] = None
    target_score: Optional[float] = None
    max_rounds: Optional[int] = None
    variants_per_round: Optional[int] = None
    concurrency: Optional[int] = None
    stagnant_rounds: Optional[int] = None
    kb_id: Optional[int] = None
    enable_rag: Optional[int] = Field(default=None, ge=0, le=1)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    name: str
    task_type: str
    description: str
    objective: str
    criteria: str
    execution_model: str
    judge_model: str
    auto_weight: float
    judge_weight: float
    initial_prompt: Optional[str] = None
    best_prompt: Optional[str] = None
    best_score: Optional[float] = None
    target_score: Optional[float] = None
    max_rounds: int
    variants_per_round: int
    concurrency: int
    stagnant_rounds: int
    kb_id: Optional[int] = None
    enable_rag: int = 0
    status: str
    current_round: int
    last_error: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class TaskListItem(BaseModel):
    id: int
    name: str
    task_type: str
    case_count: int = 0
    best_score: Optional[float] = None
    status: str
    current_round: int
    created_at: str


# ---------- 用例 ----------
class CaseCreate(BaseModel):
    input_text: str = Field(min_length=1)
    reference_output: Optional[str] = None
    keywords: Optional[list[str]] = None
    run_test: Optional[str] = None  # JSON 字符串


class CaseOut(BaseModel):
    id: int
    task_id: int
    input_text: str
    reference_output: Optional[str] = None
    keywords: Optional[str] = None
    run_test: Optional[str] = None
    sort_order: int
    created_at: str


class ImportResult(BaseModel):
    total: int
    success: int
    failed: int
    errors: list[str]


# ---------- 迭代 ----------
class StartIterationResult(BaseModel):
    task_id: int
    task_status: str
    total_rounds: int
    start_round: int
    resume: bool


class IterationStatus(BaseModel):
    task_id: int
    task_status: str
    current_round: int
    max_rounds: int
    current_best_score: Optional[float] = None
    variants_done: int = 0
    variants_total: int = 0
    cases_done: int = 0
    cases_total: int = 0
    cases_success: int = 0
    cases_failed: int = 0
    message: Optional[str] = None


class VariantOut(BaseModel):
    id: int
    variant_no: int
    prompt_text: str
    strategy_tag: Optional[str] = None
    score: Optional[float] = None
    status: str


class ScorePoint(BaseModel):
    round: int
    best_score: float


class ScoreCurve(BaseModel):
    rounds: list[ScorePoint] = []
    target_score: Optional[float] = None


class VersionOut(BaseModel):
    id: int
    version_no: int
    prompt_text: str
    is_best: int
    score: Optional[float] = None
    frozen: int
    created_at: str


class EvalResultOut(BaseModel):
    id: int
    variant_no: int
    test_case_id: int
    model_output: Optional[str] = None
    outcome: str
    error_reason: Optional[str] = None
    bleu: Optional[float] = None
    rouge: Optional[float] = None
    keyword_hit: Optional[float] = None
    format_ok: Optional[int] = None
    judge_score: Optional[int] = None
    judge_reason: Optional[str] = None
    total_score: Optional[float] = None
    manual_score: Optional[int] = None
    manual_checked: int = 0
    manual_note: Optional[str] = None


class ReviewRequest(BaseModel):
    manual_score: int = Field(ge=1, le=10)
    manual_note: Optional[str] = None