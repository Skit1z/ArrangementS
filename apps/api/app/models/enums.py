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


class PlanStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class SlotSourceType(str, enum.Enum):
    fixed_shift = "fixed_shift"
    venue_task = "venue_task"
    manual = "manual"


class SlotStatus(str, enum.Enum):
    open = "open"
    filled = "filled"
    cancelled = "cancelled"


class AssignmentSource(str, enum.Enum):
    auto = "auto"
    manual = "manual"
    swap = "swap"
    replacement = "replacement"
    forced = "forced"


class PlanAssignmentStatus(str, enum.Enum):
    pending = "pending"  # 待发布
    assigned = "assigned"  # 已安排
    vacant = "vacant"  # 空缺
    replaced = "replaced"  # 已替换
    cancelled = "cancelled"  # 已取消


class ExecutionStatus(str, enum.Enum):
    pending = "pending"  # 待值班
    completed = "completed"  # 已完成
    absent = "absent"  # 未到岗
    leave = "leave"  # 请假
    swapped = "swapped"  # 已换班
    task_cancelled = "task_cancelled"  # 任务取消


class LeaveStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    withdrawn = "withdrawn"
    cancelled = "cancelled"


class SwapMode(str, enum.Enum):
    targeted = "targeted"  # 指定人员换班
    open = "open"  # 公开征集替班


class SwapStatus(str, enum.Enum):
    awaiting_target = "awaiting_target"  # 待对方响应
    open_collecting = "open_collecting"  # 公开征集中
    pending_admin = "pending_admin"  # 待 admin 审核
    approved = "approved"
    rejected = "rejected"
    withdrawn = "withdrawn"
    expired = "expired"


class SwapCandidateStatus(str, enum.Enum):
    applied = "applied"
    selected = "selected"
    rejected = "rejected"
    expired = "expired"


class MonthlySummaryStatus(str, enum.Enum):
    calculating = "calculating"
    draft = "draft"
    confirmed = "confirmed"
    locked = "locked"
