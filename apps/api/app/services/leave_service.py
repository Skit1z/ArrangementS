"""请假流程（方案 6.1）。

审核通过后：原分配 -> 请假，岗位空缺；原人员实际完成工时 0、排班平衡工时不计入。
补位由手动/换班完成（补位人员获得工时）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, LeaveStatus, PlanAssignmentStatus, SlotStatus
from app.models.leave import LeaveRequest
from app.models.schedule import Assignment, DutySlot
from app.services.audit_service import record_audit

EMERGENCY_THRESHOLD = timedelta(hours=24)


def create_leave(
    db: Session,
    *,
    applicant_person_id: uuid.UUID,
    assignment_id: uuid.UUID,
    reason: str,
    is_admin: bool = False,
) -> LeaveRequest:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise HTTPException(status_code=404, detail="排班分配不存在")
    if not is_admin and assignment.person_id != applicant_person_id:
        raise HTTPException(status_code=403, detail="只能为本人排班申请请假")

    slot = db.get(DutySlot, assignment.duty_slot_id)
    now = datetime.now(timezone.utc)
    slot_start = slot.slot_start_at
    if slot_start.tzinfo is None:
        slot_start = slot_start.replace(tzinfo=timezone.utc)
    started = slot_start <= now
    if started and not is_admin:
        raise HTTPException(status_code=422, detail="班次已开始，普通用户不能提交请假")

    is_emergency = (slot_start - now) < EMERGENCY_THRESHOLD
    leave = LeaveRequest(
        assignment_id=assignment_id,
        applicant_person_id=applicant_person_id,
        reason=reason,
        is_emergency=is_emergency,
        status=LeaveStatus.pending,
    )
    db.add(leave)
    db.flush()
    return leave


def list_my_leaves(db: Session, person_id: uuid.UUID) -> list[LeaveRequest]:
    return list(
        db.scalars(
            select(LeaveRequest)
            .where(LeaveRequest.applicant_person_id == person_id)
            .order_by(LeaveRequest.created_at.desc())
        )
    )


def list_pending(db: Session) -> list[LeaveRequest]:
    return list(
        db.scalars(
            select(LeaveRequest).where(LeaveRequest.status == LeaveStatus.pending)
        )
    )


def withdraw(db: Session, person_id: uuid.UUID, leave_id: uuid.UUID) -> LeaveRequest:
    leave = _get(db, leave_id)
    if leave.applicant_person_id != person_id:
        raise HTTPException(status_code=403, detail="只能撤回本人申请")
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=422, detail="仅待审核申请可撤回")
    leave.status = LeaveStatus.withdrawn
    db.flush()
    return leave


def approve(db: Session, actor_id: uuid.UUID | None, leave_id: uuid.UUID, comment: str | None = None) -> LeaveRequest:
    leave = _get(db, leave_id)
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=422, detail="仅待审核申请可批准")
    assignment = db.get(Assignment, leave.assignment_id)

    # 原人员：实际完成 0、平衡工时不计入；岗位置为空缺
    assignment.execution_status = ExecutionStatus.leave
    assignment.plan_status = PlanAssignmentStatus.vacant
    assignment.credited_minutes = 0
    assignment.balance_minutes = 0
    assignment.weighted_minutes_before_round = Decimal(0)

    slot = db.get(DutySlot, assignment.duty_slot_id)
    slot.status = SlotStatus.open

    leave.status = LeaveStatus.approved
    leave.reviewer_id = actor_id
    leave.review_comment = comment
    leave.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="leave.approve",
        entity_type="leave_request", entity_id=leave.id,
        after_data={"assignment_id": str(leave.assignment_id)},
    )
    return leave


def reject(db: Session, actor_id: uuid.UUID | None, leave_id: uuid.UUID, comment: str | None = None) -> LeaveRequest:
    leave = _get(db, leave_id)
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=422, detail="仅待审核申请可拒绝")
    leave.status = LeaveStatus.rejected
    leave.reviewer_id = actor_id
    leave.review_comment = comment
    leave.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return leave


def _get(db: Session, leave_id: uuid.UUID) -> LeaveRequest:
    leave = db.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=404, detail="请假申请不存在")
    return leave
