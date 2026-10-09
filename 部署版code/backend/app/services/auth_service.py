# ==========================================================
# 认证服务：注册/登录/获取当前用户
# ==========================================================
import threading
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import param_error
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User

# ---------- 登录暴力破解防护（进程内计数 + 锁定） ----------
# 同一 IP+邮箱 15 分钟内失败达 _LOGIN_MAX_FAILS 次，锁定 _LOGIN_LOCK_SECONDS。
# 内存态实现与项目既有 progress_tracker 等一致；重启即清零，对单机演示场景足够。
_LOGIN_MAX_FAILS = 5
_LOGIN_WINDOW_SECONDS = 15 * 60
_LOGIN_LOCK_SECONDS = 15 * 60
_login_attempts: dict[str, dict] = {}
_login_lock = threading.Lock()


def _login_key(ip: str, email: str) -> str:
    """锁定键：IP + 邮箱（小写归一化），IP 为空时退化为邮箱。"""
    return f"{ip or ''}:{email.strip().lower()}"


def login_locked_seconds(ip: str, email: str) -> float | None:
    """返回剩余锁定秒数；未锁定返回 None。过期记录顺带清理，防止字典无限增长。"""
    with _login_lock:
        rec = _login_attempts.get(_login_key(ip, email))
        if not rec:
            return None
        now = time.monotonic()
        if rec["locked_until"] and now < rec["locked_until"]:
            return rec["locked_until"] - now
        # 锁定已过期，或失败计数窗口已过期：清掉该键
        if (rec["locked_until"] and now >= rec["locked_until"]) \
                or now - rec["window_start"] > _LOGIN_WINDOW_SECONDS:
            _login_attempts.pop(_login_key(ip, email), None)
        return None


def record_login_failure(ip: str, email: str) -> int:
    """记录一次登录失败；达到阈值即置为锁定态，返回当前失败次数。"""
    with _login_lock:
        key = _login_key(ip, email)
        now = time.monotonic()
        rec = _login_attempts.get(key)
        if not rec or now - rec["window_start"] > _LOGIN_WINDOW_SECONDS:
            rec = {"fails": 0, "window_start": now, "locked_until": 0}
            _login_attempts[key] = rec
        rec["fails"] += 1
        if rec["fails"] >= _LOGIN_MAX_FAILS:
            rec["locked_until"] = now + _LOGIN_LOCK_SECONDS
        return rec["fails"]


def clear_login_failures(ip: str, email: str) -> None:
    """登录成功后清除失败计数。"""
    with _login_lock:
        _login_attempts.pop(_login_key(ip, email), None)


def register(db: Session, email: str, password: str, full_name: str) -> User:
    """注册新用户。邮箱已存在则报参数错误。"""
    if db.scalar(select(User).where(User.email == email)):
        raise param_error("该邮箱已被注册")
    user = User(email=email, password_hash=hash_password(password), full_name=full_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(db: Session, email: str, password: str, client_ip: str = "") -> tuple[User, str]:
    """登录校验并签发 token。

    :param client_ip: 客户端 IP，用于失败计数与锁定（Nginx 反代下取 X-Forwarded-For）。
    """
    # 暴力破解防护：命中锁定直接拒绝，避免继续执行密码比对
    remain = login_locked_seconds(client_ip, email)
    if remain:
        raise param_error(f"尝试次数过多，请 {int(remain // 60) + 1} 分钟后再试")
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        # 邮箱不存在也计数，避免通过"锁定行为差异"枚举有效账号
        record_login_failure(client_ip, email)
        raise param_error("邮箱或密码错误")
    clear_login_failures(client_ip, email)
    if not user.is_active:
        raise param_error("账号已被禁用")
    token = create_access_token(user.id, extra={"role": user.role})
    return user, token