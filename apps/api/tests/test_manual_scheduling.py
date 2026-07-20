"""manual_scheduling_service 走核心排班规则的测试（P1.1 修复）。"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.core.security import hash_password
from app.models.audit import AuditLog
from app.models.availability import AvailabilityBlock
from app.models.enums import (
    AvailabilitySource,
    AvailabilityStatus,
    PersonStatus,
    PlanAssignmentStatus,
    SlotSourceType,
    SlotStatus,
    UserRole,
    VenueType,
)
from app.models.multiplier import MultiplierRule
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot
from app.models.user import User
from app.models.venue import Venue
from app.services import manual_scheduling_service


def _person(db, i=0, name="甲"):
    u = User(
        username=f"ms{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True
    )
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no=f"ms{i}",
        class_name="一班",
        full_name=name,
        phone="13800000000",
        status=PersonStatus.active,
        is_in_scheduling_pool=True,
    )
    db.add(p)
    db.flush()
    return p


def _venue(db, name="蓝厅"):
    v = Venue(
        name=name, code=f"V{name}", venue_type=VenueType.event_based, default_required_people=2
    )
    db.add(v)
    db.flush()
    return v


def _multipliers(db):
    db.add(
        MultiplierRule(
            name="晚双",
            start_time=time(19, 0),
            end_time=time(0, 0),
            multiplier=Decimal("2.0"),
            priority=10,
            is_active=True,
        )
    )
    db.flush()


def test_assign_person_creates_slot_with_multiplier_and_audit(db_session):
    """正常路径：建岗 + 算工时（含倍率 + 半小时取整）+ 审计。"""
    _multipliers(db_session)
    p = _person(db_session)
    v = _venue(db_session)
    db_session.commit()

    start = datetime(2026, 3, 4, 19, 0, tzinfo=timezone(timedelta(hours=8)))  # 北京时间晚 7 点
    end = datetime(2026, 3, 4, 20, 0, tzinfo=timezone(timedelta(hours=8)))
    slot, a = manual_scheduling_service.assign_person_to_new_slot(
        db_session,
        person_id=p.id,
        venue_id=v.id,
        start_at=start,
        end_at=end,
        created_by=None,
        action="test.assign",
    )
    db_session.commit()

    assert slot.source_type == SlotSourceType.manual
    assert slot.status == SlotStatus.filled
    assert slot.required_people == 1
    # 19-20 点 60 分钟 ×2 倍 = 120 weighted → 半小时取整 120
    assert a.credited_minutes == 120
    assert a.balance_minutes == 120
    assert a.raw_minutes == 60
    assert a.weighted_minutes_before_round == Decimal(120)
    assert a.plan_status == PlanAssignmentStatus.assigned
    # 审计记录写入
    logs = list(db_session.scalars(select(AuditLog).where(AuditLog.action == "test.assign")))
    assert len(logs) == 1


def test_assign_person_blocked_by_availability_block(db_session):
    """有不可值班区间的人不能被排进来。"""
    p = _person(db_session)
    v = _venue(db_session)
    # 给 p 加一个 18-21 点的不可值班区间
    start = datetime(2026, 3, 4, 19, 0, tzinfo=timezone(timedelta(hours=8)))
    end = datetime(2026, 3, 4, 20, 0, tzinfo=timezone(timedelta(hours=8)))
    db_session.add(
        AvailabilityBlock(
            person_id=p.id,
            source=AvailabilitySource.course,
            start_at=datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 3, 4, 21, 0, tzinfo=timezone.utc),
            status=AvailabilityStatus.active,
            reason="课程",
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException) as ei:
        manual_scheduling_service.assign_person_to_new_slot(
            db_session,
            person_id=p.id,
            venue_id=v.id,
            start_at=start,
            end_at=end,
        )
    assert ei.value.status_code == 422
    assert "课程" in ei.value.detail or "不可值班" in ei.value.detail


def test_assign_person_blocked_by_time_overlap(db_session):
    """该人在此时段已有排班，禁止重复排。"""
    p = _person(db_session)
    v = _venue(db_session)
    db_session.commit()

    start = datetime(2026, 3, 4, 19, 0, tzinfo=timezone(timedelta(hours=8)))
    end = datetime(2026, 3, 4, 20, 0, tzinfo=timezone(timedelta(hours=8)))
    # 第一次成功
    manual_scheduling_service.assign_person_to_new_slot(
        db_session,
        person_id=p.id,
        venue_id=v.id,
        start_at=start,
        end_at=end,
    )
    db_session.commit()
    # 第二次重叠（19:30-20:30）应被拒
    with pytest.raises(HTTPException) as ei:
        manual_scheduling_service.assign_person_to_new_slot(
            db_session,
            person_id=p.id,
            venue_id=v.id,
            start_at=end - timedelta(minutes=30),
            end_at=end + timedelta(minutes=30),
        )
    assert ei.value.status_code == 422
    assert "重叠" in ei.value.detail


def test_assign_person_rejects_inactive_person(db_session):
    """非启用状态人员不可排班。"""
    p = _person(db_session)
    p.status = PersonStatus.suspended
    v = _venue(db_session)
    db_session.commit()

    start = datetime(2026, 3, 4, 19, 0, tzinfo=timezone(timedelta(hours=8)))
    end = datetime(2026, 3, 4, 20, 0, tzinfo=timezone(timedelta(hours=8)))
    with pytest.raises(HTTPException) as ei:
        manual_scheduling_service.assign_person_to_new_slot(
            db_session,
            person_id=p.id,
            venue_id=v.id,
            start_at=start,
            end_at=end,
        )
    assert ei.value.status_code == 422


def test_create_vacant_slot_zero_balance_no_pollution(db_session):
    """空岗 balance_minutes 全部为 0，不污染统计。"""
    v = _venue(db_session)
    db_session.commit()

    start = datetime(2026, 3, 4, 19, 0, tzinfo=timezone(timedelta(hours=8)))
    end = datetime(2026, 3, 4, 20, 0, tzinfo=timezone(timedelta(hours=8)))
    slot = manual_scheduling_service.create_vacant_slot(
        db_session,
        venue_id=v.id,
        start_at=start,
        end_at=end,
        required_people=3,
    )
    db_session.commit()

    assigns = list(db_session.scalars(select(Assignment).where(Assignment.duty_slot_id == slot.id)))
    assert len(assigns) == 3
    assert all(a.person_id is None for a in assigns)
    assert all(a.plan_status == PlanAssignmentStatus.vacant for a in assigns)
    assert all(a.balance_minutes == 0 for a in assigns)
    assert all(a.credited_minutes == 0 for a in assigns)


# --- 端到端：overtime.py 走 manual_scheduling_service ---
def test_overtime_approve_api_rejects_when_blocked(client, seed_admin, db_session):
    """加班申请：admin approve 时若人员有不可值班区间，应被拒绝，申请保持 pending。"""
    from app.models.enums import (
        AvailabilitySource,
        AvailabilityStatus,
        RequestStatus,
    )
    from app.models.overtime import OvertimeRequest
    from app.models.schedule import DutySlot
    from tests.conftest import login, csrf_headers

    p = _person(db_session, 1, "申请人")
    v = _venue(db_session)
    db_session.add(
        AvailabilityBlock(
            person_id=p.id,
            source=AvailabilitySource.course,
            start_at=datetime(2026, 3, 4, 18, 0, tzinfo=timezone.utc),
            end_at=datetime(2026, 3, 4, 22, 0, tzinfo=timezone.utc),
            status=AvailabilityStatus.active,
            reason="课程",
        )
    )
    db_session.commit()

    start = datetime(2026, 3, 4, 19, 0, tzinfo=timezone(timedelta(hours=8)))
    end = datetime(2026, 3, 4, 20, 0, tzinfo=timezone(timedelta(hours=8)))
    req = OvertimeRequest(
        person_id=p.id,
        venue_id=v.id,
        start_at=start,
        end_at=end,
        reason="加班",
        status=RequestStatus.pending,
    )
    db_session.add(req)
    db_session.commit()
    req_id = req.id

    token = login(client, "admin", "admin1234")
    resp = client.post(f"/api/v1/admin/overtime/{req_id}/approve", headers=csrf_headers(token))
    assert resp.status_code == 422
    db_session.refresh(req)
    assert req.status == RequestStatus.pending
    assert (
        list(
            db_session.scalars(
                select(DutySlot).where(DutySlot.source_type == SlotSourceType.manual)
            )
        )
        == []
    )


def test_manual_slot_api_creates_zero_balance_vacancies(client, seed_admin, db_session):
    """/admin/duty-slots/manual 创建的空岗 balance 全 0，不污染统计。"""
    from tests.conftest import login, csrf_headers

    v = _venue(db_session)
    db_session.commit()
    start = datetime(2026, 3, 5, 19, 0, tzinfo=timezone(timedelta(hours=8)))
    end = datetime(2026, 3, 5, 20, 0, tzinfo=timezone(timedelta(hours=8)))

    token = login(client, "admin", "admin1234")
    resp = client.post(
        "/api/v1/admin/duty-slots/manual",
        headers=csrf_headers(token),
        json={
            "venue_id": str(v.id),
            "start_at": start.isoformat(),
            "end_at": end.isoformat(),
            "required_people": 2,
        },
    )
    assert resp.status_code == 200, resp.text
    assigns = list(
        db_session.scalars(
            select(Assignment).join(DutySlot).where(DutySlot.source_type == SlotSourceType.manual)
        )
    )
    assert len(assigns) == 2
    assert all(a.balance_minutes == 0 for a in assigns)
    assert all(a.credited_minutes == 0 for a in assigns)
