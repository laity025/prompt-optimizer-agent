# ==========================================================
# 应用配置模块：集中管理环境变量与默认参数
# ==========================================================
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """全局配置，从 .env / 环境变量读取。"""

    # 项目标识
    APP_NAME: str = "提示词自动迭代优化智能体"
    APP_VERSION: str = "1.0.0"
    API_V1_PREFIX: str = "/api/v1"

    # JWT 配置
    JWT_SECRET_KEY: str = "change-me-to-a-long-random-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440

    # 登录态 Cookie 配置
    # 本机/内网 HTTP 部署保持 False；公网 HTTPS 生产环境置 True（浏览器仅经 HTTPS 传输 cookie）
    COOKIE_SECURE: bool = False

    # 数据库：默认取 backend 目录下的 sqlite 文件
    DATABASE_URL: str = "sqlite:///./prompt_optimizer.db"

    # LLM API（OpenAI 兼容）
    LLM_BASE_URL: str = ""
    LLM_API_KEY: str = ""
    LLM_DEFAULT_MODEL: str = "qwen-plus"

    # 迭代执行超时与重试
    EXEC_TIMEOUT_SECONDS: int = 60
    EXEC_MAX_RETRIES: int = 2
    VARIANT_GEN_TEMPERATURE: float = 0.8

    # 默认迭代参数（任务未指定时使用）
    DEFAULT_TARGET_SCORE: float = 85.0
    DEFAULT_MAX_ROUNDS: int = 10
    DEFAULT_VARIANTS_PER_ROUND: int = 4
    DEFAULT_CONCURRENCY: int = 2
    DEFAULT_STAGNANT_ROUNDS: int = 3

    # RAG 检索增强
    # 嵌入模型名；留空则启用本地词法检索（无需外部依赖）。形如 BAAI/bge-m3
    EMBED_MODEL: str = ""
    # 一键导入示例语料库目录（绝对路径，可为空）
    RAG_CORPUS_DIR: str = ""
    # 评测执行时默认注入的检索块数
    RAG_EVAL_TOP_K: int = 4

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    @property
    def base_dir(self) -> Path:
        """backend 目录绝对路径，用于拼接相对路径。"""
        return Path(__file__).resolve().parent.parent

    @property
    def database_path(self) -> str:
        """将相对 sqlite 路径转为 backend 目录下的绝对路径。"""
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw = self.DATABASE_URL.replace("sqlite:///", "", 1)
            if not Path(raw).is_absolute():
                return f"sqlite:///{(self.base_dir / raw).as_posix()}"
        return self.DATABASE_URL


@lru_cache
def get_settings() -> Settings:
    """缓存单例配置对象。"""
    return Settings()