# ==========================================================
# 数据库初始化：建表（开发期用 create_all，生产建议 Alembic）
# ==========================================================
from app.db.base import Base, engine
from app import models  # noqa: F401  确保模型已注册


def init_db() -> None:
    """创建所有数据表。幂等操作，可重复调用。"""
    Base.metadata.create_all(bind=engine)