"""FastAPI 应用入口。"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.cookies import CSRF_COOKIE_NAME, CSRF_HEADER_NAME, verify_csrf_token

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
CSRF_EXEMPT_PATHS = {"/api/v1/auth/login"}


class CSRFMiddleware(BaseHTTPMiddleware):
    """对非安全方法执行双提交 Cookie 校验。"""

    async def dispatch(self, request: Request, call_next):
        if request.method not in SAFE_METHODS and request.url.path not in CSRF_EXEMPT_PATHS:
            if request.url.path.startswith("/api/"):
                header = request.headers.get(CSRF_HEADER_NAME)
                cookie = request.cookies.get(CSRF_COOKIE_NAME)
                if not header or header != cookie or not verify_csrf_token(header):
                    return JSONResponse(status_code=403, content={"detail": "CSRF 校验失败"})
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response


def create_app() -> FastAPI:
    app = FastAPI(title="会议场地排班系统 API", version="0.1.0")

    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSRFMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*", CSRF_HEADER_NAME],
    )

    app.include_router(api_router)

    @app.get("/health", tags=["system"])
    def health() -> dict:
        return {"status": "ok", "env": settings.app_env}

    return app


app = create_app()
