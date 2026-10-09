# ==========================================================
# 测试辅助：注册/登录与鉴权头（供各测试文件复用）
# ==========================================================


def login_and_token(client, email: str, password: str = "Test@1234") -> str:
    """注册并登录，返回 JWT token；失败时抛出断言。"""
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "测试用户"},
    )
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    body = resp.json()
    assert body["code"] == 0, body
    return body["data"]["token"]


def auth_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}