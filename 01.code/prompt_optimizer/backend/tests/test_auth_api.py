# ==========================================================
# 接口测试：认证与鉴权（注册/登录/身份获取/鉴权校验）
# 走真实 HTTP 契约，覆盖成功路径与失败/越权场景
# ==========================================================
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # tests 目录，供 helpers
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend 目录，供 app

from helpers import auth_headers, login_and_token


class TestAuth:
    def test_register_success(self, client):
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "u1@a.com", "password": "Test@1234", "full_name": "甲"},
        )
        body = resp.json()
        assert resp.status_code == 200
        assert body["code"] == 0
        assert body["data"]["email"] == "u1@a.com"

    def test_register_duplicate_email(self, client):
        login_and_token(client, "dup@a.com")
        resp = client.post(
            "/api/v1/auth/register",
            json={"email": "dup@a.com", "password": "Test@1234", "full_name": "重复"},
        )
        assert resp.json()["code"] != 0

    def test_login_success_returns_token(self, client):
        token = login_and_token(client, "login@a.com")
        assert isinstance(token, str) and len(token) > 20

    def test_login_wrong_password(self, client):
        client.post(
            "/api/v1/auth/register",
            json={"email": "lp@a.com", "password": "Test@1234", "full_name": "x"},
        )
        resp = client.post(
            "/api/v1/auth/login", json={"email": "lp@a.com", "password": "Wrong@1"}
        )
        assert resp.json()["code"] != 0

    def test_me_with_valid_token(self, client):
        token = login_and_token(client, "me@a.com")
        resp = client.get("/api/v1/auth/me", headers=auth_headers(token))
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["email"] == "me@a.com"

    def test_me_without_token_unauthorized(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.json()["code"] != 0

    def test_me_with_malformed_token(self, client):
        resp = client.get("/api/v1/auth/me", headers=auth_headers("bad.token.here"))
        assert resp.json()["code"] != 0