"""排班相关请求 / 响应。"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    seed: int = 42


class AssignmentView(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID | None
    person_name: str | None
    position_index: int
    plan_status: str
    execution_status: str
    credited_minutes: int


class SlotView(BaseModel):
    id: uuid.UUID
    venue_id: uuid.UUID
    source_type: str
    slot_start_at: datetime
    slot_end_at: datetime
    required_people: int
    month_key: str
    status: str
    is_locked: bool
    assignments: list[AssignmentView]


class WeekView(BaseModel):
    plan_id: uuid.UUID
    week_start: date
    week_end: date
    status: str
    revision: int
    slots: list[SlotView]
