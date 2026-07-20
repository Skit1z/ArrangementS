"""登录失败限速。优先使用 Redis；不可用时回退进程内存（单机可用）。"""

from __future__ import annotations

import time

from app.core.config import settings

try:  # pragma: no cover - 取决于运行环境
    import redis as _redis

    _client = _redis.from_url(settings.redis_url, socket_connect_timeout=0.3)
    _client.ping()
except Exception:  # noqa: BLE001 - 任何连接问题都回退
    _client = None

_memory: dict[str, tuple[int, float]] = {}


def _key(identifier: str) -> str:
    return f"login:fail:{identifier}"


def register_failure(identifier: str) -> int:
    """记录一次失败，返回当前窗口内失败次数。"""
    key = _key(identifier)
    window = settings.login_lock_seconds
    if _client is not None:
        pipe = _client.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        count, _ = pipe.execute()
        return int(count)
    count, expiry = _memory.get(key, (0, 0.0))
    now = time.time()
    if now > expiry:
        count = 0
    count += 1
    _memory[key] = (count, now + window)
    return count


def is_locked(identifier: str) -> bool:
    key = _key(identifier)
    if _client is not None:
        val = _client.get(key)
        return val is not None and int(val) >= settings.login_max_failures
    count, expiry = _memory.get(key, (0, 0.0))
    if time.time() > expiry:
        return False
    return count >= settings.login_max_failures


def reset(identifier: str) -> None:
    key = _key(identifier)
    if _client is not None:
        _client.delete(key)
    else:
        _memory.pop(key, None)
