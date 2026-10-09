# ==========================================================
# 报告分享表模型：为「评测对比/工作流优化/任务迭代」报告
# 生成免登录的只读分享链接（令牌 + 可设置过期 + 可撤销 + 访问计数）
# ==========================================================
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import now_iso


class ReportShare(Base):
    """一条报告分享记录。

    report_type: benchmark=多模型对比评测 / optimization=工作流步骤优化 / task=任务迭代
    target_id  : 对应 BenchmarkRun.id / WorkflowStepOptimization.id / Task.id
    status     : active=生效 / revoked=已撤销（撤销后公开访问失效）
    expires_at : ISO 时间戳；None 表示永不过期
    """

    __tablename__ = "report_shares"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    report_type: Mapped[str] = mapped_column(String(16), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    expires_at: Mapped[str] = mapped_column(String(32), nullable=True)
    view_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)