"""学期相关请求 / 响应。"""
from __future__ import annotations

import uuid
from datetime import date, time

from pydantic import BaseModel, Field

from app.models.enums import BuildingType


class SemesterCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    first_monday: date
    week_count: int = Field(default=20, ge=18, le=22)
    is_current: bool = False
    course_buffer_enabled: bool = False
    course_buffer_minutes: int = 10


class SemesterUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    first_monday: date | None = None
    week_count: int | None = Field(default=None, ge=18, le=22)
    course_buffer_enabled: bool | None = None
    course_buffer_minutes: int | None = None


class SemesterOut(BaseModel):
    id: uuid.UUID
    name: str
    first_monday: date
    week_count: int
    is_current: bool
    course_buffer_enabled: bool
    course_buffer_minutes: int

    model_config = {"from_attributes": True}


class PeriodRuleOut(BaseModel):
    id: uuid.UUID
    period_group: str
    building_type: BuildingType
    start_time: time
    end_time: time
    is_active: bool

    model_config = {"from_attributes": True}


class BuildingRuleOut(BaseModel):
    id: uuid.UUID
    prefix: str
    building_type: BuildingType
    priority: int
    is_active: bool

    model_config = {"from_attributes": True}
