"""换班：指定人员换班与公开征集替班（方案 6.2）。

admin 最终审核；审核时重新校验时间冲突/课程冲突/不可值班/场地限制/每周上限/暂停/禁止搭档/
班次是否已开始；通过后原子化转移，工时归最终承担人员，其他公开报名自动失效。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    AssignmentSource,
    ExecutionStatus,
    PlanAssignmentStatus,
    SlotStatus,
    SwapCandidateStatus,
    SwapMode,
    SwapStatus,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot
from app.models.swap import SwapCandidate, SwapRequest
from app.scheduling import eligibility
from app.services import multiplier_service
from app.services.audit_service import record_audit
from app.services.schedule_service import _assignment_hours


def _owned_assignment(db: Session, person_id: uuid.UUID, assignment_id: uuid.UUID) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="排班分配不存在")
    if a.person_id != person_id:
        raise HTTPException(status_code=403, detail="只能换本人的班次")
    return a


def create_targeted(db, *, requester_person_id, assignment_id, target_person_id, reason=None) -> SwapRequest:
    _owned_assignment(db, requester_person_id, assignment_id)
    if target_person_id == requester_person_id:
        raise HTTPException(status_code=422, detail="不能指定自己")
    if db.get(PersonProfile, target_person_id) is None:
        raise HTTPException(status_code=404, detail="接替人员不存在")
    swap = SwapRequest(
        assignment_id=assignment_id, requester_person_id=requester_person_id,
        mode=SwapMode.targeted, target_person_id=target_person_id, reason=reason,
        status=SwapStatus.awaiting_target,
    )
    db.add(swap)
    db.flush()
    return swap


def create_open(db, *, requester_person_id, assignment_id, reason=None) -> SwapRequest:
    _owned_assignment(db, requester_person_id, assignment_id)
    swap = SwapRequest(
        assignment_id=assignment_id, requester_person_id=requester_person_id,
        mode=SwapMode.open, reason=reason, status=SwapStatus.open_collecting,
    )
    db.add(swap)
    db.flush()
    return swap


def respond_target(db, *, target_person_id, swap_id, accept: bool) -> SwapRequest:
    swap = _get(db, swap_id)
    if swap.mode != SwapMode.targeted or swap.status != SwapStatus.awaiting_target:
        raise HTTPException(status_code=422, detail="当前状态不可响应")
    if swap.target_person_id != target_person_id:
        raise HTTPException(status_code=403, detail="非被指定人员")
    if accept:
        swap.selected_person_id = target_person_id
        swap.status = SwapStatus.pending_admin
    else:
        swap.status = SwapStatus.rejected
    db.flush()
    return swap


def apply_open(db, *, candidate_person_id, swap_id) -> SwapCandidate:
    swap = _get(db, swap_id)
    if swap.mode != SwapMode.open or swap.status != SwapStatus.open_collecting:
        raise HTTPException(status_code=422, detail="该替班未在公开征集")
    if candidate_person_id == swap.requester_person_id:
        raise HTTPException(status_code=422, detail="不能给自己报名")
    exists = db.scalar(
        select(SwapCandidate).where(
            SwapCandidate.swap_request_id == swap_id,
            SwapCandidate.candidate_person_id == candidate_person_id,
        )
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="已报名")
    cand = SwapCandidate(swap_request_id=swap_id, candidate_person_id=candidate_person_id)
    db.add(cand)
    db.flush()
    return cand


def withdraw(db, *, requester_person_id, swap_id) -> SwapRequest:
    swap = _get(db, swap_id)
    if swap.requester_person_id != requester_person_id:
        raise HTTPException(status_code=403, detail="只能撤回本人发起的换班")
    if swap.status in (SwapStatus.approved, SwapStatus.rejected):
        raise HTTPException(status_code=422, detail="已结束的换班不可撤回")
    swap.status = SwapStatus.withdrawn
    db.flush()
    return swap


def admin_approve(
    db, *, actor_id, swap_id, selected_person_id: uuid.UUID | None = None
) -> SwapRequest:
    swap = _get(db, swap_id)
    if swap.status not in (SwapStatus.pending_admin, SwapStatus.open_collecting):
        raise HTTPException(status_code=422, detail="当前状态不可审核")

    final_person_id = selected_person_id or swap.selected_person_id or swap.target_person_id
    if final_person_id is None:
        raise HTTPException(status_code=422, detail="需指定最终接替人员")
    person = db.get(PersonProfile, final_person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="接替人员不存在")

    assignment = db.get(Assignment, swap.assignment_id)
    slot = db.get(DutySlot, assignment.duty_slot_id)

    # 班次是否已开始
    now = datetime.now(timezone.utc)
    start = slot.slot_start_at.replace(tzinfo=timezone.utc) if slot.slot_start_at.tzinfo is None else slot.slot_start_at
    if start <= now:
        raise HTTPException(status_code=422, detail="班次已开始，不可换班")

    # 重新校验硬约束
    if not eligibility.check_person_available_for_slot(db, person, slot):
        raise HTTPException(status_code=422, detail="接替人员存在课程/不可值班/场地等硬冲突")
    if eligibility.has_time_overlap_with_person(db, person.id, slot, exclude_assignment_id=assignment.id):
        raise HTTPException(status_code=422, detail="接替人员在该时间已有排班，时间重叠")

    # 原子转移：工时归最终承担人员
    before = {"person_id": str(assignment.person_id)}
    engine_rules = multiplier_service.load_engine_rules(db)
    raw, weighted, credited = _assignment_hours(slot, engine_rules)
    assignment.person_id = person.id
    assignment.assignment_source = AssignmentSource.swap
    assignment.plan_status = PlanAssignmentStatus.assigned
    assignment.execution_status = ExecutionStatus.pending
    assignment.raw_minutes = raw
    assignment.weighted_minutes_before_round = weighted
    assignment.credited_minutes = credited
    assignment.balance_minutes = credited
    assignment.version += 1
    slot.status = SlotStatus.filled

    swap.selected_person_id = person.id
    swap.status = SwapStatus.approved
    swap.reviewer_id = actor_id
    swap.reviewed_at = now

    # 公开征集中的其他报名自动失效
    for cand in swap.candidates:
        cand.status = (
            SwapCandidateStatus.selected
            if cand.candidate_person_id == person.id
            else SwapCandidateStatus.expired
        )

    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="swap.approve",
        entity_type="swap_request", entity_id=swap.id,
        before_data=before, after_data={"person_id": str(person.id)},
    )
    return swap


def admin_reject(db, *, actor_id, swap_id, comment=None) -> SwapRequest:
    swap = _get(db, swap_id)
    swap.status = SwapStatus.rejected
    swap.reviewer_id = actor_id
    swap.review_comment = comment
    swap.reviewed_at = datetime.now(timezone.utc)
    db.flush()
    return swap


def list_open(db) -> list[SwapRequest]:
    return list(db.scalars(select(SwapRequest).where(SwapRequest.status == SwapStatus.open_collecting)))


def list_my(db, person_id) -> list[SwapRequest]:
    return list(
        db.scalars(
            select(SwapRequest)
            .where(SwapRequest.requester_person_id == person_id)
            .order_by(SwapRequest.created_at.desc())
        )
    )


def list_invitations(db, person_id) -> list[SwapRequest]:
    return list(
        db.scalars(
            select(SwapRequest).where(
                SwapRequest.mode == SwapMode.targeted,
                SwapRequest.target_person_id == person_id,
                SwapRequest.status == SwapStatus.awaiting_target,
            )
        )
    )


def _get(db, swap_id) -> SwapRequest:
    swap = db.get(SwapRequest, swap_id)
    if swap is None:
        raise HTTPException(status_code=404, detail="换班申请不存在")
    return swap
