"""普通用户自助视图：我的排班、我的工时（方案 10.2 / 10.7）。

普通用户只能看到已发布计划中的本人排班；同班/前班/后班人员展示
``full_name`` + ``class_name`` + ``phone``（供移动端展示联系电话），
绝不返回身份证号、银行卡号、困难等级等敏感字段。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import PlanAssignmentStatus, PlanStatus
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.models.venue import Venue

VISIBLE_PLAN_STATUSES = (PlanAssignmentStatus.assigned, PlanAssignmentStatus.pending)


def my_assignments(
    db: Session, person_id: uuid.UUID, *, start: date | None = None, end: date | None = None
) -> list[dict]:
    stmt = (
        select(Assignment, DutySlot, Venue, WeeklyPlan)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .join(Venue, DutySlot.venue_id == Venue.id)
        .join(WeeklyPlan, DutySlot.weekly_plan_id == WeeklyPlan.id)
        .where(
            Assignment.person_id == person_id,
            Assignment.plan_status.in_(VISIBLE_PLAN_STATUSES),
            WeeklyPlan.status == PlanStatus.published,  # 仅已发布
        )
        .order_by(DutySlot.slot_start_at)
    )
    if start is not None:
        stmt = stmt.where(WeeklyPlan.week_end >= start)
    if end is not None:
        stmt = stmt.where(WeeklyPlan.week_start <= end)

    rows = db.execute(stmt).all()
    out: list[dict] = []
    for a, slot, venue, _plan in rows:
        out.append(
            {
                "assignment_id": str(a.id),
                "slot_id": str(slot.id),
                "venue_name": venue.name,
                "slot_start_at": slot.slot_start_at.isoformat(),
                "slot_end_at": slot.slot_end_at.isoformat(),
                "credited_minutes": a.credited_minutes,
                "plan_status": a.plan_status.value,
                "execution_status": a.execution_status.value,
                "teammates": _teammates(db, slot.id, person_id),
                "previous_shift": _adjacent_shift_people(
                    db, venue.id, slot.slot_start_at, find_next=False
                ),
                "next_shift": _adjacent_shift_people(
                    db, venue.id, slot.slot_end_at, find_next=True
                ),
            }
        )
    return out


def _teammates(db: Session, slot_id: uuid.UUID, exclude_person_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        select(Assignment, PersonProfile)
        .join(PersonProfile, Assignment.person_id == PersonProfile.id)
        .where(
            Assignment.duty_slot_id == slot_id,
            Assignment.person_id != exclude_person_id,
            Assignment.plan_status.in_(VISIBLE_PLAN_STATUSES),
        )
    ).all()
    return [
        {"full_name": p.full_name, "class_name": p.class_name, "phone": p.phone} for _a, p in rows
    ]


def _adjacent_shift_people(
    db: Session, venue_id: uuid.UUID, reference_time: datetime, find_next: bool
) -> list[dict]:
    """查找同场地的前/后一班已发布班次的在岗人员。

    只看 ``WeeklyPlan.status == published`` 的班次，避免泄露草稿计划中的人员安排。
    """
    boundary = DutySlot.slot_start_at if find_next else DutySlot.slot_end_at
    stmt = (
        select(DutySlot)
        .join(WeeklyPlan, DutySlot.weekly_plan_id == WeeklyPlan.id)
        .where(
            DutySlot.venue_id == venue_id,
            WeeklyPlan.status == PlanStatus.published,  # 仅已发布计划
            boundary >= reference_time if find_next else boundary <= reference_time,
        )
        .order_by(DutySlot.slot_start_at.asc() if find_next else DutySlot.slot_end_at.desc())
        .limit(1)
    )
    slot = db.scalar(stmt)
    if slot is None:
        return []

    rows = db.execute(
        select(PersonProfile)
        .join(Assignment, Assignment.person_id == PersonProfile.id)
        .where(
            Assignment.duty_slot_id == slot.id,
            Assignment.plan_status.in_(VISIBLE_PLAN_STATUSES),
        )
    ).all()
    return [{"full_name": p.full_name, "class_name": p.class_name, "phone": p.phone} for p in rows]


def next_duty(db: Session, person_id: uuid.UUID) -> dict | None:
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Assignment, DutySlot, Venue)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .join(Venue, DutySlot.venue_id == Venue.id)
        .join(WeeklyPlan, DutySlot.weekly_plan_id == WeeklyPlan.id)
        .where(
            Assignment.person_id == person_id,
            WeeklyPlan.status == PlanStatus.published,
            Assignment.plan_status.in_(VISIBLE_PLAN_STATUSES),
        )
        .order_by(DutySlot.slot_start_at)
    ).all()
    for a, slot, venue in rows:
        start = slot.slot_start_at
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if start >= now:
            return {
                "assignment_id": str(a.id),
                "venue_name": venue.name,
                "slot_start_at": slot.slot_start_at.isoformat(),
                "slot_end_at": slot.slot_end_at.isoformat(),
                "teammates": _teammates(db, slot.id, person_id),
                "previous_shift": _adjacent_shift_people(
                    db, venue.id, slot.slot_start_at, find_next=False
                ),
                "next_shift": _adjacent_shift_people(
                    db, venue.id, slot.slot_end_at, find_next=True
                ),
            }
    return None


def get_current_on_duty_staff(db: Session) -> list[dict]:
    """获取当前时刻正处于在岗值班状态的人员及其联系电话。"""
    now = datetime.now(timezone.utc)

    stmt = (
        select(Assignment, DutySlot, Venue, PersonProfile)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .join(Venue, DutySlot.venue_id == Venue.id)
        .join(PersonProfile, Assignment.person_id == PersonProfile.id)
        .join(WeeklyPlan, DutySlot.weekly_plan_id == WeeklyPlan.id)
        .where(
            WeeklyPlan.status == PlanStatus.published,
            Assignment.plan_status.in_(VISIBLE_PLAN_STATUSES),
        )
        .order_by(Venue.sort_order, DutySlot.slot_start_at)
    )

    rows = db.execute(stmt).all()

    current_items: list[dict] = []
    for a, slot, venue, person in rows:
        s_start = slot.slot_start_at
        if s_start.tzinfo is None:
            s_start = s_start.replace(tzinfo=timezone.utc)
        s_end = slot.slot_end_at
        if s_end.tzinfo is None:
            s_end = s_end.replace(tzinfo=timezone.utc)

        if s_start <= now <= s_end:
            current_items.append(
                {
                    "assignment_id": str(a.id),
                    "slot_id": str(slot.id),
                    "venue_id": str(venue.id),
                    "venue_name": venue.name,
                    "slot_start_at": slot.slot_start_at.isoformat(),
                    "slot_end_at": slot.slot_end_at.isoformat(),
                    "person_id": str(person.id),
                    "full_name": person.full_name,
                    "class_name": person.class_name,
                    "phone": person.phone,
                }
            )

    return current_items
