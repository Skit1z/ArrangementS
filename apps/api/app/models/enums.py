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


class VenueType(str, enum.Enum):
    fixed_shift = "fixed_shift"  # 黄楼：固定班次
    event_based = "event_based"  # 蓝厅 / 图书馆报告厅：按任务安排


class DayType(str, enum.Enum):
    workday = "workday"  # 调休工作日 -> 按工作日规则
    weekend_rule = "weekend_rule"  # 法定节假日/周末 -> 按周末规则
    closed = "closed"  # 停班
    custom = "custom"  # 自定义人数


class SpecialDateSource(str, enum.Enum):
    manual = "manual"
    holiday_sync = "holiday_sync"


class TaskStatus(str, enum.Enum):
    draft = "draft"
    confirmed = "confirmed"
    scheduled = "scheduled"
    executing = "executing"
    completed = "completed"
    cancelled = "cancelled"
