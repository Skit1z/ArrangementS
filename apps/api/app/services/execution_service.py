"""执行状态：班次完成、未到岗标记（方案 7.4 / 2.5）。

未到岗：实际完成工时改为 0，但排班平衡工时保留（绝不降低后续自动排班权重）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    ExecutionStatus,
    PlanAssignmentStatus,
    SlotSourceType,
    TaskStatus,
)
from app.models.schedule import Assignment, DutySlot
from app.models.venue_task import VenueTask
from app.services.audit_service import record_audit


def _get(db: Session, assignment_id: uuid.UUID) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="排班分配不存在")
    return a


def mark_completed(db: Session, *, actor_id: uuid.UUID | None, assignment_id: uuid.UUID) -> Assignment:
    a = _get(db, assignment_id)
    if (
        a.person_id is None
        or a.plan_status != PlanAssignmentStatus.assigned
        or a.execution_status != ExecutionStatus.pending
    ):
        raise HTTPException(status_code=422, detail="仅待执行的有效分配可标记完成")
    a.execution_status = ExecutionStatus.completed
    db.flush()
    slot = db.get(DutySlot, a.duty_slot_id)
    if slot.source_type == SlotSourceType.venue_task and slot.source_id is not None:
        _maybe_complete_task(db, slot.source_id)
    record_audit(
        db, actor_user_id=actor_id, action="assignment.mark_completed",
        entity_type="assignment", entity_id=a.id,
    )
    return a


def mark_absent(
    db: Session, *, actor_id: uuid.UUID | None, assignment_id: uuid.UUID,
    reason: str | None = None, ip: str | None = None, ua: str | None = None,
) -> Assignment:
    a = _get(db, assignment_id)
    if (
        a.person_id is None
        or a.plan_status != PlanAssignmentStatus.assigned
        or a.execution_status != ExecutionStatus.pending
    ):
        raise HTTPException(status_code=422, detail="仅待执行的有效分配可标记未到岗")
    a.execution_status = ExecutionStatus.absent
    a.credited_minutes = 0  # 实际完成工时 0
    # balance_minutes 保持不变：未到岗不降低后续自动排班权重
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="assignment.mark_absent",
        entity_type="assignment", entity_id=a.id, reason=reason, ip_address=ip, user_agent=ua,
    )
    slot = db.get(DutySlot, a.duty_slot_id)
    if slot.source_type == SlotSourceType.venue_task and slot.source_id is not None:
        _maybe_complete_task(db, slot.source_id)
    return a


def auto_complete_ended(db: Session, now: datetime | None = None) -> int:
    """定时任务：班次结束后自动将“待值班”置为“已完成”（方案 7.4）。

    若班次关联 ``VenueTask``（蓝厅/报告厅任务），且该任务所有分配均已完成，
    则同步把任务从 executing 推进到 completed。
    """
    now = now or datetime.now(timezone.utc)
    rows = db.execute(
        select(Assignment, DutySlot)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(
            Assignment.execution_status == ExecutionStatus.pending,
            Assignment.plan_status == PlanAssignmentStatus.assigned,
            Assignment.person_id.isnot(None),
        )
    ).all()
    count = 0
    affected_task_ids: set[uuid.UUID] = set()
    for a, slot in rows:
        end = slot.slot_end_at.replace(tzinfo=timezone.utc) if slot.slot_end_at.tzinfo is None else slot.slot_end_at
        if end <= now:
            a.execution_status = ExecutionStatus.completed
            count += 1
            if slot.source_type == SlotSourceType.venue_task and slot.source_id is not None:
                affected_task_ids.add(slot.source_id)
    # 先把 assignment 的内存改动写库，_maybe_complete_task 的查询才能看到最新状态
    db.flush()
    for task_id in affected_task_ids:
        _maybe_complete_task(db, task_id)
    db.flush()
    return count


def _maybe_complete_task(db: Session, task_id: uuid.UUID) -> None:
    """若该任务的所有 assigned 分配都已终结，则同步完成任务。"""
    task = db.get(VenueTask, task_id)
    if task is None or task.status not in (TaskStatus.scheduled, TaskStatus.executing):
        return
    slot_ids = [
        sid for (sid,) in db.execute(
            select(DutySlot.id).where(
                DutySlot.source_type == SlotSourceType.venue_task,
                DutySlot.source_id == task_id,
            )
        )
    ]
    if not slot_ids:
        return
    pending = db.scalar(
        select(Assignment).where(
            Assignment.duty_slot_id.in_(slot_ids),
            Assignment.plan_status == PlanAssignmentStatus.assigned,
            Assignment.execution_status.notin_((ExecutionStatus.completed, ExecutionStatus.absent)),
        ).limit(1)
    )
    if pending is None:
        task.status = TaskStatus.completed
        task.version += 1
