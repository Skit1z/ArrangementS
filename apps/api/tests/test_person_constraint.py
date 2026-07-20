"""PersonConstraint 有效期与换班终审补查测试（P1.4 / P1.5）。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.core.security import hash_password
from app.models.constraint import PersonConstraint
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
from app.scheduling import eligibility


BEIJING_TZ = timezone(timedelta(hours=8))


def _person(db, i=0, name="甲"):
    u = User(username=f"c{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no=f"c{i}",
        class_name="一班",
        full_name=name,
        phone="13800000000",
        status=PersonStatus.active,
        is_in_scheduling_pool=True,
    )
    db.add(p)
    db.flush()
    return p


def _slot_on(db, venue, day, start_hour=9, end_hour=11):
    """在指定日期建一个 DutySlot（不入 plan，仅供 eligibility 检测）。"""
    s = datetime.combine(day, time(start_hour), tzinfo=BEIJING_TZ)
    e = datetime.combine(day, time(end_hour), tzinfo=BEIJING_TZ)
    return DutySlot(
        venue_id=venue.id,
        source_type=SlotSourceType.fixed_shift,
        slot_start_at=s,
        slot_end_at=e,
        required_people=1,
        credited_minutes=120,
    )


# ============ P1.4：effective_start/end 生效 ============
def test_constraint_outside_effective_range_ignored(db_session):
    """约束有效期外应被忽略。"""
    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db_session.add(v)
    db_session.flush()
    p = _person(db_session)
    # 禁黄楼，但只在 2026-01-01 ~ 2026-01-31 生效
    db_session.add(
        PersonConstraint(
            person_id=p.id,
            constraint_type="forbid_venue",
            constraint_value={"venue_ids": [str(v.id)]},
            is_hard=True,
            is_active=True,
            effective_start=date(2026, 1, 1),
            effective_end=date(2026, 1, 31),
        )
    )
    db_session.commit()

    # 2026-03-04（在范围外）→ 应可用
    slot_march = _slot_on(db_session, v, date(2026, 3, 4))
    assert eligibility.check_person_available_for_slot(db_session, p, slot_march) is True

    # 2026-01-15（在范围内）→ 应不可用
    slot_jan = _slot_on(db_session, v, date(2026, 1, 15))
    assert eligibility.check_person_available_for_slot(db_session, p, slot_jan) is False


def test_constraint_open_ended_effective_start(db_session):
    """只有 effective_start、无 end：从该日期起永久生效。"""
    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db_session.add(v)
    db_session.flush()
    p = _person(db_session)
    db_session.add(
        PersonConstraint(
            person_id=p.id,
            constraint_type="forbid_venue",
            constraint_value={"venue_ids": [str(v.id)]},
            is_hard=True,
            is_active=True,
            effective_start=date(2026, 2, 1),
            effective_end=None,
        )
    )
    db_session.commit()

    # 1 月（之前）可用
    assert (
        eligibility.check_person_available_for_slot(
            db_session, p, _slot_on(db_session, v, date(2026, 1, 15))
        )
        is True
    )
    # 3 月（之后）不可用
    assert (
        eligibility.check_person_available_for_slot(
            db_session, p, _slot_on(db_session, v, date(2026, 3, 4))
        )
        is False
    )


def test_constraint_no_effective_dates_always_active(db_session):
    """无 effective_start/end（None）→ 永久生效。"""
    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db_session.add(v)
    db_session.flush()
    p = _person(db_session)
    db_session.add(
        PersonConstraint(
            person_id=p.id,
            constraint_type="forbid_venue",
            constraint_value={"venue_ids": [str(v.id)]},
            is_hard=True,
            is_active=True,
        )
    )
    db_session.commit()
    assert (
        eligibility.check_person_available_for_slot(
            db_session, p, _slot_on(db_session, v, date(2026, 3, 4))
        )
        is False
    )


# ============ P1.5：换班终审补查 ============
def _assignment_with(db, person, venue, day, hour=9, partner=None):
    """构造一条已存在的 assignment（含可选同班搭档）。"""
    plan = WeeklyPlan(
        week_start=day - timedelta(days=day.weekday()),
        week_end=day - timedelta(days=day.weekday()) + timedelta(days=6),
        revision=1,
        status=PlanStatus.published,
    )
    db.add(plan)
    db.flush()
    s = datetime.combine(day, time(hour), tzinfo=BEIJING_TZ)
    e = datetime.combine(day, time(hour + 2), tzinfo=BEIJING_TZ)
    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=venue.id,
        source_type=SlotSourceType.fixed_shift,
        slot_start_at=s,
        slot_end_at=e,
        required_people=2 if partner else 1,
        credited_minutes=120,
        month_key=day.strftime("%Y-%m"),
        status=SlotStatus.filled,
    )
    db.add(slot)
    db.flush()
    a = Assignment(
        duty_slot_id=slot.id,
        person_id=person.id,
        position_index=0,
        plan_status=PlanAssignmentStatus.assigned,
        execution_status=ExecutionStatus.pending,
        raw_minutes=120,
        weighted_minutes_before_round=Decimal(120),
        credited_minutes=120,
        balance_minutes=120,
    )
    db.add(a)
    if partner:
        a2 = Assignment(
            duty_slot_id=slot.id,
            person_id=partner.id,
            position_index=1,
            plan_status=PlanAssignmentStatus.assigned,
            execution_status=ExecutionStatus.pending,
            raw_minutes=120,
            weighted_minutes_before_round=Decimal(120),
            credited_minutes=120,
            balance_minutes=120,
        )
        db.add(a2)
    db.flush()
    return a, slot


def test_swap_approve_rejects_when_partner_pair_forbidden(db_session):
    """接替人与现有同班人员存在禁止同班关系 → 拒绝。"""
    from app.services import swap_service

    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db_session.add(v)
    db_session.flush()
    requester = _person(db_session, 0, "发起人")
    receiver = _person(db_session, 1, "接替人")
    existing_partner = _person(db_session, 2, "现有同班")

    # 现有同班人配置「禁止与接替人搭档」
    db_session.add(
        PersonConstraint(
            person_id=existing_partner.id,
            constraint_type="no_pair_with",
            constraint_value={"person_ids": [str(receiver.id)]},
            is_hard=True,
            is_active=True,
        )
    )
    db_session.commit()

    # 用未来日期
    future = datetime.now(BEIJING_TZ).date() + timedelta(days=14)
    # 同一个 slot 上：发起人在第 0 位，现有同班在第 1 位
    plan = WeeklyPlan(
        week_start=future - timedelta(days=future.weekday()),
        week_end=future - timedelta(days=future.weekday()) + timedelta(days=6),
        revision=1,
        status=PlanStatus.published,
    )
    db_session.add(plan)
    db_session.flush()
    s = datetime.combine(future, time(9), tzinfo=BEIJING_TZ)
    e = datetime.combine(future, time(11), tzinfo=BEIJING_TZ)
    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=v.id,
        source_type=SlotSourceType.fixed_shift,
        slot_start_at=s,
        slot_end_at=e,
        required_people=2,
        credited_minutes=120,
        month_key=future.strftime("%Y-%m"),
        status=SlotStatus.filled,
    )
    db_session.add(slot)
    db_session.flush()
    requester_a = Assignment(
        duty_slot_id=slot.id,
        person_id=requester.id,
        position_index=0,
        plan_status=PlanAssignmentStatus.assigned,
        execution_status=ExecutionStatus.pending,
        raw_minutes=120,
        weighted_minutes_before_round=Decimal(120),
        credited_minutes=120,
        balance_minutes=120,
    )
    db_session.add(requester_a)
    db_session.add(
        Assignment(
            duty_slot_id=slot.id,
            person_id=existing_partner.id,
            position_index=1,
            plan_status=PlanAssignmentStatus.assigned,
            execution_status=ExecutionStatus.pending,
            raw_minutes=120,
            weighted_minutes_before_round=Decimal(120),
            credited_minutes=120,
            balance_minutes=120,
        )
    )
    db_session.flush()
    db_session.commit()

    swap = swap_service.create_targeted(
        db_session,
        requester_person_id=requester.id,
        assignment_id=requester_a.id,
        target_person_id=receiver.id,
        reason="x",
    )
    swap_service.respond_target(
        db_session, target_person_id=receiver.id, swap_id=swap.id, accept=True
    )
    db_session.commit()

    # admin 终审：应当拒绝（no_pair_with 违反）
    with pytest.raises(HTTPException) as ei:
        swap_service.admin_approve(
            db_session,
            actor_id=None,
            swap_id=swap.id,
            selected_person_id=receiver.id,
        )
    assert ei.value.status_code == 422


def test_swap_approve_rejects_inactive_person(db_session):
    """接替人非启用状态 → 拒绝。"""
    from app.services import swap_service

    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=1)
    db_session.add(v)
    db_session.flush()
    requester = _person(db_session, 0, "发起人")
    receiver = _person(db_session, 1, "接替人")
    receiver.status = PersonStatus.suspended  # 非启用
    db_session.commit()

    # 用未来日期（避免触发「班次已开始」检查）
    future = datetime.now(BEIJING_TZ).date() + timedelta(days=14)
    requester_a, _ = _assignment_with(db_session, requester, v, future)
    swap = swap_service.create_targeted(
        db_session,
        requester_person_id=requester.id,
        assignment_id=requester_a.id,
        target_person_id=receiver.id,
        reason="x",
    )
    swap_service.respond_target(
        db_session, target_person_id=receiver.id, swap_id=swap.id, accept=True
    )
    db_session.commit()

    with pytest.raises(HTTPException) as ei:
        swap_service.admin_approve(
            db_session,
            actor_id=None,
            swap_id=swap.id,
            selected_person_id=receiver.id,
        )
    assert ei.value.status_code == 422
    assert "启用" in ei.value.detail or "状态" in ei.value.detail


# --- constraints API CRUD ---
def test_constraints_api_crud(client, seed_admin, db_session):
    """admin 通过 API 为人员创建/查询/更新/删除约束。"""
    from tests.conftest import login, csrf_headers

    p = _person(db_session, 5, "受约束人")
    db_session.commit()
    token = login(client, "admin", "admin1234")

    # 创建：暂停排班 2026-04-01 ~ 2026-04-30
    resp = client.post(
        f"/api/v1/admin/people/{p.id}/constraints",
        headers=csrf_headers(token),
        json={
            "constraint_type": "suspend",
            "constraint_value": None,
            "is_hard": True,
            "effective_start": "2026-04-01",
            "effective_end": "2026-04-30",
            "is_active": True,
        },
    )
    assert resp.status_code == 200, resp.text
    cid = resp.json()["id"]

    # 列表
    resp = client.get(f"/api/v1/admin/people/{p.id}/constraints", headers=csrf_headers(token))
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["constraint_type"] == "suspend"
    assert resp.json()[0]["effective_start"] == "2026-04-01"

    # 更新：拉长到 5 月底
    resp = client.patch(
        f"/api/v1/admin/people/constraints/{cid}",
        headers=csrf_headers(token),
        json={"effective_end": "2026-05-31"},
    )
    assert resp.status_code == 200
    assert resp.json()["effective_end"] == "2026-05-31"

    # 删除
    resp = client.delete(f"/api/v1/admin/people/constraints/{cid}", headers=csrf_headers(token))
    assert resp.status_code == 200
    resp = client.get(f"/api/v1/admin/people/{p.id}/constraints", headers=csrf_headers(token))
    assert resp.json() == []


def test_constraints_api_rejects_unknown_type(client, seed_admin, db_session):
    from tests.conftest import login, csrf_headers

    p = _person(db_session, 6, "受约束人")
    db_session.commit()
    token = login(client, "admin", "admin1234")
    resp = client.post(
        f"/api/v1/admin/people/{p.id}/constraints",
        headers=csrf_headers(token),
        json={"constraint_type": "bogus_type"},
    )
    assert resp.status_code == 422


def test_constraints_api_rejects_inverted_dates(client, seed_admin, db_session):
    from tests.conftest import login, csrf_headers

    p = _person(db_session, 7, "受约束人")
    db_session.commit()
    token = login(client, "admin", "admin1234")
    resp = client.post(
        f"/api/v1/admin/people/{p.id}/constraints",
        headers=csrf_headers(token),
        json={
            "constraint_type": "suspend",
            "effective_start": "2026-05-01",
            "effective_end": "2026-04-01",
        },
    )
    assert resp.status_code == 422
