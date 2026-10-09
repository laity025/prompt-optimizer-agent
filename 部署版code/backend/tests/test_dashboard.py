# ==========================================================
# 资产管理门户/汇总仪表盘测试
# 覆盖：overview / trend / tasks / models / versions 聚合与数据隔离
# ==========================================================
import uuid
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from helpers import auth_headers, login_and_token  # noqa: E402


def _mk_task(client, token, name=None):
    """创建任务并加 1 条用例，返回 (task_id, headers)。"""
    h = auth_headers(token)
    payload = {
        "name": name or f"资产任务{uuid.uuid4().hex[:6]}",
        "task_type": "summary",
        "description": "d", "objective": "o", "criteria": "c",
        "initial_prompt": "请简洁摘要。", "max_rounds": 1,
    }
    tid = client.post("/api/v1/tasks", json=payload, headers=h).json()["data"]["id"]
    client.post(f"/api/v1/tasks/{tid}/cases",
                json={"input_text": "今天天气晴朗", "reference_output": "晴天"}, headers=h)
    return tid, h


def _inject_version(task_id: int, text: str, version_no: int = 1):
    """直接向测试库插入一条 PromptVersion（版本仅供迭代生成，测试注入更轻量）。"""
    from sqlalchemy.orm import Session
    from app.db.base import engine
    from app.models import PromptVersion
    with Session(engine) as s:
        s.add(PromptVersion(task_id=task_id, version_no=version_no,
                            prompt_text=text, is_best=0, score=88.0, frozen=0))
        s.commit()


def _inject_workflow_activity(user_id: int, task_id: int,
                              run_created_at: str, opt_created_at: str):
    """注入一条工作流 + 其运行/优化记录，用于趋势聚合与隔离测试。created_at 为 "YYYY-MM-DD HH:MM:SS"。"""
    from sqlalchemy.orm import Session
    from app.db.base import engine
    from app.models import Workflow, WorkflowRun, WorkflowStepOptimization
    with Session(engine) as s:
        wf = Workflow(user_id=user_id, task_id=task_id, name="自审注入工作流")
        s.add(wf)
        s.flush()
        s.add(WorkflowRun(workflow_id=wf.id, task_id=task_id, name="run",
                          status="completed", run_baseline=0, avg_score=80.0,
                          baseline_avg_score=75.0, created_at=run_created_at))
        s.add(WorkflowStepOptimization(workflow_id=wf.id, task_id=task_id, step_seq=1,
                                       status="completed", base_prompt="p", best_prompt="pp",
                                       base_score=70.0, best_score=85.0, improved=1,
                                       current_round=1, max_rounds=1, created_at=opt_created_at))
        s.commit()
        return wf.id


class TestDashboard:
    def test_overview_and_trend(self, client):
        """总览统计与近 N 天趋势聚合，数据随资产创建而变化。"""
        token = login_and_token(client, f"db_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _mk_task(client, token)

        ov = client.get("/api/v1/dashboard/overview", headers=h).json()
        assert ov["code"] == 0
        data = ov["data"]
        assert data["tasks"] == 1
        assert data["cases"] == 1
        assert data["versions"] == 0  # 未迭代前无版本
        assert data["endpoints"] == 0

        tr = client.get("/api/v1/dashboard/trend?days=30", headers=h).json()["data"]
        assert tr["days"] == 30
        today = tr["series"]["task"].get(_today())
        assert today == 1  # 今天创建了 1 个任务

    def test_tasks_asset_table(self, client):
        """任务资产表：聚合各子模块数量 + 关键字过滤。"""
        token = login_and_token(client, f"db2_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _mk_task(client, token, name="检索专用资产任务")

        rows = client.get("/api/v1/dashboard/tasks", headers=h).json()["data"]
        assert rows["total"] == 1
        item = rows["items"][0]
        assert item["id"] == tid
        assert item["case_count"] == 1
        assert item["version_count"] == 0
        assert item["benchmark_count"] == 0
        assert item["workflow_count"] == 0

        # 关键字过滤命中
        hit = client.get("/api/v1/dashboard/tasks?keyword=检索专用", headers=h).json()["data"]
        assert hit["total"] == 1
        miss = client.get("/api/v1/dashboard/tasks?keyword=不存在的名字", headers=h).json()["data"]
        assert miss["total"] == 0

    def test_versions_search_and_isolation(self, client):
        """版本库检索：跨任务搜到冻结/最优版本，且看不到他人资产。"""
        token_a = login_and_token(client, f"db3_{uuid.uuid4().hex[:8]}@a.com")
        token_b = login_and_token(client, f"db4_{uuid.uuid4().hex[:8]}@b.com")
        h_a, h_b = auth_headers(token_a), auth_headers(token_b)
        tid, _ = _mk_task(client, token_a, name="甲的任务")
        _inject_version(tid, "请对输入做精准摘要。", version_no=1)

        # A 检索到自己的版本
        vs = client.get("/api/v1/dashboard/versions?keyword=摘要", headers=h_a).json()["data"]
        assert vs["total"] >= 1
        assert vs["items"][0]["task_id"] == tid
        # B 检索同一关键词：看不到 A 的版本（数据隔离）
        vs_b = client.get("/api/v1/dashboard/versions?keyword=摘要", headers=h_b).json()["data"]
        assert vs_b["total"] == 0

    def test_models_stats(self, client):
        """模型统计：无调用/无评测时返回空数组，接口可用。"""
        token = login_and_token(client, f"db5_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        data = client.get("/api/v1/dashboard/models", headers=h).json()["data"]
        assert data["calls"] == []
        assert data["best_dist"] == []

    def test_trend_workflow_isolation_and_window(self, client):
        """趋势隔离：工作流运行/优化必须归口属主；且遵守 days 时间窗口。"""
        import datetime as dt

        from sqlalchemy.orm import Session
        from app.db.base import engine
        from app.models import User

        mail_a = f"db6_{uuid.uuid4().hex[:8]}@a.com"
        mail_b = f"db7_{uuid.uuid4().hex[:8]}@b.com"
        token_a = login_and_token(client, mail_a)
        token_b = login_and_token(client, mail_b)

        def _uid(email):
            with Session(engine) as s:
                return s.query(User.id).filter(User.email == email).scalar()

        tid, _ = _mk_task(client, token_a)
        today = _today()
        old_day = (dt.datetime.now() - dt.timedelta(days=40)).strftime("%Y-%m-%d")
        _inject_workflow_activity(
            _uid(mail_a), tid,
            run_created_at=f"{today} 10:00:00",
            opt_created_at=f"{old_day} 10:00:00",
        )

        h_a, h_b = auth_headers(token_a), auth_headers(token_b)
        tr_a = client.get("/api/v1/dashboard/trend?days=30", headers=h_a).json()["data"]
        # 今天的运行记录应被统计；40 天前的优化记录超出 30 天窗口应被排除
        assert tr_a["series"]["workflow_run"].get(today, 0) == 1
        assert tr_a["series"]["optimization"].get(old_day) is None
        # 拉长到 90 天窗口，40 天前的优化记录应进入统计
        tr_a90 = client.get("/api/v1/dashboard/trend?days=90", headers=h_a).json()["data"]
        assert tr_a90["series"]["optimization"].get(old_day, 0) == 1

        # 数据隔离：B 无任何工作流资产，必定看不到 A 的运行/优化趋势（防跨租户）
        tr_b = client.get("/api/v1/dashboard/trend?days=30", headers=h_b).json()["data"]
        assert tr_b["series"]["workflow_run"] == {}
        assert tr_b["series"]["optimization"] == {}

    def test_requires_auth(self, client):
        """未登录访问仪表盘应返回 401。"""
        r = client.get("/api/v1/dashboard/overview").json()
        assert r["code"] == 401


def _today() -> str:
    """当前日期 YYYY-MM-DD（与后端 now_iso 截断口径一致）。"""
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d")
