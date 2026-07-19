"""场地任务：值班时间、重叠校验、工时预览测试。"""
from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.enums import VenueType
from app.models.multiplier import MultiplierRule
from app.models.venue import Venue
from app.services import task_service


def _event_venue(db):
    v = Venue(name="蓝厅", code="LT", venue_type=VenueType.event_based,
              default_required_people=2, default_prep_minutes=30, default_cleanup_minutes=30)
    db.add(v)
    db.flush()
    return v


def _default_multipliers(db):
    db.add(MultiplierRule(name="早间双倍", start_time=time(0, 0), end_time=time(8, 0), multiplier=Decimal("2.0"), priority=10, is_active=True))
    db.add(MultiplierRule(name="晚间双倍", start_time=time(19, 0), end_time=time(0, 0), multiplier=Decimal("2.0"), priority=10, is_active=True))
    db.flush()


def test_create_task_computes_duty_window(db_session):
    v = _event_venue(db_session)
    task = task_service.create_task(
        db_session, venue_id=v.id, title="讲座",
        booking_start_at=datetime(2026, 3, 2, 9, 30),
        booking_end_at=datetime(2026, 3, 2, 11, 30),
    )
    db_session.commit()
    # 默认提前 30、收尾 30
    assert task.duty_start_at == datetime(2026, 3, 2, 9, 0)
    assert task.duty_end_at == datetime(2026, 3, 2, 12, 0)
    assert task.required_people == 2


def test_same_venue_overlap_rejected(db_session):
    v = _event_venue(db_session)
    task_service.create_task(db_session, venue_id=v.id, title="A",
        booking_start_at=datetime(2026, 3, 2, 9, 0), booking_end_at=datetime(2026, 3, 2, 11, 0))
    db_session.commit()
    with pytest.raises(HTTPException) as ei:
        task_service.create_task(db_session, venue_id=v.id, title="B",
            booking_start_at=datetime(2026, 3, 2, 11, 15), booking_end_at=datetime(2026, 3, 2, 12, 0))
    assert ei.value.status_code == 409  # 完整值班时间(含收尾/提前)重叠


def test_booking_end_before_start_rejected(db_session):
    v = _event_venue(db_session)
    with pytest.raises(HTTPException) as ei:
        task_service.create_task(db_session, venue_id=v.id, title="X",
            booking_start_at=datetime(2026, 3, 2, 12, 0), booking_end_at=datetime(2026, 3, 2, 11, 0))
    assert ei.value.status_code == 422


def test_required_people_min_1(db_session):
    v = _event_venue(db_session)
    with pytest.raises(HTTPException):
        task_service.create_task(db_session, venue_id=v.id, title="X", required_people=0,
            booking_start_at=datetime(2026, 3, 2, 9, 0), booking_end_at=datetime(2026, 3, 2, 10, 0))


def test_task_hours_preview_with_multiplier(db_session):
    _default_multipliers(db_session)
    v = _event_venue(db_session)
    # 预约 18:30-19:00，提前30/收尾30 → 完整值班 18:00-19:30
    # 18:00-19:00(60 ×1) + 19:00-19:30(30 ×2)=60+60=120 → credited 120
    task = task_service.create_task(db_session, venue_id=v.id, title="晚会",
        booking_start_at=datetime(2026, 3, 2, 18, 30), booking_end_at=datetime(2026, 3, 2, 19, 0))
    db_session.commit()
    preview = task_service.preview_task_hours(db_session, task)
    assert preview["weighted_minutes_before_round"] == 120.0
    assert preview["credited_minutes"] == 120


def test_completed_task_not_editable(db_session):
    from app.models.enums import TaskStatus
    v = _event_venue(db_session)
    task = task_service.create_task(db_session, venue_id=v.id, title="A",
        booking_start_at=datetime(2026, 3, 2, 9, 0), booking_end_at=datetime(2026, 3, 2, 10, 0))
    task.status = TaskStatus.completed
    db_session.commit()
    with pytest.raises(HTTPException) as ei:
        task_service.update_task(db_session, task.id, {"title": "B"})
    assert ei.value.status_code == 422


# --- 任务状态转换 ---
def test_transition_task_valid_flow(db_session):
    """draft → confirmed → scheduled → executing → completed 全链路。"""
    from app.models.enums import TaskStatus
    v = _event_venue(db_session)
    task = task_service.create_task(db_session, venue_id=v.id, title="A",
        booking_start_at=datetime(2026, 3, 2, 9, 0), booking_end_at=datetime(2026, 3, 2, 10, 0))
    db_session.commit()

    for target in (TaskStatus.confirmed, TaskStatus.scheduled, TaskStatus.executing, TaskStatus.completed):
        task_service.transition_task(db_session, task.id, target)
        db_session.flush()
        db_session.refresh(task)
        assert task.status == target


def test_transition_task_rejects_invalid_jump(db_session):
    """draft 不能直接跳到 executing（必须经 confirmed/scheduled）。"""
    from app.models.enums import TaskStatus
    v = _event_venue(db_session)
    task = task_service.create_task(db_session, venue_id=v.id, title="A",
        booking_start_at=datetime(2026, 3, 2, 9, 0), booking_end_at=datetime(2026, 3, 2, 10, 0))
    db_session.commit()

    with pytest.raises(HTTPException) as ei:
        task_service.transition_task(db_session, task.id, TaskStatus.executing)
    assert ei.value.status_code == 422


def test_transition_task_rejects_terminal(db_session):
    """已完成/已取消任务不允许再转换。"""
    from app.models.enums import TaskStatus
    v = _event_venue(db_session)
    task = task_service.create_task(db_session, venue_id=v.id, title="A",
        booking_start_at=datetime(2026, 3, 2, 9, 0), booking_end_at=datetime(2026, 3, 2, 10, 0))
    task.status = TaskStatus.completed
    db_session.commit()
    with pytest.raises(HTTPException):
        task_service.transition_task(db_session, task.id, TaskStatus.scheduled)
