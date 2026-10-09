# ==========================================================
# 迭代轮次与提示词变体表模型
# ==========================================================
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class Iteration(Base):
    """一次迭代轮次：记录基准提示词与最优变体快照。"""

    __tablename__ = "iterations"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    round_no: Mapped[int] = mapped_column(Integer, nullable=False)
    base_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    best_variant_id: Mapped[int] = mapped_column(Integer, nullable=True)
    best_score: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")  # running/completed/failed
    started_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    finished_at: Mapped[str] = mapped_column(String(32), nullable=True)

    task = relationship("Task", back_populates="iterations")
    variants = relationship("Variant", back_populates="iteration", cascade="all, delete-orphan")


class Variant(Base):
    """单轮内的提示词变体：携带生成策略标签、综合得分与执行摘要。"""

    __tablename__ = "variants"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    iteration_id: Mapped[int] = mapped_column(ForeignKey("iterations.id"), nullable=False)
    variant_no: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    strategy_tag: Mapped[str] = mapped_column(String(64), nullable=True)
    score: Mapped[float] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")  # pending/running/completed/failed
    exec_summary: Mapped[str] = mapped_column(Text, nullable=True)  # JSON 摘要
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    iteration = relationship("Iteration", back_populates="variants")
    evals = relationship("EvalResult", back_populates="variant", cascade="all, delete-orphan")