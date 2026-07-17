"""执行状态：班次完成、未到岗标记（方案 7.4 / 2.5）。

未到岗：实际完成工时改为 0，但排班平衡工时保留（绝不降低后续自动排班权重）。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ExecutionStatus, PlanAssignmentStatus
from app.models.schedule import Assignment, DutySlot
from app.services.audit_service import record_audit


def _get(db: Session, assignment_id: uuid.UUID) -> Assignment:
    a = db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="排班分配不存在")
    return a


def mark_completed(db: Session, *, actor_id: uuid.UUID | None, assignment_id: uuid.UUID) -> Assignment:
    a = _get(db, assignment_id)
    if a.person_id is None:
        raise HTTPException(status_code=422, detail="空缺岗位不能标记完成")
    a.execution_status = ExecutionStatus.completed
    db.flush()
    return a


def mark_absent(
    db: Session, *, actor_id: uuid.UUID | None, assignment_id: uuid.UUID,
    reason: str | None = None, ip: str | None = None, ua: str | None = None,
) -> Assignment:
    a = _get(db, assignment_id)
    if a.person_id is None:
        raise HTTPException(status_code=422, detail="空缺岗位不能标记未到岗")
    a.execution_status = ExecutionStatus.absent
    a.credited_minutes = 0  # 实际完成工时 0
    # balance_minutes 保持不变：未到岗不降低后续自动排班权重
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="assignment.mark_absent",
        entity_type="assignment", entity_id=a.id, reason=reason, ip_address=ip, user_agent=ua,
    )
    return a


def auto_complete_ended(db: Session, now: datetime | None = None) -> int:
    """定时任务：班次结束后自动将“待值班”置为“已完成”（方案 7.4）。"""
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
    for a, slot in rows:
        end = slot.slot_end_at.replace(tzinfo=timezone.utc) if slot.slot_end_at.tzinfo is None else slot.slot_end_at
        if end <= now:
            a.execution_status = ExecutionStatus.completed
            count += 1
    db.flush()
    return count
