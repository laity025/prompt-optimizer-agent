# ==========================================================
# 评估结果表模型
# ==========================================================
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class EvalResult(Base):
    """变体在单个用例上的评估记录，完整留痕支持复现与人工抽检。"""

    __tablename__ = "eval_results"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id"), nullable=False)
    test_case_id: Mapped[int] = mapped_column(ForeignKey("test_cases.id"), nullable=False)
    model_output: Mapped[str] = mapped_column(Text, nullable=True)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False, default="success")  # success/failed
    error_reason: Mapped[str] = mapped_column(Text, nullable=True)
    # 自动指标
    bleu: Mapped[float] = mapped_column(Float, nullable=True)
    rouge: Mapped[float] = mapped_column(Float, nullable=True)
    keyword_hit: Mapped[float] = mapped_column(Float, nullable=True)
    format_ok: Mapped[int] = mapped_column(Integer, nullable=True)
    # 评审打分
    judge_score: Mapped[int] = mapped_column(Integer, nullable=True)
    judge_reason: Mapped[str] = mapped_column(Text, nullable=True)
    total_score: Mapped[float] = mapped_column(Float, nullable=True)
    # 人工抽检
    manual_score: Mapped[int] = mapped_column(Integer, nullable=True)
    manual_checked: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    manual_note: Mapped[str] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    variant = relationship("Variant", back_populates="evals")
    test_case = relationship("TestCase", back_populates="evals")