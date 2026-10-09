# ==========================================================
# 多 Agent / 多步工作流评测表模型
#   Workflow：一个线性多步工作流模板（步骤按序串联）
#   WorkflowStep：单步（prompt 模板 + 模型），可引用 {{input}} / {{stepN.out}} 占位符
#   WorkflowRun：一次工作流端到端评测运行
#   WorkflowResult：单用例在本次运行中的最终输出、步骤追踪与评测结果（含基线对照）
# ==========================================================
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class Workflow(Base):
    """面向 RAG/多 Agent 的线性多步工作流模板，隶属于某任务。"""

    __tablename__ = "workflows"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    steps = relationship(
        "WorkflowStep", back_populates="workflow",
        cascade="all, delete-orphan", order_by="WorkflowStep.seq",
    )
    runs = relationship(
        "WorkflowRun", back_populates="workflow",
        cascade="all, delete-orphan", order_by="WorkflowRun.id.desc()",
    )
    optimizations = relationship(
        "WorkflowStepOptimization", back_populates="workflow",
        cascade="all, delete-orphan", order_by="WorkflowStepOptimization.id.desc()",
    )


class WorkflowStep(Base):
    """工作流中的一步：按 seq 先后链式执行。

    prompt_template 支持占位符：
      {{input}}      -> 用例原始输入
      {{stepN.out}}  -> 第 N 步（seq=N）的输出
    步骤在推理前会用已完成的变量集对模板做插值。
    """

    __tablename__ = "workflow_steps"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # 可选指定模型；留空用任务执行模型
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # 输出变量名（用于报告展示；寻址固定为 {{step{seq}.out}}）
    output_var: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    workflow = relationship("Workflow", back_populates="steps")


class WorkflowRun(Base):
    """一次工作流评测运行：记录状态、平均分与基线对照平均分。"""

    __tablename__ = "workflow_runs"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/completed/failed
    run_baseline: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 是否跑单 prompt 基线对照
    avg_score: Mapped[float] = mapped_column(Float, nullable=True)  # 工作流端到端平均分
    baseline_avg_score: Mapped[float] = mapped_column(Float, nullable=True)  # 单 prompt 基线平均分
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    finished_at: Mapped[str] = mapped_column(String(32), nullable=True)

    workflow = relationship("Workflow", back_populates="runs")
    results = relationship(
        "WorkflowResult", back_populates="run",
        cascade="all, delete-orphan", order_by="WorkflowResult.test_case_id",
    )


class WorkflowResult(Base):
    """单个用例的工作流评测结果：最终输出 + 步骤追踪 + 指标/评审/综合分 + 基线对照。"""

    __tablename__ = "workflow_results"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("workflow_runs.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(Integer, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=True)
    final_output: Mapped[str] = mapped_column(Text, nullable=True)
    error_reason: Mapped[str] = mapped_column(Text, nullable=True)
    # 步骤追踪 JSON：[{seq, name, output_var, output}]
    step_trace: Mapped[str] = mapped_column(Text, nullable=True)
    # 自动指标（参考输出存在时才有 BLEU/ROUGE）
    bleu: Mapped[float] = mapped_column(Float, nullable=True)
    rouge: Mapped[float] = mapped_column(Float, nullable=True)
    keyword_hit: Mapped[float] = mapped_column(Float, nullable=True)
    format_ok: Mapped[int] = mapped_column(Integer, nullable=True)
    judge_score: Mapped[float] = mapped_column(Float, nullable=True)
    judge_reason: Mapped[str] = mapped_column(Text, nullable=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=True)
    # 单 prompt 基线对照
    baseline_output: Mapped[str] = mapped_column(Text, nullable=True)
    baseline_score: Mapped[float] = mapped_column(Float, nullable=True)

    run = relationship("WorkflowRun", back_populates="results")


class WorkflowStepOptimization(Base):
    """对工作流中某个单一步骤的自动迭代优化运行。

    复用优化器的变体生成与链式评测：以该步骤当前 prompt 为基准，多轮生成变体，
    每轮把最优变体作为下一轮基准并最终回写该步骤的 prompt_template。
    """

    __tablename__ = "workflow_step_optimizations"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow_id: Mapped[int] = mapped_column(ForeignKey("workflows.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(Integer, nullable=False)
    step_seq: Mapped[int] = mapped_column(Integer, nullable=False)  # 目标步骤序号（1-based）
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/completed/failed
    # 基准 / 结果
    base_prompt: Mapped[str] = mapped_column(Text, nullable=False)  # 优化前该步骤 prompt
    best_prompt: Mapped[str] = mapped_column(Text, nullable=True)   # 优化后最优 prompt
    base_score: Mapped[float] = mapped_column(Float, nullable=True)  # 优化前整链平均分（baseline sheet）
    best_score: Mapped[float] = mapped_column(Float, nullable=True)  # 优化后整链平均分
    improved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 是否较优化前提升
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    finished_at: Mapped[str] = mapped_column(String(32), nullable=True)

    variants = relationship(
        "WorkflowStepOptVariant", back_populates="optimization",
        cascade="all, delete-orphan", order_by="WorkflowStepOptVariant.round_no, WorkflowStepOptVariant.variant_no",
    )
    workflow = relationship("Workflow", back_populates="optimizations")


class WorkflowStepOptVariant(Base):
    """一次步骤优化中生成的单个变体及其整链评测打分。"""

    __tablename__ = "workflow_step_opt_variants"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    optimization_id: Mapped[int] = mapped_column(ForeignKey("workflow_step_optimizations.id"), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    variant_no: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    strategy_tag: Mapped[str] = mapped_column(String(32), nullable=False, default="rewrite")
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    avg_score: Mapped[float] = mapped_column(Float, nullable=True)  # 整链平均分
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending/running/completed/failed
    error_reason: Mapped[str] = mapped_column(Text, nullable=True)
    is_best: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 是否该轮最优变体

    optimization = relationship("WorkflowStepOptimization", back_populates="variants")