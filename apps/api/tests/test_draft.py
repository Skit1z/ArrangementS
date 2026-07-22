"""拖拽草稿保存测试（方案 9.5）。"""

from __future__ import annotations

from datetime import date, datetime, time

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import hash_password
from app.models.availability import AvailabilityBlock
from app.models.enums import (
    AssignmentSource,
    AvailabilitySource,
    AvailabilityStatus,
    PersonStatus,
    PlanAssignmentStatus,
    UserRole,
    VenueType,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot
from app.models.user import User
from app.models.venue import ShiftTemplate, Venue
from app.services import draft_service, schedule_service

MONDAY = date(2026, 3, 2)


def _yellow(db, templates=2):
    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db.add(v)
    db.flush()
    specs = [("第1班", time(8, 0), time(10, 0)), ("第2班", time(10, 0), time(12, 0))]
    for i, (n, s, e) in enumerate(specs[:templates]):
        db.add(
            ShiftTemplate(
                venue_id=v.id,
                name=n,
                start_time=s,
                end_time=e,
                credited_minutes=120,
                weekday_required_people=2,
                weekend_required_people=1,
                sort_order=i,
            )
        )
    db.flush()
    return v


def _person(db, i):
    u = User(username=f"d{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no=f"d{i}",
        class_name="一班",
        full_name=f"人{i}",
        phone="13800000000",
        status=PersonStatus.active,
        is_in_scheduling_pool=True,
    )
    db.add(p)
    db.flush()
    return p


def _setup(db, templates=1, people=4):
    _yellow(db, templates)
    ps = [_person(db, i) for i in range(people)]
    db.commit()
    schedule_service.generate(db, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    db.commit()
    return ps


def _monday_slots(db):
    slots = list(db.scalars(select(DutySlot).order_by(DutySlot.slot_start_at)))
    return [s for s in slots if s.slot_start_at.date() == MONDAY]


def test_unassign_then_assign(db_session):
    ps = _setup(db_session, templates=1)
    slot = _monday_slots(db_session)[0]
    plan = schedule_service.get_plan(db_session, MONDAY)
    v = plan.version

    draft_service.apply_operations(
        db_session,
        week_start=MONDAY,
        expected_version=v,
        operations=[{"op": "unassign", "slot_id": str(slot.id), "position_index": 0}],
        actor_id=None,
    )
    db_session.commit()
    a = db_session.scalar(
        select(Assignment).where(Assignment.duty_slot_id == slot.id, Assignment.position_index == 0)
    )
    assert a.person_id is None
    assert a.plan_status == PlanAssignmentStatus.vacant

    plan = schedule_service.get_plan(db_session, MONDAY)
    draft_service.apply_operations(
        db_session,
        week_start=MONDAY,
        expected_version=plan.version,
        operations=[
            {
                "op": "assign",
                "slot_id": str(slot.id),
                "position_index": 0,
                "person_id": str(ps[0].id),
            }
        ],
        actor_id=None,
    )
    db_session.commit()
    db_session.refresh(a)
    assert a.person_id == ps[0].id
    assert a.assignment_source == AssignmentSource.manual
    assert a.credited_minutes == 120


def test_optimistic_lock_conflict(db_session):
    _setup(db_session, templates=1)
    slot = _monday_slots(db_session)[0]
    with pytest.raises(HTTPException) as ei:
        draft_service.apply_operations(
            db_session,
            week_start=MONDAY,
            expected_version=999,
            operations=[{"op": "unassign", "slot_id": str(slot.id), "position_index": 0}],
            actor_id=None,
        )
    assert ei.value.status_code == 409


def test_time_overlap_never_allowed_even_forced(db_session):
    ps = _setup(db_session, templates=2, people=4)
    slots = _monday_slots(db_session)
    s1, s2 = slots[0], slots[1]  # 08:00-10:00 与 10:00-12:00 不重叠

    # 构造重叠：把 s2 的时间改为与 s1 重叠
    s2.slot_start_at = datetime(2026, 3, 2, 9, 0)
    s2.slot_end_at = datetime(2026, 3, 2, 11, 0)
    db_session.flush()

    # 让某人占据 s1 位置0
    plan = schedule_service.get_plan(db_session, MONDAY)
    draft_service.apply_operations(
        db_session,
        week_start=MONDAY,
        expected_version=plan.version,
        operations=[
            {"op": "assign", "slot_id": str(s1.id), "position_index": 0, "person_id": str(ps[0].id)}
        ],
        actor_id=None,
    )
    db_session.commit()

    # 同一人排到重叠的 s2 —— 即使 forced 也必须拒绝
    plan = schedule_service.get_plan(db_session, MONDAY)
    with pytest.raises(HTTPException) as ei:
        draft_service.apply_operations(
            db_session,
            week_start=MONDAY,
            expected_version=plan.version,
            operations=[
                {
                    "op": "assign",
                    "slot_id": str(s2.id),
                    "position_index": 0,
                    "person_id": str(ps[0].id),
                    "forced": True,
                    "forced_reason": "就要他",
                }
            ],
            actor_id=None,
        )
    assert ei.value.status_code == 422
    assert "时间重叠" in ei.value.detail


def test_hard_constraint_requires_forced_with_reason(db_session):
    ps = _setup(db_session, templates=1, people=4)
    slot = _monday_slots(db_session)[0]
    # p0 该时段有课
    db_session.add(
        AvailabilityBlock(
            person_id=ps[0].id,
            source=AvailabilitySource.course,
            start_at=slot.slot_start_at,
            end_at=slot.slot_end_at,
            status=AvailabilityStatus.active,
        )
    )
    # 先清空该岗位
    plan = schedule_service.get_plan(db_session, MONDAY)
    draft_service.apply_operations(
        db_session,
        week_start=MONDAY,
        expected_version=plan.version,
        operations=[
            {"op": "unassign", "slot_id": str(slot.id), "position_index": 0},
            {"op": "unassign", "slot_id": str(slot.id), "position_index": 1},
        ],
        actor_id=None,
    )
    db_session.commit()

    # 不带 forced -> 拒绝
    plan = schedule_service.get_plan(db_session, MONDAY)
    with pytest.raises(HTTPException) as ei:
        draft_service.apply_operations(
            db_session,
            week_start=MONDAY,
            expected_version=plan.version,
            operations=[
                {
                    "op": "assign",
                    "slot_id": str(slot.id),
                    "position_index": 0,
                    "person_id": str(ps[0].id),
                }
            ],
            actor_id=None,
        )
    assert ei.value.status_code == 422

    # forced 但无原因 -> 拒绝
    plan = schedule_service.get_plan(db_session, MONDAY)
    with pytest.raises(HTTPException) as ei2:
        draft_service.apply_operations(
            db_session,
            week_start=MONDAY,
            expected_version=plan.version,
            operations=[
                {
                    "op": "assign",
                    "slot_id": str(slot.id),
                    "position_index": 0,
                    "person_id": str(ps[0].id),
                    "forced": True,
                    "forced_reason": "",
                }
            ],
            actor_id=None,
        )
    assert ei2.value.status_code == 422

    # forced + 原因 -> 允许，并写审计
    plan = schedule_service.get_plan(db_session, MONDAY)
    draft_service.apply_operations(
        db_session,
        week_start=MONDAY,
        expected_version=plan.version,
        operations=[
            {
                "op": "assign",
                "slot_id": str(slot.id),
                "position_index": 0,
                "person_id": str(ps[0].id),
                "forced": True,
                "forced_reason": "人手不足",
            }
        ],
        actor_id=None,
    )
    db_session.commit()
    a = db_session.scalar(
        select(Assignment).where(Assignment.duty_slot_id == slot.id, Assignment.position_index == 0)
    )
    assert a.person_id == ps[0].id
    assert a.assignment_source == AssignmentSource.forced
    assert a.forced_reason == "人手不足"

    from app.models.audit import AuditLog

    logs = list(db_session.scalars(select(AuditLog).where(AuditLog.action == "assignment.force")))
    assert len(logs) == 1


def test_same_person_twice_in_one_slot_rejected(db_session):
    ps = _setup(db_session, templates=1, people=4)
    slot = _monday_slots(db_session)[0]
    plan = schedule_service.get_plan(db_session, MONDAY)
    draft_service.apply_operations(
        db_session,
        week_start=MONDAY,
        expected_version=plan.version,
        operations=[
            {
                "op": "assign",
                "slot_id": str(slot.id),
                "position_index": 0,
                "person_id": str(ps[0].id),
            }
        ],
        actor_id=None,
    )
    db_session.commit()
    plan = schedule_service.get_plan(db_session, MONDAY)
    with pytest.raises(HTTPException) as ei:
        draft_service.apply_operations(
            db_session,
            week_start=MONDAY,
            expected_version=plan.version,
            operations=[
                {
                    "op": "assign",
                    "slot_id": str(slot.id),
                    "position_index": 1,
                    "person_id": str(ps[0].id),
                }
            ],
            actor_id=None,
        )
    assert ei.value.status_code == 422


def test_validate_reports_vacancy(db_session):
    _setup(db_session, templates=1, people=4)
    slot = _monday_slots(db_session)[0]
    plan = schedule_service.get_plan(db_session, MONDAY)
    draft_service.apply_operations(
        db_session,
        week_start=MONDAY,
        expected_version=plan.version,
        operations=[{"op": "unassign", "slot_id": str(slot.id), "position_index": 0}],
        actor_id=None,
    )
    db_session.commit()
    conflicts = draft_service.validate_week(db_session, MONDAY)
    vac = [c for c in conflicts if c.kind == "vacancy" and c.slot_id == str(slot.id)]
    assert len(vac) == 1


def test_candidates_flags_overlap_and_sorted(db_session):
    ps = _setup(db_session, templates=1, people=4)
    slot = _monday_slots(db_session)[0]
    cands = draft_service.list_candidates(db_session, slot.id)
    assert len(cands) == 4
    # 已排在本岗位的人对该岗位应标记时间重叠（其自身分配即占用该时段）
    assigned_ids = {
        str(a.person_id)
        for a in db_session.scalars(
            select(Assignment).where(
                Assignment.duty_slot_id == slot.id, Assignment.person_id.isnot(None)
            )
        )
    }
    for c in cands:
        if c["person_id"] in assigned_ids:
            assert c["time_overlap"] is True
    del ps


def test_week_people_returns_unavailable_slots(db_session):
    ps = _setup(db_session, templates=1, people=3)
    slot = _monday_slots(db_session)[0]
    db_session.add(
        AvailabilityBlock(
            person_id=ps[0].id,
            source=AvailabilitySource.course,
            start_at=slot.slot_start_at,
            end_at=slot.slot_end_at,
            status=AvailabilityStatus.active,
        )
    )
    db_session.commit()

    rows = draft_service.week_people(db_session, MONDAY)
    assert len(rows) == 3
    me = next(r for r in rows if r["person_id"] == str(ps[0].id))
    assert str(slot.id) in me["unavailable_slot_ids"]
    other = next(r for r in rows if r["person_id"] == str(ps[1].id))
    assert str(slot.id) not in other["unavailable_slot_ids"]


def test_draft_invalid_operations_raises_422(db_session):
    _setup(db_session, templates=1, people=2)
    plan = schedule_service.get_plan(db_session, MONDAY)
    with pytest.raises(HTTPException) as ei:
        draft_service.apply_operations(
            db_session,
            week_start=MONDAY,
            expected_version=plan.version,
            operations=[
                {"op": "assign", "slot_id": "invalid-uuid", "position_index": 0, "person_id": None}
            ],
            actor_id=None,
        )
    assert ei.value.status_code == 422
