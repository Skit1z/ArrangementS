"""阶段七：请假、换班、不可值班申请、未到岗标记测试。"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import hash_password
from app.models.availability import AvailabilityBlock
from app.models.enums import (
    AvailabilityStatus,
    ExecutionStatus,
    LeaveStatus,
    PersonStatus,
    PlanAssignmentStatus,
    PlanStatus,
    SlotSourceType,
    SlotStatus,
    SwapStatus,
    UserRole,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.models.venue import Venue
from app.models.enums import VenueType
from app.services import (
    availability_service,
    execution_service,
    leave_service,
    swap_service,
)


def _person(db, i):
    from app.models.user import User

    u = User(username=f"w{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(user_id=u.id, student_no=f"w{i}", class_name="一班", full_name=f"人{i}",
                      phone="13800000000", status=PersonStatus.active, is_in_scheduling_pool=True)
    db.add(p)
    db.flush()
    return p


def _future_assignment(db, person, hours_ahead=48):
    venue = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db.add(venue)
    db.flush()
    plan = WeeklyPlan(week_start=date(2026, 3, 2), week_end=date(2026, 3, 8), revision=1, status=PlanStatus.published)
    db.add(plan)
    db.flush()
    start = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
    slot = DutySlot(
        weekly_plan_id=plan.id, venue_id=venue.id, source_type=SlotSourceType.fixed_shift,
        slot_start_at=start, slot_end_at=start + timedelta(hours=2),
        required_people=2, credited_minutes=120, month_key="2026-03", status=SlotStatus.filled,
    )
    db.add(slot)
    db.flush()
    a = Assignment(
        duty_slot_id=slot.id, person_id=person.id, position_index=0,
        plan_status=PlanAssignmentStatus.assigned, execution_status=ExecutionStatus.pending,
        credited_minutes=120, balance_minutes=120,
    )
    db.add(a)
    db.flush()
    return a, slot


# --- 请假 ---
def test_leave_approve_zeroes_hours_and_vacates(db_session):
    p = _person(db_session, 0)
    a, slot = _future_assignment(db_session, p)
    db_session.commit()

    leave = leave_service.create_leave(db_session, applicant_person_id=p.id, assignment_id=a.id, reason="病假")
    db_session.commit()
    assert leave.status == LeaveStatus.pending

    leave_service.approve(db_session, actor_id=None, leave_id=leave.id)
    db_session.commit()
    db_session.refresh(a)
    assert a.execution_status == ExecutionStatus.leave
    assert a.plan_status == PlanAssignmentStatus.vacant
    assert a.credited_minutes == 0
    assert a.balance_minutes == 0


def test_leave_only_own_assignment(db_session):
    p0 = _person(db_session, 0)
    p1 = _person(db_session, 1)
    a, _ = _future_assignment(db_session, p0)
    db_session.commit()
    with pytest.raises(HTTPException) as ei:
        leave_service.create_leave(db_session, applicant_person_id=p1.id, assignment_id=a.id, reason="x")
    assert ei.value.status_code == 403


def test_duplicate_leave_rejected_and_approval_can_be_revoked(db_session):
    p = _person(db_session, 0)
    a, slot = _future_assignment(db_session, p)
    leave = leave_service.create_leave(
        db_session, applicant_person_id=p.id, assignment_id=a.id, reason="病假"
    )
    with pytest.raises(HTTPException) as duplicate:
        leave_service.create_leave(
            db_session, applicant_person_id=p.id, assignment_id=a.id, reason="重复"
        )
    assert duplicate.value.status_code == 409
    leave_service.approve(db_session, actor_id=None, leave_id=leave.id)
    leave_service.revoke_approval(db_session, actor_id=None, leave_id=leave.id)
    assert leave.status == LeaveStatus.cancelled
    assert a.execution_status == ExecutionStatus.pending
    assert a.plan_status == PlanAssignmentStatus.assigned
    assert a.credited_minutes == 120
    assert slot.status == SlotStatus.filled


def test_emergency_flag_within_24h(db_session):
    p = _person(db_session, 0)
    a, _ = _future_assignment(db_session, p, hours_ahead=10)
    db_session.commit()
    leave = leave_service.create_leave(db_session, applicant_person_id=p.id, assignment_id=a.id, reason="急事")
    assert leave.is_emergency is True


# --- 换班 ---
def test_targeted_swap_full_flow(db_session):
    p0 = _person(db_session, 0)
    p1 = _person(db_session, 1)
    a, slot = _future_assignment(db_session, p0)
    db_session.commit()

    swap = swap_service.create_targeted(db_session, requester_person_id=p0.id, assignment_id=a.id, target_person_id=p1.id)
    db_session.commit()
    assert swap.status == SwapStatus.awaiting_target

    swap_service.respond_target(db_session, target_person_id=p1.id, swap_id=swap.id, accept=True)
    db_session.commit()
    assert swap.status == SwapStatus.pending_admin

    swap_service.admin_approve(db_session, actor_id=None, swap_id=swap.id)
    db_session.commit()
    db_session.refresh(a)
    assert a.person_id == p1.id  # 已转移给接替人员
    assert a.balance_minutes == 120  # 工时归最终承担人员
    assert swap.status == SwapStatus.approved


def test_open_swap_flow_and_other_candidates_expire(db_session):
    p0 = _person(db_session, 0)
    p1 = _person(db_session, 1)
    p2 = _person(db_session, 2)
    a, slot = _future_assignment(db_session, p0)
    db_session.commit()

    swap = swap_service.create_open(db_session, requester_person_id=p0.id, assignment_id=a.id)
    db_session.commit()
    swap_service.apply_open(db_session, candidate_person_id=p1.id, swap_id=swap.id)
    swap_service.apply_open(db_session, candidate_person_id=p2.id, swap_id=swap.id)
    db_session.commit()

    swap_service.admin_approve(db_session, actor_id=None, swap_id=swap.id, selected_person_id=p1.id)
    db_session.commit()
    db_session.refresh(a)
    assert a.person_id == p1.id
    from app.models.enums import SwapCandidateStatus
    from app.models.swap import SwapCandidate
    cands = {c.candidate_person_id: c.status for c in db_session.scalars(select(SwapCandidate))}
    assert cands[p1.id] == SwapCandidateStatus.selected
    assert cands[p2.id] == SwapCandidateStatus.expired


def test_swap_creation_rejects_started_shift(db_session):
    p0 = _person(db_session, 0)
    p1 = _person(db_session, 1)
    a, _ = _future_assignment(db_session, p0, hours_ahead=-1)
    with pytest.raises(HTTPException) as exc:
        swap_service.create_targeted(
            db_session,
            requester_person_id=p0.id,
            assignment_id=a.id,
            target_person_id=p1.id,
        )
    assert exc.value.status_code == 422


def test_swap_approve_revalidates_time_overlap(db_session):
    p0 = _person(db_session, 0)
    p1 = _person(db_session, 1)
    a, slot = _future_assignment(db_session, p0)
    # p1 已有一个与该 slot 时间重叠的分配
    other = Assignment(
        duty_slot_id=slot.id, person_id=p1.id, position_index=1,
        plan_status=PlanAssignmentStatus.assigned, execution_status=ExecutionStatus.pending,
        credited_minutes=120, balance_minutes=120,
    )
    db_session.add(other)
    db_session.flush()
    swap = swap_service.create_targeted(db_session, requester_person_id=p0.id, assignment_id=a.id, target_person_id=p1.id)
    swap_service.respond_target(db_session, target_person_id=p1.id, swap_id=swap.id, accept=True)
    db_session.commit()
    with pytest.raises(HTTPException) as ei:
        swap_service.admin_approve(db_session, actor_id=None, swap_id=swap.id)
    assert ei.value.status_code == 422  # 时间重叠，拒绝


# --- 不可值班申请 ---
def test_availability_request_approve_creates_block(db_session):
    p = _person(db_session, 0)
    db_session.commit()
    start = datetime.now(timezone.utc) + timedelta(days=1)
    req = availability_service.create_request(db_session, person_id=p.id, start_at=start, end_at=start + timedelta(hours=2), reason="有事")
    db_session.commit()
    availability_service.approve(db_session, actor_id=None, request_id=req.id)
    db_session.commit()
    blocks = list(db_session.scalars(select(AvailabilityBlock).where(AvailabilityBlock.person_id == p.id, AvailabilityBlock.status == AvailabilityStatus.active)))
    assert len(blocks) == 1


def test_weekly_availability_request_expands_until_date(db_session):
    p = _person(db_session, 0)
    start = datetime.now(timezone.utc) + timedelta(days=1)
    until = start + timedelta(weeks=2)
    req = availability_service.create_request(
        db_session,
        person_id=p.id,
        start_at=start,
        end_at=start + timedelta(hours=2),
        reason="每周有事",
        recurrence_rule=f"FREQ=WEEKLY;UNTIL={until.isoformat()}",
    )
    availability_service.approve(db_session, actor_id=None, request_id=req.id)
    blocks = list(db_session.scalars(select(AvailabilityBlock).where(
        AvailabilityBlock.source_ref_id == req.id
    )))
    assert len(blocks) == 3


def test_availability_request_past_rejected(db_session):
    p = _person(db_session, 0)
    db_session.commit()
    past = datetime.now(timezone.utc) - timedelta(days=2)
    with pytest.raises(HTTPException):
        availability_service.create_request(db_session, person_id=p.id, start_at=past, end_at=past + timedelta(hours=1), reason="x")


# --- 未到岗 ---
def test_mark_absent_zeroes_credited_preserves_balance(db_session):
    p = _person(db_session, 0)
    a, _ = _future_assignment(db_session, p)
    db_session.commit()
    execution_service.mark_absent(db_session, actor_id=None, assignment_id=a.id, reason="缺勤")
    db_session.commit()
    db_session.refresh(a)
    assert a.execution_status == ExecutionStatus.absent
    assert a.credited_minutes == 0  # 实际完成 0
    assert a.balance_minutes == 120  # 平衡工时保留（不降低后续排班权重）


# --- 审核中心：GET /admin/assignments/daily + mark-absent/complete API 端到端 ---
def test_admin_daily_assignments_endpoint(client, seed_admin, db_session):
    """admin GET /admin/assignments/daily?date=... 返回当天所有分配。"""
    from tests.conftest import csrf_headers, login

    p = _person(db_session, 0)
    a, slot = _future_assignment(db_session, p, hours_ahead=12)
    db_session.commit()

    # 计算当天日期（slot 所在 UTC 日）
    slot_day = slot.slot_start_at.date()
    token = login(client, "admin", "admin1234")
    resp = client.get(
        f"/api/v1/admin/assignments/daily?date={slot_day.isoformat()}",
        headers=csrf_headers(token),
    )
    assert resp.status_code == 200, resp.text
    rows = resp.json()
    assert any(r["assignment_id"] == str(a.id) for r in rows)
    mine = next(r for r in rows if r["assignment_id"] == str(a.id))
    assert mine["person_name"] == "人0"
    assert mine["venue_name"] == "黄楼"
    assert mine["execution_status"] == "pending"


def test_admin_daily_assignments_requires_admin(client, seed_admin, db_session):
    """普通用户不能访问。"""
    from tests.conftest import login, csrf_headers

    _person(db_session, 0)
    db_session.commit()
    # 用 admin 创建一个普通用户来登录
    from app.models.user import User
    from app.models.enums import UserRole
    u = User(username="u1", password_hash=hash_password("y"), role=UserRole.user, is_active=True)
    db_session.add(u); db_session.commit()
    token = login(client, "u1", "y")
    resp = client.get(
        "/api/v1/admin/assignments/daily?date=2026-03-04",
        headers=csrf_headers(token),
    )
    assert resp.status_code == 403


def test_admin_mark_absent_via_api(client, seed_admin, db_session):
    """admin 通过 API 标记未到岗。"""
    from tests.conftest import login, csrf_headers

    p = _person(db_session, 0)
    a, _ = _future_assignment(db_session, p, hours_ahead=12)
    db_session.commit()

    token = login(client, "admin", "admin1234")
    resp = client.post(
        f"/api/v1/assignments/{a.id}/mark-absent",
        headers=csrf_headers(token),
        json={"comment": "缺勤"},
    )
    assert resp.status_code == 200, resp.text
    db_session.refresh(a)
    assert a.execution_status == ExecutionStatus.absent
