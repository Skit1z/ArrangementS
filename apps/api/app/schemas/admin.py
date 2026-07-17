"""admin 账号管理请求 / 响应。"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CreateAdminRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=6, max_length=256)


class ResetPasswordResult(BaseModel):
    message: str
    # 仅在生成/重置时一次性返回，不落库、不入日志。
    new_password: str | None = None
