# ==========================================================
# Prompt 一键上线/在线调用服务表模型
# Endpoint：把任务的最优/冻结提示词封装为可对外的调用端点
# EndpointCallLog：每次调用的输入/输出日志与耗时
# ==========================================================
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class Endpoint(Base):
    """对外可调用的提示词服务端点。

    绑定某个任务的一份提示词快照 + 执行模型，生成独立 api_key 供外部调用鉴权。
    """

    __tablename__ = "service_endpoints"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str] = mapped_column(Text, nullable=True)
    # 发布生效的提示词快照（来自冻结版本或任务最优提示词），与执行模型/任务类型一并固化
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    api_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)  # 1=启用
    call_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    calls = relationship("EndpointCallLog", back_populates="endpoint",
                         cascade="all, delete-orphan")


class EndpointCallLog(Base):
    """端点调用日志：记录输入、输出、成败与耗时。"""

    __tablename__ = "endpoint_call_logs"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    endpoint_id: Mapped[int] = mapped_column(ForeignKey("service_endpoints.id"), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=True)
    output: Mapped[str] = mapped_column(Text, nullable=True)
    error_reason: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")  # success/failed
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    endpoint = relationship("Endpoint", back_populates="calls")