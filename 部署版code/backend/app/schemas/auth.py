# ==========================================================
# 通用响应结构 & 认证相关 Pydantic Schema
# ==========================================================
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, EmailStr, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一响应包裹：code=0 成功，message 提示，data 业务数据。"""

    code: int = 0
    message: str = "success"
    data: Optional[T] = None


class PageResult(BaseModel, Generic[T]):
    """分页结果结构。"""

    items: list[T]
    total: int
    page: int
    page_size: int


# ---------- 认证 ----------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=64)
    full_name: str = Field(default="", max_length=64)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str] = None
    role: str
    is_active: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    token: str
    user: UserOut