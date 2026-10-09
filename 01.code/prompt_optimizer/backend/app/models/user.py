# ==========================================================
# 用户表模型
# ==========================================================
from datetime import datetime

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def now_iso() -> str:
    """当前时间 ISO 8601 字符串（本地时间）。"""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


class User(Base):
    """系统用户：注册/登录主体，业务数据按 user_id 隔离。"""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), nullable=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="user")
    is_active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=True)

    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")
    logs = relationship("OperationLog", back_populates="user", cascade="all, delete-orphan")