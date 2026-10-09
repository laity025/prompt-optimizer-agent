# ==========================================================
# 数据库基础：声明式 Base、会话工厂、依赖注入 get_db
# ==========================================================
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import get_settings

settings = get_settings()

# 创建引擎；SQLite 需关闭 check_same_thread 以便多线程访问
engine = create_engine(
    settings.database_path,
    connect_args={"check_same_thread": False} if settings.database_path.startswith("sqlite") else {},
)

# 会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def get_db() -> Generator:
    """FastAPI 依赖：每个请求独立数据库会话，结束后自动关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()