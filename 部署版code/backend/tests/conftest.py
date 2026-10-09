# ==========================================================
# pytest 全局配置：隔离数据库 + 注入测试客户端
# 关键：必须在导入 app 之前设置 DATABASE_URL 指向独立临时库，
# 避免污染开发/部署数据库；LLM 由各测试自行注入 mock(set_mock_client)。
# ==========================================================
import os
import pathlib
import sys
import tempfile

# 使 pytest 能从 backend 根目录 import app 包
_BACKEND = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND))

# 独立临时数据库（绝对路径）：conftest 在导入 app 前设置，保证引擎指向临时库
_tmpdir = tempfile.mkdtemp(prefix="prompt_opt_test_")
os.environ["DATABASE_URL"] = f"sqlite:///{(pathlib.Path(_tmpdir) / 'test.db').as_posix()}"
os.environ["LLM_BASE_URL"] = ""
os.environ["LLM_API_KEY"] = ""

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db.base import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _init_tables():
    """会话级：建表（业务初始化数据由各测试自行构造，不运行 init_db）。"""
    Base.metadata.create_all(engine)
    yield
    engine.dispose()


@pytest.fixture()
def client():
    """提供一个隔离的 API 测试客户端实例。"""
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_llm_mock():
    """每个测试结束后重置全局 LLM client，避免 E2E 注入的 FakeLLM 泄漏到后续用例。"""
    yield
    from app.llm.client import LLMClient, set_mock_client

    set_mock_client(LLMClient("", ""))