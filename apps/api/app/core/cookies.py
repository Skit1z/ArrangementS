"""认证 Cookie 与 CSRF 令牌管理（双提交 Cookie 方案）。"""
from __future__ import annotations

import hashlib
import hmac
import secrets

from fastapi import Response

from app.core.config import settings
from app.core.deps import ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME

CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"


def _sign(token: str) -> str:
    return hmac.new(settings.csrf_secret.encode(), token.encode(), hashlib.sha256).hexdigest()


def issue_csrf_token() -> str:
    raw = secrets.token_urlsafe(24)
    return f"{raw}.{_sign(raw)}"


def verify_csrf_token(token: str | None) -> bool:
    if not token or "." not in token:
        return False
    raw, sig = token.rsplit(".", 1)
    return hmac.compare_digest(sig, _sign(raw))


def set_auth_cookies(response: Response, access: str, refresh: str) -> str:
    common = {
        "secure": settings.cookie_secure,
        "samesite": "lax",
        "domain": settings.cookie_domain,
    }
    response.set_cookie(
        ACCESS_COOKIE_NAME,
        access,
        httponly=True,
        max_age=settings.access_token_ttl_minutes * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        refresh,
        httponly=True,
        path="/api/v1/auth",
        max_age=settings.refresh_token_ttl_days * 86400,
        **common,
    )
    csrf = issue_csrf_token()
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf,
        httponly=False,  # 需被前端 JS 读取以回填请求头
        max_age=settings.access_token_ttl_minutes * 60,
        **common,
    )
    return csrf


def clear_auth_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE_NAME, CSRF_COOKIE_NAME):
        response.delete_cookie(name, domain=settings.cookie_domain)
    response.delete_cookie(
        REFRESH_COOKIE_NAME, path="/api/v1/auth", domain=settings.cookie_domain
    )
