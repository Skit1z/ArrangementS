"""全局枚举定义。"""
from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    admin = "admin"
    user = "user"


class PersonStatus(str, enum.Enum):
    active = "active"
    suspended = "suspended"
    left = "left"


class ImportBatchStatus(str, enum.Enum):
    previewing = "previewing"
    confirmed = "confirmed"
    failed = "failed"
