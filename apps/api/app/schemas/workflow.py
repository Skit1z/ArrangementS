"""请假 / 换班 / 不可值班申请的请求 / 响应。"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import (
    LeaveStatus,
    RequestStatus,
    SwapCandidateStatus,
    SwapMode,
    SwapStatus,
)


# --- 不可值班申请 ---
class AvailabilityRequestIn(BaseModel):
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=1, max_length=255)
    recurrence_rule: str | None = None


class AvailabilityRequestOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    reason: str
    recurrence_rule: str | None
    status: RequestStatus

    model_config = {"from_attributes": True}


class AdminBlockIn(BaseModel):
    person_id: uuid.UUID
    start_at: datetime
    end_at: datetime
    reason: str | None = None


class ReviewIn(BaseModel):
    comment: str | None = None


# --- 请假 ---
class LeaveIn(BaseModel):
    assignment_id: uuid.UUID
    reason: str = Field(min_length=1, max_length=255)


class LeaveOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    applicant_person_id: uuid.UUID
    reason: str
    is_emergency: bool
    status: LeaveStatus

    model_config = {"from_attributes": True}


# --- 换班 ---
class SwapTargetedIn(BaseModel):
    assignment_id: uuid.UUID
    target_person_id: uuid.UUID
    reason: str | None = None


class SwapOpenIn(BaseModel):
    assignment_id: uuid.UUID
    reason: str | None = None


class SwapApproveIn(BaseModel):
    selected_person_id: uuid.UUID | None = None


class SwapCandidateOut(BaseModel):
    id: uuid.UUID
    candidate_person_id: uuid.UUID
    candidate_name: str | None = None
    status: SwapCandidateStatus

    model_config = {"from_attributes": True}


class SwapOut(BaseModel):
    id: uuid.UUID
    assignment_id: uuid.UUID
    requester_person_id: uuid.UUID
    mode: SwapMode
    target_person_id: uuid.UUID | None
    selected_person_id: uuid.UUID | None
    status: SwapStatus
    # Extra fields for UI:
    requester_name: str | None = None
    requester_phone: str | None = None
    venue_name: str | None = None
    slot_start_at: datetime | None = None
    slot_end_at: datetime | None = None
    candidates: list[SwapCandidateOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
