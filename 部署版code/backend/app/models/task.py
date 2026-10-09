# ==========================================================
# 优化任务表模型
# ==========================================================
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class Task(Base):
    """优化任务：描述优化目标、评分标准、迭代配置与当前最优提示词。"""

    __tablename__ = "tasks"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # text_gen/summary/extraction/code/custom
    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    criteria: Mapped[str] = mapped_column(Text, nullable=False)
    execution_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    judge_model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    auto_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    judge_weight: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    initial_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    best_prompt: Mapped[str] = mapped_column(Text, nullable=True)
    best_score: Mapped[float] = mapped_column(Float, nullable=True)
    # 终止条件配置
    target_score: Mapped[float] = mapped_column(Float, nullable=True)
    max_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    variants_per_round: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    stagnant_rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    # 已废弃的"提升阈值"参数（UI/API 不再使用），但旧库该列 NOT NULL 且无 DB 级默认，
    # 删除模型定义会导致历史任务的 INSERT 缺该列而失败，故仅保留列以兼容存量数据
    stop_threshold: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    # RAG 检索增强：绑定的知识库 + 开关。开启后评测执行时自动检索并注入知识库上下文
    kb_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("knowledge_bases.id"), nullable=True)
    enable_rag: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0=关 1=开
    # 运行状态
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    current_round: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=True)

    owner = relationship("User", back_populates="tasks")
    cases = relationship("TestCase", back_populates="task", cascade="all, delete-orphan")
    versions = relationship("PromptVersion", back_populates="task", cascade="all, delete-orphan")
    iterations = relationship("Iteration", back_populates="task", cascade="all, delete-orphan")
    logs = relationship(
        "OperationLog",
        back_populates="task",
        cascade="all, delete-orphan",
        foreign_keys="OperationLog.task_id",
    )