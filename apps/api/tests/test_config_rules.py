"""倍率规则、特殊日期、每日人数、初始化数据测试。"""
from __future__ import annotations

from datetime import date, time
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.models.enums import DayType, SpecialDateSource, VenueType
from app.models.special_date import SpecialDate
from app.models.venue import ShiftTemplate
from app.services import day_rule_service, multiplier_service, special_date_service


# --- 倍率规则 DB 校验 ---
def test_multiplier_same_priority_overlap_rejected(db_session):
    multiplier_service.create_rule(
        db_session, name="A", start_time=time(9, 0), end_time=time(11, 0),
        multiplier=Decimal("2.0"), priority=5, is_active=True,
    )
    db_session.commit()
    with pytest.raises(HTTPException) as ei:
        multiplier_service.create_rule(
            db_session, name="B", start_time=time(10, 0), end_time=time(12, 0),
            multiplier=Decimal("2.0"), priority=5, is_active=True,
        )
    assert ei.value.status_code == 422


def test_multiplier_end_midnight_maps_to_1440(db_session):
    rule = multiplier_service.create_rule(
        db_session, name="晚间", start_time=time(19, 0), end_time=time(0, 0),
        multiplier=Decimal("2.0"), priority=10, is_active=True,
    )
    engine = multiplier_service.to_engine_rule(rule)
    assert engine.start_min == 19 * 60
    assert engine.end_min == 1440


# --- 节假日同步解析 ---
def test_parse_holiday_json():
    data = {"days": [
        {"name": "国庆节", "date": "2026-10-01", "isOffDay": True},
        {"name": "国庆节", "date": "2026-10-11", "isOffDay": False},
    ]}
    items = special_date_service.parse_holiday_json(data)
    assert items[0]["day_type"] == DayType.weekend_rule.value  # 放假
    assert items[1]["day_type"] == DayType.workday.value  # 补班


def test_holiday_sync_preview_and_confirm(db_session):
    data = {"days": [{"name": "元旦", "date": "2027-01-01", "isOffDay": True}]}
    items = special_date_service.parse_holiday_json(data)
    preview = special_date_service.preview_sync(db_session, items)
    assert preview[0]["status"] == "new"
    # 确认前不得写入
    assert special_date_service.get_special_date(db_session, date(2027, 1, 1)) is None
    special_date_service.confirm_sync(db_session, actor_id=None, items=items)
    db_session.commit()
    sd = special_date_service.get_special_date(db_session, date(2027, 1, 1))
    assert sd is not None
    assert sd.source == SpecialDateSource.holiday_sync


# --- 每日人数规则 ---
def _shift():
    return ShiftTemplate(name="第1班", start_time=time(8, 0), end_time=time(10, 0),
                         credited_minutes=120, weekday_required_people=2, weekend_required_people=1)


def test_weekday_two_people():
    # 2026-03-02 是周一
    assert day_rule_service.resolve_required_people(date(2026, 3, 2), _shift(), None) == 2


def test_weekend_one_person():
    # 2026-03-07 是周六
    assert day_rule_service.resolve_required_people(date(2026, 3, 7), _shift(), None) == 1


def test_adjusted_workday_two_people():
    sd = SpecialDate(date=date(2026, 3, 7), day_type=DayType.workday, source=SpecialDateSource.manual)
    assert day_rule_service.resolve_required_people(date(2026, 3, 7), _shift(), sd) == 2


def test_holiday_weekend_rule_one_person():
    sd = SpecialDate(date=date(2026, 3, 3), day_type=DayType.weekend_rule, source=SpecialDateSource.manual)
    assert day_rule_service.resolve_required_people(date(2026, 3, 3), _shift(), sd) == 1


def test_closed_zero_people():
    sd = SpecialDate(date=date(2026, 3, 3), day_type=DayType.closed, source=SpecialDateSource.manual)
    assert day_rule_service.resolve_required_people(date(2026, 3, 3), _shift(), sd) == 0


# --- 初始化数据 ---
def test_init_data_seeds_venues_and_multipliers(db_session, monkeypatch):
    from app.db import init_data

    init_data.ensure_venues(db_session)
    init_data.ensure_multiplier_rules(db_session)
    db_session.commit()

    from sqlalchemy import select
    from app.models.venue import Venue

    venues = list(db_session.scalars(select(Venue)))
    assert {v.code for v in venues} == {"HL", "LT", "TSG"}
    yellow = next(v for v in venues if v.code == "HL")
    assert yellow.venue_type == VenueType.fixed_shift
    templates = list(db_session.scalars(select(ShiftTemplate).where(ShiftTemplate.venue_id == yellow.id)))
    assert len(templates) == 6
    assert all(t.credited_minutes == 120 for t in templates)
