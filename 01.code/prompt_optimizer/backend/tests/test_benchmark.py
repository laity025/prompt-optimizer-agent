# ==========================================================
# 多模型对比评测测试：mock LLM 返回按模型区分的输出，
# 验证 start/异步完成/最优模型判定/best_score/矩阵/导出
# ==========================================================
import asyncio
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402

from helpers import auth_headers, login_and_token  # noqa: E402

from app.llm.client import LLMClient  # noqa: E402
from app.main import app  # noqa: E402


class _BenchFakeLLM(LLMClient):
    """按渲染模型返回不同输出，使两模型在对比评测中产生可区分的得分差异。"""

    def __init__(self):
        super().__init__("http://127.0.0.1:9", "fake")

    async def chat(self, messages, **kwargs):
        model = kwargs.get("model") or ""
        if "modelA" in model:
            return "模型A的输出：公园里有松鼠和鸟。"
        if "modelB" in model:
            return "模型B更完整的输出：公园里有松鼠和鸟，环境十分优美宜人。"
        return "通用输出"

    async def chat_json(self, messages, **kwargs):
        return {"score": 8, "reason": "内容贴切，符合标准。"}


def _create_bench_task(client, token):
    h = auth_headers(token)
    payload = {
        "name": f"评测任务{uuid.uuid4().hex[:6]}",
        "task_type": "summary",
        "description": "文本摘要任务",
        "objective": "忠于原文",
        "criteria": "简洁准确",
        "initial_prompt": "请对输入进行简洁准确的摘要。",
        "max_rounds": 1,
    }
    tid = client.post("/api/v1/tasks", json=payload, headers=h).json()["data"]["id"]
    add = client.post(
        f"/api/v1/tasks/{tid}/cases",
        json={"input_text": "今天天气很好，我们在公园散步", "reference_output": "今天在公园散步"},
        headers=h,
    ).json()
    assert add["code"] == 0
    return tid, h


async def _wait_benchmark(tid, run_id, h, rounds=120):
    """async 驱动后台评测任务实际执行完（start 用 create_task，需同一事件循环推进）。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(rounds):
            r = (await ac.get(f"/api/v1/tasks/{tid}/benchmarks/{run_id}", headers=h)).json()["data"]
            if r["run"]["status"] in ("completed", "failed"):
                return r
            await asyncio.sleep(0.2)
        return None


class TestBenchmark:
    def test_multi_model_compare(self, client):
        """两模型对比评测：后端成功执行并产出最优模型与得分矩阵。"""
        from app.llm.client import set_mock_client

        set_mock_client(_BenchFakeLLM())
        token = login_and_token(client, f"bench_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_bench_task(client, token)

        # 1) 发起评测
        start = client.post(
            f"/api/v1/tasks/{tid}/benchmarks/start",
            json={"models": ["modelA", "modelB"], "prompt_mode": "best", "name": "AB对比"},
            headers=h,
        ).json()
        assert start["code"] == 0
        run_id = start["data"]["run_id"]

        # 2) 等待后台评测完成
        report = asyncio.run(_wait_benchmark(tid, run_id, h))
        assert report is not None, "评测超时未完成"
        assert report["run"]["status"] == "completed"
        assert report["run"]["best_model"] in ("modelA", "modelB")
        assert report["run"]["best_score"] and report["run"]["best_score"] > 0

        # 3) 对比矩阵：两个模型 × 1 用例，每格都有得分
        assert report["models_order"] == ["modelA", "modelB"]
        assert len(report["models"]) == 2
        assert all(m["avg_score"] is not None and m["avg_score"] > 0 for m in report["models"])
        assert len(report["matrix"]) == 1
        assert len(report["matrix"][0]["models"]) == 2
        assert all(c["score"] is not None for c in report["matrix"][0]["models"])

        # 4) 历史列表能查到本次评测
        lst = client.get(f"/api/v1/tasks/{tid}/benchmarks", headers=h).json()["data"]
        assert lst["total"] == 1 and lst["items"][0]["status"] == "completed"

        # 5) 导出报告为 markdown 文本
        resp = client.get(f"/api/v1/tasks/{tid}/benchmarks/{run_id}/report", headers=h)
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")

        set_mock_client(LLMClient("", ""))

    def test_start_requires_models(self, client):
        """未选模型应被拒绝。"""
        from app.llm.client import set_mock_client

        set_mock_client(_BenchFakeLLM())
        token = login_and_token(client, f"bnm_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_bench_task(client, token)
        resp = client.post(
            f"/api/v1/tasks/{tid}/benchmarks/start",
            json={"models": [], "prompt_mode": "best"},
            headers=h,
        ).json()
        assert resp["code"] != 0
        set_mock_client(LLMClient("", ""))