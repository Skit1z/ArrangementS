"""普通用户自助视图测试（方案 10.2 / 10.3 / 10.7）。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.core.security import hash_password
from app.models.enums import (
    ExecutionStatus,
    PersonStatus,
    PlanAssignmentStatus,
    PlanStatus,
    SlotSourceType,
    SlotStatus,
    UserRole,
    VenueType,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.models.user import User
from app.models.venue import Venue
from app.services import me_service


def _person(db, i, name=None):
    u = User(username=f"m{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id, student_no=f"m{i}", class_name="一班", full_name=name or f"人{i}",
        phone="13800000000", status=PersonStatus.active,
        id_card_last4="1234", bank_card_last4="5678", difficulty_level="一般",
    )
    db.add(p)
    db.flush()
    return p


def _plan(db, status=PlanStatus.published):
    plan = WeeklyPlan(week_start=date(2026, 3, 2), week_end=date(2026, 3, 8), revision=1, status=status)
    db.add(plan)
    db.flush()
    return plan


def _slot_with(db, plan, people, start_offset_hours=48):
    v = Venue(name="黄楼", code=f"HL{plan.id.hex[:4]}", venue_type=VenueType.fixed_shift, default_required_people=2)
    db.add(v)
    db.flush()
    start = datetime.now(timezone.utc) + timedelta(hours=start_offset_hours)
    slot = DutySlot(
        weekly_plan_id=plan.id, venue_id=v.id, source_type=SlotSourceType.fixed_shift,
        slot_start_at=start, slot_end_at=start + timedelta(hours=2), required_people=len(people),
        credited_minutes=120, month_key="2026-03", status=SlotStatus.filled,
    )
    db.add(slot)
    db.flush()
    for i, p in enumerate(people):
        db.add(Assignment(
            duty_slot_id=slot.id, person_id=p.id, position_index=i,
            plan_status=PlanAssignmentStatus.assigned, execution_status=ExecutionStatus.pending,
            credited_minutes=120, balance_minutes=120,
        ))
    db.flush()
    return slot


def test_my_schedule_only_shows_own_assignments(db_session):
    plan = _plan(db_session)
    me = _person(db_session, 0, "我")
    other = _person(db_session, 1, "同事")
    _slot_with(db_session, plan, [me, other])
    db_session.commit()

    rows = me_service.my_assignments(db_session, me.id)
    assert len(rows) == 1
    assert rows[0]["credited_minutes"] == 120


def test_unpublished_plan_hidden_from_user(db_session):
    plan = _plan(db_session, status=PlanStatus.draft)
    me = _person(db_session, 0)
    _slot_with(db_session, plan, [me])
    db_session.commit()
    assert me_service.my_assignments(db_session, me.id) == []


def test_teammates_expose_name_class_and_phone(db_session):
    """同班人员返回 full_name + class_name + phone（供移动端「同班/前班/后班」展示联系电话）。

    绝不返回身份证号、银行卡号、困难等级等敏感字段。
    """
    plan = _plan(db_session)
    me = _person(db_session, 0, "我")
    other = _person(db_session, 1, "同事")
    _slot_with(db_session, plan, [me, other])
    db_session.commit()

    rows = me_service.my_assignments(db_session, me.id)
    mates = rows[0]["teammates"]
    assert len(mates) == 1
    assert mates[0] == {"full_name": "同事", "class_name": "一班", "phone": "13800000000"}
    # 仅这三个字段，绝不泄露其它敏感字段
    assert set(mates[0].keys()) == {"full_name", "class_name", "phone"}


def test_adjacent_shift_excludes_draft_plan(db_session):
    """前/后一班查询只看已发布计划，绝不返回草稿计划中的人员。"""
    from datetime import datetime, timedelta, timezone
    from app.models.enums import (
        ExecutionStatus,
        PlanAssignmentStatus,
        SlotSourceType,
        SlotStatus,
        VenueType,
    )
    from app.models.schedule import Assignment, DutySlot
    from app.models.venue import Venue
    from app.services import me_service

    me = _person(db_session, 0, "我")
    draft_other = _person(db_session, 1, "草稿同事")

    # 共用一个场地，便于「下一班」查询能命中
    v = Venue(name="黄楼A", code="HLA1", venue_type=VenueType.fixed_shift, default_required_people=1)
    db_session.add(v); db_session.flush()

    # 草稿计划：未来 72h 有一班，含「草稿同事」
    draft_plan = WeeklyPlan(
        week_start=date(2026, 3, 16), week_end=date(2026, 3, 22), revision=1, status=PlanStatus.draft
    )
    db_session.add(draft_plan); db_session.flush()
    start1 = datetime.now(timezone.utc) + timedelta(hours=72)
    slot1 = DutySlot(
        weekly_plan_id=draft_plan.id, venue_id=v.id, source_type=SlotSourceType.fixed_shift,
        slot_start_at=start1, slot_end_at=start1 + timedelta(hours=2), required_people=1,
        credited_minutes=120, month_key="2026-03", status=SlotStatus.filled,
    )
    db_session.add(slot1); db_session.flush()
    db_session.add(Assignment(
        duty_slot_id=slot1.id, person_id=draft_other.id, position_index=0,
        plan_status=PlanAssignmentStatus.assigned, execution_status=ExecutionStatus.pending,
        credited_minutes=120, balance_minutes=120,
    ))

    # 已发布计划：未来 48h 有一班，含「我」（同场地 v）
    pub_plan = WeeklyPlan(
        week_start=date(2026, 3, 2), week_end=date(2026, 3, 8), revision=1, status=PlanStatus.published
    )
    db_session.add(pub_plan); db_session.flush()
    start2 = datetime.now(timezone.utc) + timedelta(hours=48)
    slot2 = DutySlot(
        weekly_plan_id=pub_plan.id, venue_id=v.id, source_type=SlotSourceType.fixed_shift,
        slot_start_at=start2, slot_end_at=start2 + timedelta(hours=2), required_people=1,
        credited_minutes=120, month_key="2026-03", status=SlotStatus.filled,
    )
    db_session.add(slot2); db_session.flush()
    db_session.add(Assignment(
        duty_slot_id=slot2.id, person_id=me.id, position_index=0,
        plan_status=PlanAssignmentStatus.assigned, execution_status=ExecutionStatus.pending,
        credited_minutes=120, balance_minutes=120,
    ))
    db_session.commit()

    # 我的已发布班次（slot2），查「下一班」时：草稿计划的 slot1（同场地 v）应被忽略
    rows = me_service.my_assignments(db_session, me.id)
    my_row = next((r for r in rows if r["slot_id"] == str(slot2.id)), None)
    assert my_row is not None, "应当看到自己在 slot2 的排班"
    next_people = my_row["next_shift"]
    assert all(p["full_name"] != "草稿同事" for p in next_people), next_people


def test_next_duty_returns_upcoming_only(db_session):
    plan = _plan(db_session)
    me = _person(db_session, 0)
    _slot_with(db_session, plan, [me], start_offset_hours=-48)  # 已过去
    db_session.commit()
    assert me_service.next_duty(db_session, me.id) is None

    plan2 = WeeklyPlan(week_start=date(2026, 3, 9), week_end=date(2026, 3, 15), revision=1, status=PlanStatus.published)
    db_session.add(plan2)
    db_session.flush()
    _slot_with(db_session, plan2, [me], start_offset_hours=72)  # 未来
    db_session.commit()
    nxt = me_service.next_duty(db_session, me.id)
    assert nxt is not None
    assert nxt["venue_name"] == "黄楼"


def test_me_timetable_returns_active(client, seed_admin, db_session):
    """登录用户调用 /me/timetable 返回本人当前学期的生效课表。"""
    from app.services import semester_service, timetable_service
    from app.timetable.extractor import RawCourseEntry
    from tests.conftest import csrf_headers, login

    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    u = User(
        username="202301070410",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no="202301070410",
        class_name="信管231",
        full_name="王文博",
        phone="13800000000",
    )
    db_session.add(p)
    db_session.commit()

    entries = [
        RawCourseEntry(
            weekday=1, period_start=1, period_end=2, week_expr="1-4周", location_code="B101"
        )
    ]
    up = timetable_service.create_upload_from_entries(
        db_session,
        person_id=p.id,
        semester_id=sem.id,
        uploader_user_id=None,
        file_name="t.pdf",
        entries=entries,
    )
    timetable_service.approve(db_session, up.id, reviewer_id=None)
    db_session.commit()

    login(client, "202301070410", "pw123456")
    resp = client.get("/api/v1/me/timetable")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body is not None
    assert body["upload_id"] == str(up.id)
    assert body["review_status"] == "approved"
    assert len(body["entries"]) == 1
    assert body["entries"][0]["weekday"] == 1


def test_me_timetable_null_when_none(client, seed_admin, db_session):
    """无课表时返回 null。"""
    from app.services import semester_service
    from tests.conftest import login

    semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    u = User(
        username="202301070410",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(u)
    db_session.flush()
    db_session.add(
        PersonProfile(
            user_id=u.id,
            student_no="202301070410",
            class_name="信管231",
            full_name="王文博",
            phone="13800000000",
        )
    )
    db_session.commit()

    login(client, "202301070410", "pw123456")
    resp = client.get("/api/v1/me/timetable")
    assert resp.status_code == 200
    assert resp.json() is None
