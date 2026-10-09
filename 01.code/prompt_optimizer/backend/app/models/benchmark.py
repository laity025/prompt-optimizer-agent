# ==========================================================
# 多模型横向对比评测表模型
# BenchmarkRun：一次对比评测运行；BenchmarkResult：单模型在单用例上的评估明细
# ==========================================================
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class BenchmarkRun(Base):
    """一次「多模型横向对比」评测运行。

    记录评测所用提示词快照、参与对比的模型集合、运行状态与最优模型结论。
    """

    __tablename__ = "benchmark_runs"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # 评测提示词来源：best=当前最优 / initial=初始 / custom=自定义
    prompt_mode: Mapped[str] = mapped_column(String(16), nullable=False, default="best")
    prompt_snapshot: Mapped[str] = mapped_column(Text, nullable=True)
    # 参与对比的模型列表，逗号分隔
    models_json: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/completed/failed
    progress: Mapped[str] = mapped_column(Text, nullable=True)
    best_model: Mapped[str] = mapped_column(String(128), nullable=True)
    best_score: Mapped[float] = mapped_column(Float, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    finished_at: Mapped[str] = mapped_column(String(32), nullable=True)

    results = relationship("BenchmarkResult", back_populates="run",
                           cascade="all, delete-orphan")


class BenchmarkResult(Base):
    """单模型在某用例上的评测结果（含输出、指标、评审分、综合分）。"""

    __tablename__ = "benchmark_results"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("benchmark_runs.id"), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    test_case_id: Mapped[int] = mapped_column(Integer, nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=True)
    output: Mapped[str] = mapped_column(Text, nullable=True)
    error_reason: Mapped[str] = mapped_column(Text, nullable=True)
    # 自动指标（含参考输出时才有 BLEU/ROUGE）
    bleu: Mapped[float] = mapped_column(Float, nullable=True)
    rouge: Mapped[float] = mapped_column(Float, nullable=True)
    keyword_hit: Mapped[float] = mapped_column(Float, nullable=True)
    format_ok: Mapped[int] = mapped_column(Integer, nullable=True)
    # 横向归一化后的评审分（1-10）与理由
    judge_score: Mapped[float] = mapped_column(Float, nullable=True)
    judge_reason: Mapped[str] = mapped_column(Text, nullable=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=True)

    run = relationship("BenchmarkRun", back_populates="results")