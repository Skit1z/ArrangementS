"""系统状态与版本/构建信息接口。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.core.config import settings

BEIJING_TZ = timezone(timedelta(hours=8))
START_TIME = datetime.now(BEIJING_TZ)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def system_status() -> dict:
    now = datetime.now(BEIJING_TZ)
    uptime_seconds = int((now - START_TIME).total_seconds())

    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days > 0:
        parts.append(f"{days}天")
    if hours > 0:
        parts.append(f"{hours}小时")
    if minutes > 0:
        parts.append(f"{minutes}分")
    if not parts:
        parts.append(f"{seconds}秒")
    uptime_formatted = "".join(parts)

    return {
        "status": "online",
        "backend_build_time": START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        "backend_start_time": START_TIME.strftime("%Y-%m-%d %H:%M:%S"),
        "uptime_seconds": uptime_seconds,
        "uptime_formatted": uptime_formatted,
        "env": settings.app_env,
    }
