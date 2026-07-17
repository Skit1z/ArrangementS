"""认证相关的请求 / 响应模型。"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.models.enums import UserRole


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    old_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=6, max_length=256)


class UserOut(BaseModel):
    id: uuid.UUID
    username: str
    role: UserRole
    is_active: bool

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    message: str
