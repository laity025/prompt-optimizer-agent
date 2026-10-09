# ==========================================================
# 提示词版本表模型
# ==========================================================
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class PromptVersion(Base):
    """提示词版本：初始版(0)与每轮最优版，支持冻结与回退。"""

    __tablename__ = "prompt_versions"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)  # 初始=0, 每轮=轮次号
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    is_best: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score: Mapped[float] = mapped_column(Float, nullable=True)
    parent_version_id: Mapped[int] = mapped_column(Integer, nullable=True)
    frozen: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    task = relationship("Task", back_populates="versions")