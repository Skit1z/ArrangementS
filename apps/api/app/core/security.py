"""密码哈希、令牌签发与校验。

- 密码：Argon2id，明文绝不落盘。
- 令牌：JWT（HS256），承载 user_id / role / type。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.core.config import settings

_ph = PasswordHasher()

ACCESS_TOKEN = "access"
REFRESH_TOKEN = "refresh"


def hash_password(plain: str) -> str:
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def needs_rehash(hashed: str) -> bool:
    try:
        return _ph.check_needs_rehash(hashed)
    except (InvalidHashError, ValueError):
        return True


def _create_token(subject: uuid.UUID, role: str, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(subject),
        "role": role,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_access_token(subject: uuid.UUID, role: str) -> str:
    return _create_token(
        subject, role, ACCESS_TOKEN, timedelta(minutes=settings.access_token_ttl_minutes)
    )


def create_refresh_token(subject: uuid.UUID, role: str) -> str:
    return _create_token(
        subject, role, REFRESH_TOKEN, timedelta(days=settings.refresh_token_ttl_days)
    )


def decode_token(token: str, expected_type: str | None = None) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if expected_type is not None and payload.get("type") != expected_type:
        raise jwt.InvalidTokenError("token type mismatch")
    return payload
