"""学期服务测试。"""
from __future__ import annotations

from datetime import date

import pytest
from fastapi import HTTPException

from app.models.enums import BuildingType
from app.services import semester_service


def test_create_semester_seeds_defaults(db_session):
    sem = semester_service.create_semester(
        db_session, name="2026 秋", first_monday=date(2026, 9, 1)
    )
    db_session.commit()
    assert len(sem.period_rules) == 6
    assert len(sem.building_rules) == 2
    # 第二教学楼 3-4 节 10:20-12:10
    second = next(
        r for r in sem.period_rules
        if r.period_group == "3-4" and r.building_type == BuildingType.second
    )
    assert (second.start_time.hour, second.start_time.minute) == (10, 20)


def test_week_count_is_fixed_at_20(db_session):
    sem = semester_service.create_semester(db_session, name="标准", first_monday=date(2026, 9, 1))
    assert sem.week_count == 20
    with pytest.raises(HTTPException):
        semester_service.create_semester(db_session, name="短", first_monday=date(2027, 9, 1), week_count=1)
    with pytest.raises(HTTPException):
        semester_service.create_semester(db_session, name="长", first_monday=date(2028, 9, 1), week_count=30)


def test_update_semester_rejects_non_20_week_count(db_session):
    sem = semester_service.create_semester(db_session, name="原", first_monday=date(2026, 9, 1))
    db_session.commit()
    with pytest.raises(HTTPException):
        semester_service.update_semester(db_session, sem.id, {"week_count": 18})
    semester_service.update_semester(db_session, sem.id, {"name": "改", "week_count": 20})
    assert sem.name == "改"
    assert sem.week_count == 20


def test_activate_semester_is_exclusive(db_session):
    a = semester_service.create_semester(db_session, name="A", first_monday=date(2026, 2, 24))
    b = semester_service.create_semester(db_session, name="B", first_monday=date(2026, 9, 1))
    db_session.commit()
    semester_service.activate_semester(db_session, a.id)
    semester_service.activate_semester(db_session, b.id)
    db_session.commit()
    db_session.refresh(a)
    db_session.refresh(b)
    assert b.is_current is True
    assert a.is_current is False


def test_resolve_building_type(db_session):
    sem = semester_service.create_semester(db_session, name="A", first_monday=date(2026, 9, 1))
    db_session.commit()
    assert semester_service.resolve_building_type(db_session, sem.id, "B608") == BuildingType.main
    assert semester_service.resolve_building_type(db_session, sem.id, "02-101") == BuildingType.second
    assert semester_service.resolve_building_type(db_session, sem.id, "X999") is None
