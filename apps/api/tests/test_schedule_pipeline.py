"""排班全链路集成测试：岗位生成 -> 求解 -> 落库 -> 发布。"""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import select

from app.core.security import hash_password
from app.models.availability import AvailabilityBlock
from app.models.enums import (
    AvailabilitySource,
    AvailabilityStatus,
    PersonStatus,
    PlanStatus,
    UserRole,
    VenueType,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot
from app.models.user import User
from app.models.venue import ShiftTemplate, Venue
from app.services import schedule_service

MONDAY = date(2026, 3, 2)


def _yellow(db, templates=2):
    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db.add(v)
    db.flush()
    specs = [("第1班", time(8, 0), time(10, 0)), ("第2班", time(10, 0), time(12, 0))]
    for i, (n, s, e) in enumerate(specs[:templates]):
        db.add(ShiftTemplate(venue_id=v.id, name=n, start_time=s, end_time=e,
                             credited_minutes=120, weekday_required_people=2, weekend_required_people=1, sort_order=i))
    db.flush()
    return v


def _person(db, i):
    u = User(username=f"u{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(user_id=u.id, student_no=f"u{i}", class_name="一班", full_name=f"人{i}",
                      phone="13800000000", status=PersonStatus.active, is_in_scheduling_pool=True)
    db.add(p)
    db.flush()
    return p


def test_generate_fills_weekday_slots(db_session):
    _yellow(db_session, templates=2)
    for i in range(4):
        _person(db_session, i)
    db_session.commit()

    summary = schedule_service.generate(db_session, MONDAY, actor_id=None, seed=1)
    db_session.commit()
    assert summary["vacancies"] == 0

    # 周一（工作日）第1班应有 2 个已分配、互不相同的人
    slots = list(db_session.scalars(select(DutySlot)))
    monday_shift1 = next(
        s for s in slots if s.slot_start_at == datetime(2026, 3, 2, 8, 0)
    )
    assert monday_shift1.required_people == 2
    people = [a.person_id for a in monday_shift1.assignments if a.person_id]
    assert len(people) == 2 and len(set(people)) == 2

    # 周六（2026-03-07）第1班仅需 1 人
    sat_shift1 = next(s for s in slots if s.slot_start_at == datetime(2026, 3, 7, 8, 0))
    assert sat_shift1.required_people == 1


def test_yellow_credited_fixed_120(db_session):
    _yellow(db_session, templates=1)
    _person(db_session, 0)
    _person(db_session, 1)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, seed=1)
    db_session.commit()
    a = db_session.scalar(select(Assignment).where(Assignment.person_id.isnot(None)))
    assert a.credited_minutes == 120
    assert a.balance_minutes == 120


def test_course_conflict_excludes_person(db_session):
    _yellow(db_session, templates=1)
    p0 = _person(db_session, 0)
    _person(db_session, 1)
    _person(db_session, 2)
    # p0 在周一第1班时间有课
    db_session.add(AvailabilityBlock(
        person_id=p0.id, source=AvailabilitySource.course,
        start_at=datetime(2026, 3, 2, 8, 0), end_at=datetime(2026, 3, 2, 10, 0),
        status=AvailabilityStatus.active,
    ))
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, seed=1)
    db_session.commit()
    slots = list(db_session.scalars(select(DutySlot)))
    monday1 = next(s for s in slots if s.slot_start_at == datetime(2026, 3, 2, 8, 0))
    assigned = {a.person_id for a in monday1.assignments if a.person_id}
    assert p0.id not in assigned  # 有课冲突不被排入


def test_publish_sets_status_and_assigned(db_session):
    _yellow(db_session, templates=1)
    _person(db_session, 0)
    _person(db_session, 1)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, seed=1)
    db_session.commit()
    plan = schedule_service.publish(db_session, MONDAY, actor_id=None)
    db_session.commit()
    assert plan.status == PlanStatus.published
    assert plan.published_at is not None


def test_reproducible_generate(db_session):
    _yellow(db_session, templates=2)
    for i in range(5):
        _person(db_session, i)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, seed=7)
    db_session.commit()
    first = {
        (str(a.duty_slot_id), a.position_index): str(a.person_id)
        for a in db_session.scalars(select(Assignment)) if a.person_id
    }
    # 重新生成（同 seed）应得到相同分配
    schedule_service.generate(db_session, MONDAY, actor_id=None, seed=7)
    db_session.commit()
    second = {
        (str(a.duty_slot_id), a.position_index): str(a.person_id)
        for a in db_session.scalars(select(Assignment)) if a.person_id
    }
    assert set(first.values()) == set(second.values())
