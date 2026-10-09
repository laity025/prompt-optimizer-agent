# ==========================================================
# 模型汇总：确保 create_all 能扫描到全部表
# ==========================================================
from app.models.user import User
from app.models.report_share import ReportShare
from app.models.task import Task
from app.models.test_case import TestCase
from app.models.prompt_version import PromptVersion
from app.models.iteration import Iteration, Variant
from app.models.eval_result import EvalResult
from app.models.operation_log import OperationLog
from app.models.benchmark import BenchmarkRun, BenchmarkResult
from app.models.endpoint import Endpoint, EndpointCallLog
from app.models.knowledge import KnowledgeBase, KnowledgeChunk, KnowledgeDoc
from app.models.workflow import (
    Workflow,
    WorkflowResult,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepOptVariant,
    WorkflowStepOptimization,
)

__all__ = [
    "User",
    "ReportShare",
    "Task",
    "TestCase",
    "PromptVersion",
    "Iteration",
    "Variant",
    "EvalResult",
    "OperationLog",
    "BenchmarkRun",
    "BenchmarkResult",
    "Endpoint",
    "EndpointCallLog",
    "KnowledgeBase",
    "KnowledgeDoc",
    "KnowledgeChunk",
    "Workflow",
    "WorkflowStep",
    "WorkflowRun",
    "WorkflowResult",
    "WorkflowStepOptimization",
    "WorkflowStepOptVariant",
]