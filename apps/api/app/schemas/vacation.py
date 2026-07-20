"""假期相关请求 / 响应。"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class VacationCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    start_date: date
    end_date: date
    semester_id: uuid.UUID | None = None
    yellow_shift_template_ids: list[uuid.UUID] | None = None
    required_people: int = 1


class VacationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    yellow_shift_template_ids: list[uuid.UUID] | None = None
    required_people: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class VacationOut(BaseModel):
    id: uuid.UUID
    name: str
    start_date: date
    end_date: date
    semester_id: uuid.UUID | None
    yellow_shift_template_ids: list[uuid.UUID] | None = None
    required_people: int
    is_active: bool

    model_config = {"from_attributes": True}


class AvailabilityInterval(BaseModel):
    start_at: datetime
    end_at: datetime


class SetAvailabilityRequest(BaseModel):
    person_id: uuid.UUID
    intervals: list[AvailabilityInterval]


class AvailabilityOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    notes: str | None = None

    model_config = {"from_attributes": True}
