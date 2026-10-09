# ==========================================================
# 知识库（RAG 检索评测）测试：
#   chunk_text / 建库 / 上传语料 / 检索 / 评测(来源支撑度+忠实度)
#   属主隔离 / 任务绑定 RAG / execute_cases 上下文注入
# ==========================================================
import asyncio
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import auth_headers, login_and_token  # noqa: E402

from app.llm.client import LLMClient, set_mock_client  # noqa: E402
from app.services import rag_service  # noqa: E402


class _RagFakeLLM(LLMClient):
    """mock 执行器/评审：返回固定答案与忠实度打分。"""

    def __init__(self):
        super().__init__("http://127.0.0.1:9", "fake")
        self.last_messages: list | None = None

    async def chat(self, messages, **kwargs):
        self.last_messages = messages
        return "平台采用前后端分离架构，前端使用 React 与 Vite，后端使用 FastAPI。"

    async def chat_json(self, messages, **kwargs):
        return {"score": 88, "reason": "忠实于检索到的知识库上下文"}


def _make_kb(client, token, name="我的知识库"):
    return client.post("/api/v1/knowledge-bases",
                       json={"name": name, "description": "测试"},
                       headers=auth_headers(token)).json()["data"]


def _corpus():
    return "本项目采用前后端分离架构。\n\n" \
           "前端技术栈为 React 18、TypeScript、Vite 与 Ant Design 5。\n\n" \
           "后端技术栈为 FastAPI、SQLAlchemy 2.0 与 SQL Server。\n\n" \
           "系统支持提示词迭代优化与多模型对比评测。"


class TestChunk:
    def test_chunk_text_splits_long_content(self):
        text = "一。" * 3000  # 超长文本
        chunks = rag_service.chunk_text(text)
        assert len(chunks) >= 2
        assert all(c for c in chunks)
        # 每块长度不超过 size，加上尾部与下一块的重叠部分
        assert all(len(c) <= 512 + 60 + 10 for c in chunks)

    def test_chunk_text_short_single(self):
        chunks = rag_service.chunk_text("很短内容", size=512)
        assert chunks == ["很短内容"]

    def test_empty_returns_empty(self):
        assert rag_service.chunk_text("   ") == []


class TestKbLifecycle:
    def test_create_add_retrieve_evaluate(self, client):
        set_mock_client(_RagFakeLLM())
        token = login_and_token(client, f"rag_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)

        # 1) 建库
        kb = _make_kb(client, token)
        kb_id = kb["id"]

        # 2) 上传语料 → 生成块
        doc = client.post(f"/api/v1/knowledge-bases/{kb_id}/docs",
                          json={"title": "架构说明", "content": _corpus()},
                          headers=h).json()
        assert doc["code"] == 0 and doc["data"]["chunk_count"] >= 1

        # 列表/详情可见
        lst = client.get("/api/v1/knowledge-bases", headers=h).json()["data"]
        assert any(i["id"] == kb_id for i in lst["items"])
        detail = client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=h).json()["data"]
        assert detail["doc_count"] == 1 and len(detail["docs"]) == 1

        # 3) 检索预览能命中相关块
        ret = client.post(f"/api/v1/knowledge-bases/{kb_id}/retrieve",
                          json={"query": "前端使用什么技术栈？", "top_k": 3},
                          headers=h).json()
        assert ret["code"] == 0
        hits = ret["data"]["hits"]
        assert len(hits) >= 1
        assert any("React" in hit["text"] for hit in hits)

        # 4) RAG 评测：答案 + 来源支撑度 + 忠实度
        ev = client.post(f"/api/v1/knowledge-bases/{kb_id}/evaluate",
                         json={"query": "整体架构是怎样的？", "top_k": 3},
                         headers=h).json()
        assert ev["code"] == 0
        data = ev["data"]
        assert data["answer"]
        assert isinstance(data["source_score"], float)
        assert data["faithfulness"]["score"] >= 0
        assert data["retrieved"]

        # 5) 删除
        rm = client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=h).json()
        assert rm["code"] == 0
        set_mock_client(LLMClient("", ""))

    def test_kb_ownership_isolation(self, client):
        set_mock_client(_RagFakeLLM())
        a = login_and_token(client, f"rk_{uuid.uuid4().hex[:8]}@a.com")
        b = login_and_token(client, f"rk_{uuid.uuid4().hex[:8]}@b.com")
        kb = _make_kb(client, a)
        kb_id = kb["id"]
        # B 访问 A 的库被拒
        res = client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=auth_headers(b)).json()
        assert res["code"] != 0
        # 空库检索返回状态错误
        ret = client.post(f"/api/v1/knowledge-bases/{kb_id}/retrieve",
                          json={"query": "x"}, headers=auth_headers(a)).json()
        assert ret["code"] == 0 and ret["data"]["hits"] == []
        set_mock_client(LLMClient("", ""))

    def test_source_support(self):
        ctx = "平台采用前后端分离架构，前端 React，后端 FastAPI。"
        assert rag_service.source_support("采用前后端分离架构", ctx) > 0
        assert rag_service.source_support("毫无关系的另一话题内容", ctx) < \
            rag_service.source_support("采用前后端分离架构", ctx)


class TestTaskRagBinding:
    def test_task_bind_kb_and_inject_context(self, client):
        """任务开启 RAG 并绑定知识库后，execute_cases 会给用例注入检索上下文。"""
        fake = _RagFakeLLM()
        set_mock_client(fake)
        token = login_and_token(client, f"tb_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        kb_id = _make_kb(client, token)["id"]
        client.post(f"/api/v1/knowledge-bases/{kb_id}/docs",
                    json={"title": "T", "content": _corpus()}, headers=h)

        tid = client.post("/api/v1/tasks", json={
            "name": "RAG任务", "task_type": "summary", "description": "d",
            "objective": "o", "criteria": "c", "initial_prompt": "请依据知识库做摘要",
            "kb_id": kb_id, "enable_rag": 1,
        }, headers=h).json()["data"]["id"]

        # 加载任务 ORM 后执行
        from app.db.base import SessionLocal
        from app.models import Task
        from app.services.executor import execute_cases

        s = SessionLocal()
        try:
            task = s.get(Task, tid)
            results = asyncio.run(execute_cases(
                prompt=task.initial_prompt,
                inputs=[{"case_id": 1, "input_text": "前端技术栈是什么？"}],
                task=task, concurrency=1,
            ))
        finally:
            s.close()

        assert results[0]["error_reason"] == ""
        assert "【检索到的知识库上下文】" in fake.last_messages[1]["content"]
        set_mock_client(LLMClient("", ""))

    def test_task_bind_others_kb_rejected(self, client):
        a = login_and_token(client, f"tj_{uuid.uuid4().hex[:8]}@a.com")
        b = login_and_token(client, f"tj_{uuid.uuid4().hex[:8]}@b.com")
        kb_id = _make_kb(client, a)["id"]
        # B 用自己的 token 绑定 A 的知识库应被拒
        res = client.post("/api/v1/tasks", json={
            "name": "t", "task_type": "summary", "description": "d",
            "objective": "o", "criteria": "c", "kb_id": kb_id, "enable_rag": 1,
        }, headers=auth_headers(b)).json()
        assert res["code"] != 0

    def test_delete_kb_unbinds_tasks(self, client):
        """删除被任务绑定的知识库后，任务应被解绑且 RAG 开关关闭。"""
        token = login_and_token(client, f"du_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        kb_id = _make_kb(client, token)["id"]
        tid = client.post("/api/v1/tasks", json={
            "name": "UB", "task_type": "summary", "description": "d",
            "objective": "o", "criteria": "c", "kb_id": kb_id, "enable_rag": 1,
        }, headers=h).json()["data"]["id"]

        assert client.delete(f"/api/v1/knowledge-bases/{kb_id}", headers=h).json()["code"] == 0

        from app.db.base import SessionLocal
        from app.models import Task

        s = SessionLocal()
        try:
            t = s.get(Task, tid)
            assert t.kb_id is None and t.enable_rag == 0
        finally:
            s.close()

    def test_concurrent_uploads_no_lost_count(self, client):
        """多篇文档上传到同一库，doc_count/chunk_count 采用原子累加不丢。"""
        token = login_and_token(client, f"cc_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        kb_id = _make_kb(client, token)["id"]

        # 连续上传 5 篇：计数必须精确累加到 5，不能出现丢失/覆盖
        for _ in range(5):
            resp = client.post(f"/api/v1/knowledge-bases/{kb_id}/docs",
                               json={"title": "C", "content": _corpus()}, headers=h).json()
            assert resp["code"] == 0

        detail = client.get(f"/api/v1/knowledge-bases/{kb_id}", headers=h).json()["data"]
        assert detail["doc_count"] == 5
        assert detail["chunk_count"] >= 5