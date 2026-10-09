# ==========================================================
# 接口测试：任务与用例的完整 CRUD、数据隔离与越权、管理员接口权限
# ==========================================================
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests 目录，供 helpers
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend 目录，供 app

from helpers import auth_headers, login_and_token


def _mk_task_payload():
    return {
        "name": f"任务{uuid.uuid4().hex[:6]}",
        "task_type": "summary",
        "description": "文本摘要任务",
        "objective": "忠于原文、简洁准确",
        "criteria": "信息不丢失；语言通顺；不超过两句话",
    }


class TestTaskCrud:
    def test_list_without_token_unauthorized(self, client):
        resp = client.get("/api/v1/tasks")
        assert resp.json()["code"] != 0

    def test_create_and_get(self, client):
        token = login_and_token(client, f"cr_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        created = client.post("/api/v1/tasks", json=_mk_task_payload(), headers=h).json()
        assert created["code"] == 0
        task = created["data"]
        assert task["status"] == "pending"
        assert task["best_score"] is None

        got = client.get(f"/api/v1/tasks/{task['id']}", headers=h).json()
        assert got["code"] == 0
        assert got["data"]["name"] == task["name"]

    def test_target_score_blank_defaults_to_none(self, client):
        """回归：目标分数留空时，落库应为 None（不设达标线），
        绝不能被 DEFAULT_TARGET_SCORE(85) 悄悄回填——否则任务首轮就"达标即停"，
        与"留空=靠收敛多跑"的语义相悖。"""
        token = login_and_token(client, f"ts_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        payload = _mk_task_payload()  # 不传 target_score
        created = client.post("/api/v1/tasks", json=payload, headers=h).json()
        assert created["code"] == 0
        assert created["data"]["target_score"] is None, "留空目标分数必须落库为 None，而非 85"

    def test_target_score_explicit_kept(self, client):
        """显式填写的目标分数应原样保留。"""
        token = login_and_token(client, f"ts2_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        p = _mk_task_payload()
        p["target_score"] = 92.0
        created = client.post("/api/v1/tasks", json=p, headers=h).json()
        assert created["code"] == 0
        assert created["data"]["target_score"] == 92.0

    def test_list_and_keyword_filter(self, client):
        token = login_and_token(client, f"lst_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        uid = uuid.uuid4().hex[:6]
        client.post("/api/v1/tasks", json={**_mk_task_payload(), "name": f"摘要-{uid}"}, headers=h)
        lst = client.get(f"/api/v1/tasks?keyword={uid}", headers=h).json()
        assert lst["data"]["total"] == 1

    def test_update_task(self, client):
        token = login_and_token(client, f"up_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        tid = client.post("/api/v1/tasks", json=_mk_task_payload(), headers=h).json()["data"]["id"]
        updated = client.put(
            f"/api/v1/tasks/{tid}", json={"name": "改后名称"}, headers=h
        ).json()
        assert updated["code"] == 0
        assert updated["data"]["name"] == "改后名称"

    def test_delete_task(self, client):
        token = login_and_token(client, f"del_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        tid = client.post("/api/v1/tasks", json=_mk_task_payload(), headers=h).json()["data"]["id"]
        resp = client.delete(f"/api/v1/tasks/{tid}", headers=h).json()
        assert resp["code"] == 0
        got = client.get(f"/api/v1/tasks/{tid}", headers=h).json()
        assert got["code"] != 0

    def test_data_isolation_between_users(self, client):
        """A 创建的任务，B 不能访问（返回非 0）。"""
        hA = auth_headers(login_and_token(client, f"isoA_{uuid.uuid4().hex[:6]}@a.com"))
        hB = auth_headers(login_and_token(client, f"isoB_{uuid.uuid4().hex[:6]}@a.com"))
        tid = client.post("/api/v1/tasks", json=_mk_task_payload(), headers=hA).json()["data"]["id"]
        resp = client.get(f"/api/v1/tasks/{tid}", headers=hB).json()
        assert resp["code"] != 0


class TestCaseCrud:
    def test_add_list_delete_case(self, client):
        token = login_and_token(client, f"c_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        tid = client.post("/api/v1/tasks", json=_mk_task_payload(), headers=h).json()["data"]["id"]

        add = client.post(
            f"/api/v1/tasks/{tid}/cases",
            json={"input_text": "今天天气很好我们去公园", "reference_output": "今天去公园", "keywords": ["公园"]},
            headers=h,
        ).json()
        assert add["code"] == 0

        lst = client.get(f"/api/v1/tasks/{tid}/cases", headers=h).json()
        assert lst["data"]["total"] == 1
        assert lst["data"]["items"][0]["input_text"] == "今天天气很好我们去公园"

        cid = lst["data"]["items"][0]["id"]
        resp = client.delete(f"/api/v1/tasks/{tid}/cases/{cid}", headers=h).json()
        assert resp["code"] == 0
        assert client.get(f"/api/v1/tasks/{tid}/cases", headers=h).json()["data"]["total"] == 0

    def test_add_case_requires_input(self, client):
        token = login_and_token(client, f"cf_{uuid.uuid4().hex[:8]}@a.com")
        h = auth_headers(token)
        tid = client.post("/api/v1/tasks", json=_mk_task_payload(), headers=h).json()["data"]["id"]
        resp = client.post(
            f"/api/v1/tasks/{tid}/cases", json={"input_text": ""}, headers=h
        ).json()
        assert resp["code"] != 0


class TestAdminPermission:
    def test_normal_user_cannot_access_admin_logs(self, client):
        token = login_and_token(client, f"adm_{uuid.uuid4().hex[:8]}@a.com")
        resp = client.get("/api/v1/admin/logs", headers=auth_headers(token))
        assert resp.json()["code"] != 0  # 1003 权限不足 / 403

    def test_normal_user_cannot_list_users(self, client):
        token = login_and_token(client, f"adm2_{uuid.uuid4().hex[:8]}@a.com")
        resp = client.get("/api/v1/admin/users", headers=auth_headers(token))
        assert resp.json()["code"] != 0


class TestMeta:
    def test_task_templates_available(self, client):
        resp = client.get("/api/v1/task-templates")
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) > 0

    def test_models_available(self, client):
        resp = client.get("/api/v1/models")
        assert resp.json()["code"] == 0

    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        # /health 返回统一响应包裹 {code, data:{status}}
        assert resp.json()["data"]["status"] == "ok"