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

from app.models.enums import ExecutionStatus, LeaveStatus, PlanAssignmentStatus, SlotStatus, SwapStatus
from app.models.leave import LeaveRequest
from app.models.schedule import Assignment, DutySlot
from app.models.swap import SwapRequest
from app.services import multiplier_service
from app.services.audit_service import record_audit
from app.services.schedule_service import _assignment_hours, mark_plan_changed

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
    if assignment.person_id is None or assignment.plan_status in (
        PlanAssignmentStatus.vacant,
        PlanAssignmentStatus.replaced,
        PlanAssignmentStatus.cancelled,
    ):
        raise HTTPException(status_code=422, detail="该分配已取消、空缺或被替换，不能申请请假")
    if assignment.execution_status != ExecutionStatus.pending:
        raise HTTPException(status_code=422, detail="该分配已请假、换班或结束，不能申请请假")
    duplicate = db.scalar(
        select(LeaveRequest).where(
            LeaveRequest.assignment_id == assignment_id,
            LeaveRequest.status.in_((LeaveStatus.pending, LeaveStatus.approved)),
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="该分配已有待审核或已批准的请假申请")
    active_swap = db.scalar(
        select(SwapRequest).where(
            SwapRequest.assignment_id == assignment_id,
            SwapRequest.status.in_((
                SwapStatus.awaiting_target,
                SwapStatus.open_collecting,
                SwapStatus.pending_admin,
            )),
        )
    )
    if active_swap is not None:
        raise HTTPException(status_code=409, detail="该分配已有进行中的换班申请，不能同时请假")

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
            select(LeaveRequest).where(
                LeaveRequest.status.in_((LeaveStatus.pending, LeaveStatus.approved))
            )
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
    if assignment is None or assignment.person_id != leave.applicant_person_id:
        raise HTTPException(status_code=422, detail="原分配已变更，不能批准请假")
    if assignment.plan_status in (PlanAssignmentStatus.replaced, PlanAssignmentStatus.cancelled):
        raise HTTPException(status_code=422, detail="原分配已取消或换班，不能批准请假")
    if assignment.execution_status != ExecutionStatus.pending:
        raise HTTPException(status_code=422, detail="原分配状态已变化，不能批准请假")

    # 原人员：实际完成 0、平衡工时不计入；岗位置为空缺
    assignment.execution_status = ExecutionStatus.leave
    assignment.plan_status = PlanAssignmentStatus.vacant
    assignment.credited_minutes = 0
    assignment.balance_minutes = 0
    assignment.weighted_minutes_before_round = Decimal(0)

    slot = db.get(DutySlot, assignment.duty_slot_id)
    slot.status = SlotStatus.open
    mark_plan_changed(db, slot.plan)

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


def revoke_approval(
    db: Session, actor_id: uuid.UUID | None, leave_id: uuid.UUID, comment: str | None = None
) -> LeaveRequest:
    """管理员撤销已批准请假，并恢复仍属于申请人的原分配。"""
    leave = _get(db, leave_id)
    if leave.status != LeaveStatus.approved:
        raise HTTPException(status_code=422, detail="仅已批准请假可撤销批准")
    assignment = db.get(Assignment, leave.assignment_id)
    if assignment is None or assignment.person_id != leave.applicant_person_id:
        raise HTTPException(status_code=409, detail="原分配已被替换，无法撤销请假批准")
    if assignment.execution_status != ExecutionStatus.leave:
        raise HTTPException(status_code=409, detail="原分配执行状态已变化，无法撤销请假批准")
    slot = db.get(DutySlot, assignment.duty_slot_id)
    start = slot.slot_start_at.replace(tzinfo=timezone.utc) if slot.slot_start_at.tzinfo is None else slot.slot_start_at
    if start <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="班次已开始，不能撤销请假批准")

    raw, weighted, credited = _assignment_hours(slot, multiplier_service.load_engine_rules(db))
    assignment.plan_status = PlanAssignmentStatus.assigned
    assignment.execution_status = ExecutionStatus.pending
    assignment.raw_minutes = raw
    assignment.weighted_minutes_before_round = weighted
    assignment.credited_minutes = credited
    assignment.balance_minutes = credited
    assignment.version += 1
    slot.status = SlotStatus.filled
    mark_plan_changed(db, slot.plan)
    leave.status = LeaveStatus.cancelled
    leave.reviewer_id = actor_id
    leave.review_comment = comment
    leave.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="leave.revoke_approval",
        entity_type="leave_request", entity_id=leave.id,
        after_data={"assignment_id": str(leave.assignment_id)},
    )
    return leave


def expire_started(db: Session, now: datetime | None = None) -> int:
    """取消班次已开始但仍待审核的请假申请。"""
    now = now or datetime.now(timezone.utc)
    rows = list(
        db.scalars(
            select(LeaveRequest)
            .join(Assignment, LeaveRequest.assignment_id == Assignment.id)
            .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
            .where(LeaveRequest.status == LeaveStatus.pending, DutySlot.slot_start_at <= now)
        )
    )
    for leave in rows:
        leave.status = LeaveStatus.cancelled
        leave.review_comment = "班次已开始，系统自动关闭"
        leave.reviewed_at = now
    db.flush()
    return len(rows)


def _get(db: Session, leave_id: uuid.UUID) -> LeaveRequest:
    leave = db.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=404, detail="请假申请不存在")
    return leave
