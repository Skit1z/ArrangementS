"""排班相关请求 / 响应。"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    seed: int = 42


class DraftOperation(BaseModel):
    op: str  # assign | unassign
    slot_id: uuid.UUID
    position_index: int
    person_id: uuid.UUID | None = None
    forced: bool = False
    forced_reason: str | None = None


class DraftSaveRequest(BaseModel):
    version: int
    operations: list[DraftOperation]


class ConflictOut(BaseModel):
    slot_id: str
    position_index: int
    person_id: str | None
    kind: str
    message: str


class CandidateOut(BaseModel):
    person_id: str
    full_name: str
    class_name: str
    student_no: str
    month_balance_minutes: int
    week_shift_count: int
    in_scheduling_pool: bool
    time_overlap: bool
    available: bool
    reasons: list[str]


class WeekPersonOut(BaseModel):
    person_id: str
    full_name: str
    class_name: str
    student_no: str
    month_balance_minutes: int
    week_shift_count: int
    in_scheduling_pool: bool
    unavailable_slot_ids: list[str]


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
    version: int
    week_label: str | None = None
    slots: list[SlotView]
