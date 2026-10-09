# ==========================================================
# 测试用例表模型
# ==========================================================
from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import now_iso


class TestCase(Base):
    """测试用例：输入 + 参考输出 + 关键词 + 代码类单元测试，用于驱动评估。"""

    __tablename__ = "test_cases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    reference_output: Mapped[str] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=True)  # JSON 数组字符串
    # 代码生成类：{"inputs":[[...],[...]],"expected":[...]}，驱动单元测试通过率
    run_test: Mapped[str] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False, default=now_iso)

    task = relationship("Task", back_populates="cases")
    evals = relationship("EvalResult", back_populates="test_case", cascade="all, delete-orphan")