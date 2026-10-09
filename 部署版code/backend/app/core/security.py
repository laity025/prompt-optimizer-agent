# ==========================================================
# 安全模块：JWT 签发/校验 + 密码哈希
# 基于 python-jose 与 passlib[bcrypt]
# ==========================================================
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import get_settings

settings = get_settings()

# bcrypt 密码哈希上下文
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """对明文密码做 bcrypt 哈希。"""
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    """校验明文密码是否匹配哈希。"""
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: int | str, extra: Optional[dict[str, Any]] = None) -> str:
    """签发 JWT，subject 为用户 id，默认有效期 24 小时。

    :param subject: 用户主键
    :param extra: 附加声明，如 role
    :return: 编码后的 token 字符串
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    payload: dict[str, Any] = {"sub": str(subject), "exp": expire}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """校验并解码 JWT，非法或过期返回 None。"""
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None