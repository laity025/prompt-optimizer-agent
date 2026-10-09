# ==========================================================
# 报告分享测试：创建/公开只读/访问计数/撤销/越权/免登录
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
        "name": name or f"共享任务{uuid.uuid4().hex[:6]}",
        "task_type": "summary",
        "description": "d", "objective": "o", "criteria": "c",
        "initial_prompt": "请简洁摘要。", "max_rounds": 1,
    }
    tid = client.post("/api/v1/tasks", json=payload, headers=h).json()["data"]["id"]
    return tid, h


def _uid_of(email) -> int:
    from sqlalchemy.orm import Session
    from app.db.base import engine
    from app.models import User
    with Session(engine) as s:
        return s.query(User.id).filter(User.email == email).scalar()


def _inject_benchmark_run(user_id: int, task_id: int, name: str) -> int:
    """直接落库一条评测运行记录（无需真实跑模型）。"""
    from sqlalchemy.orm import Session
    from app.db.base import engine
    from app.models import BenchmarkRun
    with Session(engine) as s:
        run = BenchmarkRun(user_id=user_id, task_id=task_id, name=name,
                           prompt_mode="best", prompt_snapshot="摘要提示词",
                           models_json='["model-a"]', status="completed")
        s.add(run)
        s.commit()
        return run.id


def _create_share(client, headers, report_type, target_id, expires_hours=None):
    body = {"report_type": report_type, "target_id": target_id}
    if expires_hours is not None:
        body["expires_hours"] = expires_hours
    r = client.post("/api/v1/reports/shares", json=body, headers=headers)
    return r.json()


class TestReportShare:
    def test_task_share_public_and_view_count(self, client):
        """任务报告分享：公开只读可读、访问计数随查看递增。"""
        token = login_and_token(client, f"rs_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _mk_task(client, token, name="公开分享用任务")

        resp = _create_share(client, h, "task", tid, expires_hours=None)
        assert resp["code"] == 0
        share = resp["data"]
        token_link = share["token"]
        assert share["view_count"] == 0

        # 免登录读取数据
        pub = client.get(f"/api/v1/public/reports/{token_link}/data").json()
        assert pub["code"] == 0
        d = pub["data"]
        assert d["meta"]["valid"] is True
        assert d["payload"]["task_id"] == tid
        assert d["payload"]["task_name"] == "公开分享用任务"

        # 访问计数已累加（原子自增，第二次公开读取再 +1）
        meta2 = client.get(f"/api/v1/public/reports/{token_link}").json()["data"]
        assert meta2["view_count"] == 1

    def test_benchmark_share_permission_isolation(self, client):
        """越权防护：B 不能为 A 的评测记录创建分享。"""
        mail_a = f"rs2_{uuid.uuid4().hex[:8]}@a.com"
        mail_b = f"rs3_{uuid.uuid4().hex[:8]}@b.com"
        token_a = login_and_token(client, mail_a)
        token_b = login_and_token(client, mail_b)
        tid_a, _ = _mk_task(client, token_a, name="甲评测")
        run_id = _inject_benchmark_run(_uid_of(mail_a), tid_a, "甲模型对比")

        # A 可创建
        ok = _create_share(client, auth_headers(token_a), "benchmark", run_id)
        assert ok["code"] == 0
        # B 越权创建被拒
        deny = _create_share(client, auth_headers(token_b), "benchmark", run_id)
        assert deny["code"] == 1002

    def test_revoke_invalidates_public_link(self, client):
        """撤销后公开读取失效。"""
        token = login_and_token(client, f"rs4_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _mk_task(client, token)
        share = _create_share(client, h, "task", tid)["data"]

        # 撤销
        rev = client.delete(f"/api/v1/reports/shares/{share['id']}", headers=h).json()
        assert rev["code"] == 0
        # 公开数据读取失效，元信息 valid=False
        denied = client.get(f"/api/v1/public/reports/{share['token']}/data").json()
        assert denied["code"] == 1002
        meta = client.get(f"/api/v1/public/reports/{share['token']}").json()["data"]
        assert meta["valid"] is False

    def test_expiry_validation_and_type_check(self, client):
        """非法限时时长 / 非法报告类型被拒绝。"""
        token = login_and_token(client, f"rs5_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _mk_task(client, token)

        bad_expiry = _create_share(client, h, "task", tid, expires_hours=5)
        assert bad_expiry["code"] == 1004

        bad_type = _create_share(client, h, "unknown", tid)
        assert bad_type["code"] == 1004

    def test_management_requires_auth(self, client):
        """创建/列表分享需要登录；公开读取无需登录。"""
        c = client.get("/api/v1/reports/shares").json()
        assert c["code"] == 401
        p = client.get("/api/v1/public/reports/nonexistent/data")
        assert p.status_code == 200  # 公开接口存在；token 无效返回 1002
        body = p.json()
        assert body["code"] == 1002

    def test_expired_share_rejects_public_read(self, client):
        """分享链接已过期后，公开只读应失效返回业务错误。"""
        from datetime import datetime

        from sqlalchemy.orm import Session

        from app.db.base import engine
        from app.models import ReportShare

        token = login_and_token(client, f"rs6_{uuid.uuid4().hex[:8]}@a.com")
        tid, h = _mk_task(client, token)
        share = _create_share(client, h, "task", tid, expires_hours=1)["data"]
        # 直接把该分享的过期时间改写为过去时间，模拟链接已过期
        with Session(engine) as s:
            row = s.query(ReportShare).filter(ReportShare.token == share["token"]).scalar()
            row.expires_at = datetime(2000, 1, 1, 0, 0, 0).strftime("%Y-%m-%dT%H:%M:%S")
            s.commit()
        denied = client.get(f"/api/v1/public/reports/{share['token']}/data").json()
        assert denied["code"] == 1002