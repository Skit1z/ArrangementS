"""登录失败限速（进程内内存版）。

仅依赖进程内存字典，单进程部署即可生效。多 worker 部署时各进程独立计数，
如需跨进程共享限速请改用外部存储。
"""

from __future__ import annotations

import time

from app.core.config import settings

_memory: dict[str, tuple[int, float]] = {}


def _key(identifier: str) -> str:
    return f"login:fail:{identifier}"


def register_failure(identifier: str) -> int:
    """记录一次失败，返回当前窗口内失败次数。"""
    key = _key(identifier)
    window = settings.login_lock_seconds
    count, expiry = _memory.get(key, (0, 0.0))
    now = time.time()
    if now > expiry:
        count = 0
    count += 1
    _memory[key] = (count, now + window)
    return count


def is_locked(identifier: str) -> bool:
    key = _key(identifier)
    count, expiry = _memory.get(key, (0, 0.0))
    if time.time() > expiry:
        return False
    return count >= settings.login_max_failures


def reset(identifier: str) -> None:
    _memory.pop(_key(identifier), None)
