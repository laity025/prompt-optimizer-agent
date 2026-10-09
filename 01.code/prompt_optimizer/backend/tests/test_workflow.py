# ==========================================================
# 多步工作流评测测试：占位符插值 / 链式执行 / 末步评测 / 基线对照 / CRUD / 权限
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


class _WorkflowFakeLLM(LLMClient):
    """按步骤指令返回可预测输出，验证链式变量传递与末步评测。"""

    def __init__(self):
        super().__init__("http://127.0.0.1:9", "fake")

    async def chat(self, messages, **kwargs):
        user = messages[-1]["content"]
        if "请转写：" in user:
            marker = "优化" if "更精准" in user else "原始"
            return f"{marker}转写结果:" + user.split("请转写：", 1)[1]
        if "请润色：" in user:
            return "润色版【" + user.split("请润色：", 1)[1] + "】"
        if "请对输入进行简洁准确" in user:
            return "基线摘要输出"
        return "通用步骤输出"

    async def chat_json(self, messages, **kwargs):
        # 区分走 judge（含【模型输出】与评分）与变体生成（含【改进提示词变体】）
        user = messages[-1]["content"]
        if "改进提示词变体" in user:
            # 返回一个"优化版"变体：含"更精准"标记，其链式最终输出会被评出更高分
            return [{"strategy_tag": "rewrite", "prompt": "请转写（更精准的指令）：{{input}}"}]
        # 评分：输出含"优化"字样给更高分，用于触发优化提升判定
        if "原始转写结果" in user:
            return {"score": 5, "reason": "原始输出一般。"}
        return {"score": 9, "reason": "优化输出更精准。"}


class _StepOptFakeLLM(LLMClient):
    """步骤优化专用假模型：
      chat          按指令中是否含「更精准」返回「优化/原始转写结果」，供链式传递；
      chat_json      一变体生成：返回含「更精准的指令」的优化变体；
                    二评审：按末步输出是否含「优化转写结果」给 9 分，否则（原始）给 5 分，
                    从而让变体整链平均分高于基准整链分，触发 improved=1 与步骤回写。
    """

    def __init__(self):
        super().__init__("http://127.0.0.1:9", "fake")

    async def chat(self, messages, **kwargs):
        user = messages[-1]["content"]
        if "请转写：" in user:
            marker = "优化" if "更精准" in user else "原始"
            return f"{marker}转写结果:" + user.split("请转写：", 1)[1]
        if "请润色：" in user:
            return "润色版【" + user.split("请润色：", 1)[1] + "】"
        return "通用步骤输出"

    async def chat_json(self, messages, **kwargs):
        # 「改进提示词变体」出现在变体生成请求的 system 消息里，需扫描全部消息内容
        full = " ".join(m.get("content", "") for m in messages)
        if "改进提示词变体" in full:
            return [{"strategy_tag": "rewrite", "prompt": "请转写（更精准的指令）：{{input}}"}]
        if "优化转写结果" in full:
            return {"score": 9, "reason": "优化变体整链输出更精准。"}
        if "原始转写结果" in full:
            return {"score": 5, "reason": "原始步骤输出一般。"}
        return {"score": 7, "reason": "中间分。"}


class _StagnantFakeLLM(LLMClient):
    """滞涨场景假模型：变体与基准相同（去重后仅剩基准），每轮整链分无提升。

    同时记录第 2 轮起变体生成请求是否携带上一轮失败案例反馈（验证优化器反馈回路）。
    """

    def __init__(self):
        super().__init__("http://127.0.0.1:9", "fake")
        self.saw_fail_cases = False  # 是否收到过失败案例反馈

    async def chat(self, messages, **kwargs):
        user = messages[-1]["content"]
        if "请转写：" in user:
            return "原始转写结果:" + user.split("请转写：", 1)[1]
        if "请润色：" in user:
            return "润色版【" + user.split("请润色：", 1)[1] + "】"
        return "通用步骤输出"

    async def chat_json(self, messages, **kwargs):
        full = " ".join(m.get("content", "") for m in messages)
        if "改进提示词变体" in full:
            if "失败案例" in full:
                self.saw_fail_cases = True
            # 返回与基准完全相同的变体 → 相似度去重后仅剩基准，整链分恒等于基准
            return [{"strategy_tag": "rewrite", "prompt": "请转写：{{input}}"}]
        if "原始转写结果" in full:
            return {"score": 5, "reason": "原始输出一般。"}
        return {"score": 5, "reason": "一般。"}


def _create_wf_task(client, token):
    h = auth_headers(token)
    payload = {
        "name": f"工作流任务{uuid.uuid4().hex[:6]}", "task_type": "summary",
        "description": "d", "objective": "o", "criteria": "c",
        "initial_prompt": "请对输入进行简洁准确的摘要。", "max_rounds": 1,
    }
    tid = client.post("/api/v1/tasks", json=payload, headers=h).json()["data"]["id"]
    add = client.post(f"/api/v1/tasks/{tid}/cases",
                      json={"input_text": "今天阳光灿烂，适合出行", "reference_output": "晴天适合出行"},
                      headers=h).json()
    assert add["code"] == 0
    return tid, h


def _mk_workflow(client, tid, h, steps=None):
    if steps is None:
        steps = [
            {"name": "转写", "prompt_template": "请转写：{{input}}", "output_var": "t"},
            {"name": "润色", "prompt_template": "请润色：{{step1.out}}", "output_var": "p"},
        ]
    resp = client.post(f"/api/v1/tasks/{tid}/workflows",
                       json={"name": "两步工作流", "description": "测试", "steps": steps},
                       headers=h).json()
    assert resp["code"] == 0, resp
    return resp["data"]["id"]


async def _wait_run(tid, wf_id, run_id, h, rounds=120):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(rounds):
            r = (await ac.get(
                f"/api/v1/tasks/{tid}/workflows/{wf_id}/runs/{run_id}",
                headers=h)).json()["data"]
            if r["run"]["status"] in ("completed", "failed"):
                return r
            await asyncio.sleep(0.2)
        return None


async def _wait_opt(tid, wf_id, opt_id, h, rounds=120):
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(rounds):
            r = (await ac.get(
                f"/api/v1/tasks/{tid}/workflows/{wf_id}/optimizations/{opt_id}",
                headers=h)).json()["data"]
            if r["opt"]["status"] in ("completed", "failed"):
                return r
            await asyncio.sleep(0.2)
        return None


class TestWorkflow:
    def test_chain_execution_and_evaluate(self, client):
        """两步骤链式执行：末步输出复用了上步结果，并完成评测 + 基线对照。"""
        from app.llm.client import set_mock_client

        set_mock_client(_WorkflowFakeLLM())
        token = login_and_token(client, f"wf_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)
        wf_id = _mk_workflow(client, tid, h)

        start = client.post(f"/api/v1/tasks/{tid}/workflows/{wf_id}/run",
                            json={"run_baseline": True}, headers=h).json()
        assert start["code"] == 0
        run_id = start["data"]["run_id"]

        report = asyncio.run(_wait_run(tid, wf_id, run_id, h))
        assert report is not None, "工作流评测超时未完成"
        assert report["run"]["status"] == "completed"

        # 链式传递：step2.input=step1.out，末步输出应包含两个步骤的痕迹
        case = report["cases"][0]
        assert "今天阳光灿烂" in case["final_output"]
        assert "转写结果" in case["final_output"]
        assert "润色版" in case["final_output"]
        assert len(case["step_trace"]) == 2
        # 末步评测得分与基线对照
        assert case["total_score"] and case["total_score"] > 0
        assert case["baseline_output"] == "基线摘要输出"
        assert case["baseline_score"] and case["baseline_score"] > 0
        # 平均分汇总
        assert report["run"]["avg_score"] and report["run"]["avg_score"] > 0
        assert report["run"]["baseline_avg_score"] and report["run"]["baseline_avg_score"] > 0

        # 运行历史可查
        runs = client.get(f"/api/v1/tasks/{tid}/workflows/{wf_id}/runs", headers=h).json()["data"]
        assert runs["total"] == 1 and runs["items"][0]["status"] == "completed"

        set_mock_client(LLMClient("", ""))

    def test_run_without_baseline(self, client):
        """run_baseline=false 时不产基线对照，final_output 正常。"""
        from app.llm.client import set_mock_client

        set_mock_client(_WorkflowFakeLLM())
        token = login_and_token(client, f"wfn_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)
        wf_id = _mk_workflow(client, tid, h)

        start = client.post(f"/api/v1/tasks/{tid}/workflows/{wf_id}/run",
                            json={"run_baseline": False}, headers=h).json()
        report = asyncio.run(_wait_run(tid, wf_id, start["data"]["run_id"], h))
        assert report["run"]["status"] == "completed"
        assert report["run"]["baseline_avg_score"] is None
        assert report["cases"][0]["baseline_score"] is None
        set_mock_client(LLMClient("", ""))

    def test_run_requires_steps(self, client):
        """空步骤的工作流（无有效步骤）在创建时即被拒绝。"""
        from app.llm.client import set_mock_client

        set_mock_client(_WorkflowFakeLLM())
        token = login_and_token(client, f"wfe_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)
        resp = client.post(f"/api/v1/tasks/{tid}/workflows",
                           json={"name": "空工作流", "steps": []}, headers=h).json()
        assert resp["code"] != 0, resp
        set_mock_client(LLMClient("", ""))

    def test_blank_template_steps_rejected(self, client):
        """空白指令模板的步骤在创建/更新时应被后端拒绝。"""
        from app.llm.client import set_mock_client

        set_mock_client(_WorkflowFakeLLM())
        token = login_and_token(client, f"wfbt_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)

        # 创建时含空白模板步骤 → 拒绝
        bad_create = client.post(f"/api/v1/tasks/{tid}/workflows",
                                 json={"name": "空模板", "steps": [
                                     {"name": "a", "prompt_template": "处理：{{input}}"},
                                     {"name": "b", "prompt_template": "   "},
                                 ]}, headers=h).json()
        assert bad_create["code"] != 0

        # 全空白 → 拒绝
        wf_id = _mk_workflow(client, tid, h)
        bad_update = client.put(f"/api/v1/tasks/{tid}/workflows/{wf_id}",
                                json={"steps": [{"name": "x", "prompt_template": "  \n "}]},
                                headers=h).json()
        assert bad_update["code"] != 0
        set_mock_client(LLMClient("", ""))

    def test_workflow_crud(self, client):
        """工作流 增查改删 全链路，更新可整体替换步骤。"""
        from app.llm.client import set_mock_client

        set_mock_client(_WorkflowFakeLLM())
        token = login_and_token(client, f"wfc_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)
        wf_id = _mk_workflow(client, tid, h)

        # 详情含步骤
        det = client.get(f"/api/v1/tasks/{tid}/workflows/{wf_id}", headers=h).json()["data"]
        assert det["step_count"] == 2 and det["steps"][0]["seq"] == 1

        # 整体替换为1步
        upd = client.put(f"/api/v1/tasks/{tid}/workflows/{wf_id}",
                         json={"name": "改", "steps": [
                             {"name": "单步", "prompt_template": "处理：{{input}}"},
                         ]}, headers=h).json()
        assert upd["code"] == 0
        assert upd["data"]["name"] == "改" and upd["data"]["step_count"] == 1

        # 删除
        rm = client.delete(f"/api/v1/tasks/{tid}/workflows/{wf_id}", headers=h).json()
        assert rm["code"] == 0
        after = client.get(f"/api/v1/tasks/{tid}/workflows", headers=h).json()["data"]
        assert after["total"] == 0
        set_mock_client(LLMClient("", ""))

    def test_workflow_ownership_isolation(self, client):
        """他人任务下的工作流不可跨任务访问。"""
        from app.llm.client import set_mock_client

        set_mock_client(_WorkflowFakeLLM())
        a = login_and_token(client, f"wfa_{uuid.uuid4().hex[:8]}@a.com")
        b = login_and_token(client, f"wfb_{uuid.uuid4().hex[:8]}@b.com")
        tid, ha = _create_wf_task(client, a)
        wf_id = _mk_workflow(client, tid, ha)
        # B 访问 A 工作流被拒
        res = client.get(f"/api/v1/tasks/{tid}/workflows/{wf_id}", headers=auth_headers(b)).json()
        assert res["code"] != 0
        # B 不在其任务下创建/访问
        bad = client.get(f"/api/v1/tasks/999999/workflows/{wf_id}", headers=auth_headers(a)).json()
        assert bad["code"] != 0
        set_mock_client(LLMClient("", ""))

    def test_step_optimization(self, client):
        """步骤自动迭代优化闭环：变体生成 → 整链评测 → 择优回写步骤 prompt。"""
        from app.llm.client import set_mock_client

        set_mock_client(_StepOptFakeLLM())
        token = login_and_token(client, f"wfopt_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)
        wf_id = _mk_workflow(client, tid, h)

        # 启动对 Step 1 的优化（异步）
        start = client.post(f"/api/v1/tasks/{tid}/workflows/{wf_id}/steps/1/optimize",
                            json={"max_rounds": 1}, headers=h).json()
        assert start["code"] == 0, start
        opt_id = start["data"]["opt_id"]

        # 轮询至优化完成
        report = asyncio.run(_wait_opt(tid, wf_id, opt_id, h))
        assert report is not None, "步骤优化超时未完成"
        assert report["opt"]["status"] == "completed"
        # 优化变体整链分更高 → 判定已提升
        assert report["opt"]["improved"] == 1
        assert report["opt"]["best_score"] > report["opt"]["base_score"]
        assert "更精准" in report["opt"]["best_prompt"]
        # 变体明细落库且标记本轮最优
        assert any(v["is_best"] == 1 for v in report["variants"])

        # 步骤 prompt 已回写
        wf = client.get(f"/api/v1/tasks/{tid}/workflows/{wf_id}", headers=h).json()["data"]
        step1 = next(s for s in wf["steps"] if s["seq"] == 1)
        assert "更精准" in step1["prompt_template"]

        # 历史可查
        opts = client.get(f"/api/v1/tasks/{tid}/workflows/{wf_id}/optimizations",
                          headers=h).json()["data"]
        assert opts["total"] >= 1 and opts["items"][0]["id"] == opt_id
        set_mock_client(LLMClient("", ""))

    def test_step_optimization_requires_step(self, client):
        """不存在/空模板的目标步骤应被拒绝。"""
        from app.llm.client import set_mock_client

        set_mock_client(_StepOptFakeLLM())
        token = login_and_token(client, f"wfopt2_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)
        wf_id = _mk_workflow(client, tid, h)
        # seq=9 不存在
        bad = client.post(f"/api/v1/tasks/{tid}/workflows/{wf_id}/steps/9/optimize",
                          json={"max_rounds": 1}, headers=h).json()
        assert bad["code"] != 0
        # 他人不可访问
        b = login_and_token(client, f"wfopt3_{uuid.uuid4().hex[:8]}@b.com")
        res = client.post(f"/api/v1/tasks/{tid}/workflows/{wf_id}/steps/1/optimize",
                          json={"max_rounds": 1}, headers=auth_headers(b)).json()
        assert res["code"] != 0
        set_mock_client(LLMClient("", ""))

    def test_step_optimization_stagnation(self, client):
        """连续两轮无提升应提前终止（current_round < max_rounds），improved=0，失败案例反馈闭环。"""
        from app.llm.client import set_mock_client

        fake = _StagnantFakeLLM()
        set_mock_client(fake)
        token = login_and_token(client, f"wfst_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _create_wf_task(client, token)
        wf_id = _mk_workflow(client, tid, h)

        start = client.post(f"/api/v1/tasks/{tid}/workflows/{wf_id}/steps/1/optimize",
                            json={"max_rounds": 5}, headers=h).json()
        assert start["code"] == 0
        report = asyncio.run(_wait_opt(tid, wf_id, start["data"]["opt_id"], h))
        assert report["opt"]["status"] == "completed"
        assert report["opt"]["improved"] == 0
        # 连续 2 轮滞涨提前终止：只跑了 2 轮（而非请求的 5 轮）
        assert report["opt"]["current_round"] == 2
        # 未提升时报告回填基准值，而非 None
        assert report["opt"]["best_score"] == report["opt"]["base_score"]
        assert report["opt"]["best_prompt"] == report["opt"]["base_prompt"]
        # 第 2 轮变体生成已携带上一轮失败案例反馈（生成请求含「失败案例」）
        assert fake.saw_fail_cases
        set_mock_client(LLMClient("", ""))