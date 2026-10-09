# ==========================================================
# 端到端测试：迭代闭环（变体生成→执行→评估→择优→版本→报表）
# 通过 set_mock_client 注入 FakeLLM，无需真实 API Key 即可跑通全链路；
# 另含「停止机制」测试（慢速 LLM + 子线程驱动图，主线程发停止）。
# ==========================================================
import asyncio
import sys
import threading
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests 目录，供 helpers
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend 目录，供 app

import httpx  # noqa: E402

from helpers import auth_headers, login_and_token  # noqa: E402

from app.llm.client import LLMClient  # noqa: E402
from app.main import app  # noqa: E402
from app.services.optimizer_orchestrator import run_iteration_task  # noqa: E402


class _FakeLLM(LLMClient):
    """快速模拟 LLM：变体生成返回固定变体，评审固定 8 分，执行返回固定文本。"""

    def __init__(self):
        super().__init__("http://127.0.0.1:9", "fake")

    async def chat(self, messages, **kwargs):
        return "今天天气很好，我们决定去公园散步，心情非常愉快。"

    async def chat_json(self, messages, **kwargs):
        sys_msg = messages[0]["content"] if messages else ""
        if "提示词工程专家" in sys_msg:
            return {
                "variants": [
                    {"strategy_tag": "rewrite", "prompt": "改进提示词A（注重简洁准确）"},
                    {"strategy_tag": "constraint", "prompt": "改进提示词B（强调忠实原文）"},
                ]
            }
        if "任务评审员" in sys_msg:
            return {"score": 8, "reason": "内容贴切，语言通顺，符合评分标准。"}
        if "提示词撰写专家" in sys_msg:
            return {"prompt": "默认初始提示词。"}
        return {"score": 8, "reason": "合格"}


class _SlowFakeLLM(_FakeLLM):
    """慢速模拟 LLM：执行接口耗时，用于验证停止打断能力。"""

    async def chat(self, messages, **kwargs):
        await asyncio.sleep(1.0)
        return "慢速输出结果。"


def _create_ready_task(client, token, **override):
    """创建任务并添加一条用例，返回 task_id。"""
    h = auth_headers(token)
    payload = {
        "name": f"E2E任务{uuid.uuid4().hex[:6]}",
        "task_type": "summary",
        "description": "文本摘要任务",
        "objective": "忠于原文",
        "criteria": "简洁准确",
        "max_rounds": 2,
        "target_score": 99.0,
        "variants_per_round": 2,
        **override,
    }
    tid = client.post("/api/v1/tasks", json=payload, headers=h).json()["data"]["id"]
    add = client.post(
        f"/api/v1/tasks/{tid}/cases",
        json={"input_text": "今天天气很好我们去公园散步", "reference_output": "今天去公园", "keywords": ["公园"]},
        headers=h,
    ).json()
    assert add["code"] == 0
    return tid, h


async def _start_and_wait(tid, h, rounds=120):
    """async 驱动完整迭代：start 接口内部用 asyncio.create_task 创建后台任务，
    该任务挂在同一事件循环上；通过 await asyncio.sleep 轮询推进循环，
    使后台迭代真正执行到 completed/failed/stopped。返回最终状态。"""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(f"/api/v1/tasks/{tid}/iterations/start", headers=h)
        assert r.json()["code"] == 0
        for _ in range(rounds):
            st = (await ac.get(f"/api/v1/tasks/{tid}", headers=h)).json()["data"]["status"]
            if st in ("completed", "failed", "stopped"):
                return st
            await asyncio.sleep(0.2)
        return "timeout"


class TestIterationE2E:
    def test_full_iteration_loop(self, client):
        """mock LLM 驱动完整迭代，验证变体/评估/得分曲线/版本/抽检/报表。"""
        from app.llm.client import set_mock_client

        set_mock_client(_FakeLLM())
        token = login_and_token(client, f"e2e_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_ready_task(client, token, variants_per_round=2)

        # 1) 启动迭代并等后台任务跑完（后台改为 create_task，需 async 驱动推进）
        final = asyncio.run(_start_and_wait(tid, h))
        assert final == "completed"

        # 2) 任务最终完成
        task = client.get(f"/api/v1/tasks/{tid}", headers=h).json()["data"]
        assert task["status"] == "completed"
        assert task["best_score"] is not None and task["best_score"] > 0
        assert task["best_prompt"]  # 最优提示词已更新

        # 3) 得分曲线应有两轮且有得分
        curve = client.get(f"/api/v1/tasks/{tid}/iterations/1/scores", headers=h).json()["data"]
        assert len(curve["rounds"]) == 2
        assert curve["target_score"] == 99.0

        # 4) 每轮变体数量正确
        vs = client.get(f"/api/v1/tasks/{tid}/iterations/1/variants", headers=h).json()["data"]
        assert len(vs) == 2 and all(v["prompt_text"] for v in vs)

        # 5) 评估结果明细（2变体 × 1用例 = 2 条）
        evals = client.get(
            f"/api/v1/tasks/{tid}/iterations/1/eval-results", headers=h
        ).json()["data"]
        assert evals["total"] == 2

        # 6) 人工抽检评分
        ev = evals["items"][0]
        review = client.post(
            f"/api/v1/tasks/{tid}/eval-results/{ev['id']}/review",
            json={"manual_score": 9, "manual_note": "人工复核通过"},
            headers=h,
        ).json()
        assert review["code"] == 0
        recheck = client.get(
            f"/api/v1/tasks/{tid}/iterations/1/eval-results", headers=h
        ).json()["data"]["items"]
        assert recheck[0]["manual_checked"] == 1
        assert recheck[0]["manual_note"] == "人工复核通过"

        # 7) 版本记录：每轮一条
        versions = client.get(f"/api/v1/tasks/{tid}/versions", headers=h).json()["data"]
        assert len(versions) == 2

        # 8) 版本冻结（action 走 query，前端已对齐）
        frozen = client.post(
            f"/api/v1/tasks/{tid}/versions/{versions[0]['id']}/freeze?action=freeze", headers=h
        ).json()
        assert frozen["code"] == 0

        # 9) 报告导出（md，应返回文本而非 JSON 包装）
        resp = client.get(f"/api/v1/tasks/{tid}/report/export?format=markdown", headers=h)
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers.get("content-type", "")

        # 清理：切断 mock，避免影响后续用例
        set_mock_client(LLMClient("", ""))

    def test_status_reflects_db_when_memory_stale(self, client):
        """回归：任务已完成后，iteration_status 的 task_status 必须以数据库为准，
        即使内存进度快照仍残留 running，也不能覆盖为 running，否则前端无法感知完成。"""
        from app.llm.client import set_mock_client
        from app.core.progress import progress_tracker

        set_mock_client(_FakeLLM())
        token = login_and_token(client, f"stale_{uuid.uuid4().hex[:8]}@a.com")
        # 用低目标分数，保证首轮即达标完成
        tid, h = _create_ready_task(client, token, variants_per_round=2, target_score=1.0)

        asyncio.run(_start_and_wait(tid, h))

        # 任务应已完成
        task = client.get(f"/api/v1/tasks/{tid}", headers=h).json()["data"]
        assert task["status"] == "completed"

        # 模拟最坏情况：内存进度仍残留 running（旧 bug 的来源是内存 running 覆盖数据库）
        progress_tracker.update(tid, status="running")
        stale = client.get(f"/api/v1/tasks/{tid}/iterations/status", headers=h).json()["data"]
        # 修复后：task_status 必须与数据库一致（completed），而非内存残留的 running
        assert stale["task_status"] == "completed", stale
        assert stale["current_best_score"] == task["best_score"]

        set_mock_client(LLMClient("", ""))

    def test_stop_interrupts_running(self, client):
        """慢速 LLM 下发起停止，任务应能被打断并置为 stopped。"""
        from app.llm.client import set_mock_client

        set_mock_client(_SlowFakeLLM())
        token = login_and_token(client, f"stop_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_ready_task(client, token, variants_per_round=2, target_score=99.0)

        # 在子线程中驱动迭代图（避免阻塞测试线程，便于随后调用停止接口）
        errors = []

        def runner():
            try:
                asyncio.run(run_iteration_task(tid, 1))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        th = threading.Thread(target=runner, daemon=True)
        th.start()
        time.sleep(1.5)  # 等待进入 running 并处于慢速执行中

        stop = client.post(f"/api/v1/tasks/{tid}/iterations/stop", headers=h).json()
        assert stop["code"] == 0

        th.join(timeout=20)
        assert not th.is_alive(), "迭代图未能停止退出"
        assert not errors, f"迭代抛异常: {errors}"

        task = client.get(f"/api/v1/tasks/{tid}", headers=h).json()["data"]
        assert task["status"] == "stopped"

        set_mock_client(LLMClient("", ""))