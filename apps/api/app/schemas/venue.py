"""场地、班次模板、任务、特殊日期、倍率的请求 / 响应。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, Field

from app.models.enums import DayType, SpecialDateSource, TaskStatus, VenueType


# --- 场地 ---
class VenueCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    code: str = Field(min_length=1, max_length=32)
    venue_type: VenueType
    address: str | None = None
    default_required_people: int = 2
    default_prep_minutes: int = 30
    default_cleanup_minutes: int = 30
    sort_order: int = 0
    description: str | None = None


class VenueUpdate(BaseModel):
    name: str | None = None
    venue_type: VenueType | None = None
    address: str | None = None
    default_required_people: int | None = None
    default_prep_minutes: int | None = None
    default_cleanup_minutes: int | None = None
    sort_order: int | None = None
    description: str | None = None


class VenueOut(BaseModel):
    id: uuid.UUID
    name: str
    code: str
    venue_type: VenueType
    address: str | None
    default_required_people: int
    default_prep_minutes: int
    default_cleanup_minutes: int
    sort_order: int
    is_active: bool

    model_config = {"from_attributes": True}


# --- 班次模板 ---
class ShiftTemplateIn(BaseModel):
    name: str
    start_time: time
    end_time: time
    credited_minutes: int = 120
    weekday_required_people: int = 2
    weekend_required_people: int = 1
    is_active: bool = True


class ShiftTemplateOut(ShiftTemplateIn):
    id: uuid.UUID

    model_config = {"from_attributes": True}


# --- 任务 ---
class TaskCreate(BaseModel):
    venue_id: uuid.UUID
    title: str = Field(min_length=1, max_length=128)
    booking_start_at: datetime
    booking_end_at: datetime
    prep_minutes: int | None = None
    cleanup_minutes: int | None = None
    required_people: int | None = None
    is_temporary: bool = False
    organization: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None
    requirements: str | None = None
    notes: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    booking_start_at: datetime | None = None
    booking_end_at: datetime | None = None
    prep_minutes: int | None = None
    cleanup_minutes: int | None = None
    required_people: int | None = None
    organization: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None


class TaskTransitionIn(BaseModel):
    """任务状态转换请求。target_status 必须是 TaskStatus 枚举值。"""

    target_status: str
    requirements: str | None = None
    notes: str | None = None
    expected_version: int | None = None


class TaskOut(BaseModel):
    id: uuid.UUID
    venue_id: uuid.UUID
    title: str
    booking_start_at: datetime
    booking_end_at: datetime
    prep_minutes: int
    cleanup_minutes: int
    duty_start_at: datetime
    duty_end_at: datetime
    required_people: int
    is_temporary: bool
    status: TaskStatus
    version: int

    model_config = {"from_attributes": True}


class TaskListItem(TaskOut):
    """列表项：附带场地名（脱敏风格一致），便于 admin 表格直接渲染。"""

    venue_name: str
    organization: str | None = None
    contact_name: str | None = None
    contact_phone: str | None = None


# --- 特殊日期 ---
class SpecialDateIn(BaseModel):
    date: date
    day_type: DayType
    custom_required_people: int | None = None
    reason: str | None = None


class SpecialDateOut(BaseModel):
    id: uuid.UUID
    date: date
    day_type: DayType
    custom_required_people: int | None
    reason: str | None
    source: SpecialDateSource

    model_config = {"from_attributes": True}


class HolidaySyncRequest(BaseModel):
    year: int
    url: str | None = None
    data: dict | None = None  # 手动导入 JSON 时提供，优先于网络抓取


class HolidaySyncConfirm(BaseModel):
    items: list[dict]


# --- 倍率规则 ---
class MultiplierRuleIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    start_time: time
    end_time: time
    multiplier: Decimal
    venue_id: uuid.UUID | None = None
    weekdays: list[int] | None = None
    effective_start_date: date | None = None
    effective_end_date: date | None = None
    priority: int = 0
    is_active: bool = True


class MultiplierRuleOut(BaseModel):
    id: uuid.UUID
    name: str
    start_time: time
    end_time: time
    multiplier: Decimal
    venue_id: uuid.UUID | None
    weekdays: list[int] | None
    priority: int
    is_active: bool

    model_config = {"from_attributes": True}
