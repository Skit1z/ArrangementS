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


class BuildingType(str, enum.Enum):
    all = "all"
    main = "main"  # 主教学楼（B 开头）
    second = "second"  # 第二教学楼（02- 开头）


class ParseStatus(str, enum.Enum):
    pending = "pending"
    parsing = "parsing"
    parsed = "parsed"
    failed = "failed"


class ReviewStatus(str, enum.Enum):
    draft = "draft"  # 尚未提交
    pending = "pending"  # 待 admin 审核
    approved = "approved"  # 已生效
    rejected = "rejected"
    superseded = "superseded"  # 被新版本取代


class AvailabilitySource(str, enum.Enum):
    course = "course"
    user_request = "user_request"
    admin = "admin"
    leave = "leave"
    suspension = "suspension"


class AvailabilityStatus(str, enum.Enum):
    active = "active"
    expired = "expired"  # 逻辑失效（学期结束等）


class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    withdrawn = "withdrawn"
    expired = "expired"
