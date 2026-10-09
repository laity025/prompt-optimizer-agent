# ==========================================================
# 系统操作日志表模型（管理员用）
# ==========================================================
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class OperationLog(Base):
    """操作日志：记录用户关键操作，供管理员审计。"""

    __tablename__ = "operation_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[str] = mapped_column(String(16), nullable=False, default="success")  # success/failed
    detail: Mapped[str] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    user = relationship("User", back_populates="logs")
    task = relationship("Task", back_populates="logs", foreign_keys=[task_id])