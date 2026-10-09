# ==========================================================
# 在线服务测试：创建/列表/调用(api_key)/日志/统计/轮换密钥/停用/属主隔离
# ==========================================================
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import auth_headers, login_and_token  # noqa: E402

from app.llm.client import LLMClient, set_mock_client  # noqa: E402


class _OnlineFakeLLM(LLMClient):
    """mock 执行器：固定返回一段文本，用于验证在线调用链路。"""

    def __init__(self):
        super().__init__("http://127.0.0.1:9", "fake")

    async def chat(self, messages, **kwargs):
        return "这是一个来自在线服务的处理结果。"

    async def chat_json(self, messages, **kwargs):
        return {"score": 8, "reason": "ok"}


def _make_task(client, token, prompt="请对输入做简洁摘要。"):
    payload = {
        "name": f"在线任务{uuid.uuid4().hex[:6]}",
        "task_type": "summary",
        "description": "摘要",
        "objective": "忠于原文",
        "criteria": "简洁",
        "initial_prompt": prompt,
    }
    return client.post("/api/v1/tasks", json=payload, headers=auth_headers(token))\
        .json()["data"]["id"]


class TestOnlineService:
    def test_full_lifecycle(self, client):
        """创建→调用→日志→统计→轮换密钥→停用→删除 全生命周期。"""
        set_mock_client(_OnlineFakeLLM())
        token = login_and_token(client, f"ol_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        tid = _make_task(client, token)

        # 1) 创建在线服务
        ep = client.post("/api/v1/endpoints", json={
            "task_id": tid, "name": "我的摘要服务", "model": "modelA",
        }, headers=h).json()
        assert ep["code"] == 0
        eid = ep["data"]["id"]
        key = ep["data"]["api_key"]
        assert key.startswith("sk-")

        # 2) 列表可查到
        lst = client.get("/api/v1/endpoints", headers=h).json()["data"]
        assert any(i["id"] == eid for i in lst["items"])

        # 3) 正确密钥可调用，返回输出
        inv = client.post(f"/api/v1/endpoints/{eid}/invoke",
                          json={"input": "今天天气很好"}, headers={"X-Api-Key": key}).json()
        assert inv["code"] == 0
        assert "在线服务" in inv["data"]["output"]

        # 4) 错误/缺失密钥被拒（401）
        bad = client.post(f"/api/v1/endpoints/{eid}/invoke",
                          json={"input": "x"}, headers={"X-Api-Key": "sk-wrong"}).json()
        assert bad["code"] == 401

        # 5) 日志与统计
        logs = client.get(f"/api/v1/endpoints/{eid}/logs", headers=h).json()["data"]
        assert logs["total"] == 1 and logs["items"][0]["status"] == "success"
        stats = client.get(f"/api/v1/endpoints/{eid}/stats", headers=h).json()["data"]
        assert stats["success"] == 1 and stats["call_count"] == 1

        # 6) 轮换密钥：旧密钥失效，新密钥生效
        newkey = client.post(f"/api/v1/endpoints/{eid}/rotate-key", headers=h).json()["data"]["api_key"]
        assert newkey != key
        old = client.post(f"/api/v1/endpoints/{eid}/invoke",
                          json={"input": "x"}, headers={"X-Api-Key": key}).json()
        assert old["code"] == 401
        new_ok = client.post(f"/api/v1/endpoints/{eid}/invoke",
                             json={"input": "x"}, headers={"X-Api-Key": newkey}).json()
        assert new_ok["code"] == 0

        # 7) 停用后不可调用
        client.put(f"/api/v1/endpoints/{eid}", json={"active": 0}, headers=h)
        disabled = client.post(f"/api/v1/endpoints/{eid}/invoke",
                               json={"input": "x"}, headers={"X-Api-Key": newkey}).json()
        assert disabled["code"] != 0

        # 8) 删除
        rm = client.delete(f"/api/v1/endpoints/{eid}", headers=h).json()
        assert rm["code"] == 0
        g = client.get(f"/api/v1/endpoints/{eid}", headers=h).json()
        assert g["code"] != 0

        set_mock_client(LLMClient("", ""))

    def test_ownership_isolation(self, client):
        """属主隔离：他人不可访问我的在线服务。"""
        set_mock_client(_OnlineFakeLLM())
        a = login_and_token(client, f"oa_{uuid.uuid4().hex[:8]}@a.com")
        b = login_and_token(client, f"ob_{uuid.uuid4().hex[:8]}@a.com")
        tid = _make_task(client, a)
        ep = client.post("/api/v1/endpoints", json={"task_id": tid, "model": "modelA"},
                         headers=auth_headers(a)).json()
        eid = ep["data"]["id"]

        # B 用户访问 A 的端点应被拒绝
        res = client.get(f"/api/v1/endpoints/{eid}", headers=auth_headers(b)).json()
        assert res["code"] != 0
        set_mock_client(LLMClient("", ""))