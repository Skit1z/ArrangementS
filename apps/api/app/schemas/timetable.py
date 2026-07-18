"""课表相关请求 / 响应。"""
from __future__ import annotations

import uuid
from datetime import time

from pydantic import BaseModel, Field

from app.models.enums import BuildingType, ParseStatus, ReviewStatus


class RawEntryIn(BaseModel):
    weekday: int = Field(ge=1, le=7)
    period_start: int = Field(ge=1, le=14)
    period_end: int = Field(ge=1, le=14)
    week_expr: str = Field(min_length=1, max_length=64)
    location_code: str | None = None
    course_name: str | None = None
    confidence: float | None = None


class TimetableUploadIn(BaseModel):
    semester_id: uuid.UUID
    person_id: uuid.UUID | None = None  # admin 代传时指定；普通用户忽略
    file_name: str = "timetable.pdf"
    entries: list[RawEntryIn]


class CourseRuleOut(BaseModel):
    id: uuid.UUID
    course_name: str | None
    weekday: int
    period_start: int
    period_end: int
    week_start: int | None
    week_end: int | None
    week_parity: str
    explicit_weeks: list[int] | None
    location_code: str | None
    building_type: BuildingType | None
    start_time: time | None
    end_time: time | None
    needs_review: bool

    model_config = {"from_attributes": True}


class CourseRulePatch(BaseModel):
    course_name: str | None = None
    weekday: int | None = Field(default=None, ge=1, le=7)
    period_start: int | None = Field(default=None, ge=1, le=14)
    period_end: int | None = Field(default=None, ge=1, le=14)
    week_expr: str | None = None
    location_code: str | None = None
    needs_review: bool | None = None


class TimetablePreviewOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    semester_id: uuid.UUID
    file_name: str
    parse_status: ParseStatus
    review_status: ReviewStatus
    rules: list[CourseRuleOut]

    model_config = {"from_attributes": True}

class ActiveTimetableOut(BaseModel):
    person_id: uuid.UUID
    person_name: str
    rules: list[CourseRuleOut]

    model_config = {"from_attributes": True}
