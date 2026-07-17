"""工时计算引擎单元测试（覆盖方案 19.1 的关键场景）。"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from app.services.hours import (
    MultiplierConfigError,
    MultiplierRule,
    compute_event_task_hours,
    compute_fixed_shift_hours,
    round_up_30,
    segment_weighted_minutes,
    validate_multiplier_rules,
)

# 默认预置倍率：早间双倍 00:00-08:00、晚间双倍 19:00-24:00
EARLY = MultiplierRule("早间双倍", 0, 8 * 60, Decimal("2.0"), priority=10)
LATE = MultiplierRule("晚间双倍", 19 * 60, 24 * 60, Decimal("2.0"), priority=10)
DEFAULT_RULES = [EARLY, LATE]


def dt(y=2026, m=3, d=2, hh=0, mm=0) -> datetime:
    return datetime(y, m, d, hh, mm)


# --- 黄楼固定班次：前四班与后两班均固定 2 小时，不取整 ---
def test_yellow_first_four_shifts_fixed_two_hours():
    r = compute_fixed_shift_hours(120, dt(hh=8), dt(hh=10))
    assert r.credited_minutes == 120


def test_yellow_last_two_shifts_fixed_two_hours_not_1p5():
    # 16:00-17:30 实际 90 分钟，但 credited 固定 120（严禁按 1.5 小时统计）
    r = compute_fixed_shift_hours(120, dt(hh=16), dt(hh=17, mm=30))
    assert r.credited_minutes == 120
    r2 = compute_fixed_shift_hours(120, dt(hh=17, mm=30), dt(hh=19))
    assert r2.credited_minutes == 120


# --- 临时任务倍率与取整 ---
def test_all_normal_period():
    # 10:00-12:00 完全普通时段，120 分钟 ×1.0
    r = compute_event_task_hours(dt(hh=10), dt(hh=12), DEFAULT_RULES)
    assert r.weighted_minutes_before_round == Decimal("120")
    assert r.credited_minutes == 120


def test_all_double_period():
    # 20:00-22:00 完全晚间双倍，120 分钟 ×2 = 240
    r = compute_event_task_hours(dt(hh=20), dt(hh=22), DEFAULT_RULES)
    assert r.weighted_minutes_before_round == Decimal("240")
    assert r.credited_minutes == 240


def test_cross_1900_boundary():
    # 18:30-20:00：18:30-19:00(30min ×1) + 19:00-20:00(60min ×2)=30+120=150
    r = compute_event_task_hours(dt(hh=18, mm=30), dt(hh=20), DEFAULT_RULES)
    assert r.weighted_minutes_before_round == Decimal("150")
    assert r.credited_minutes == 150


def test_cross_0800_boundary():
    # 07:00-09:00：07:00-08:00(60 ×2) + 08:00-09:00(60 ×1)=120+60=180
    r = compute_event_task_hours(dt(hh=7), dt(hh=9), DEFAULT_RULES)
    assert r.weighted_minutes_before_round == Decimal("180")
    assert r.credited_minutes == 180


def test_custom_rule_overrides_default_by_priority():
    # 自定义 09:00-10:00 ×3，优先级更高，覆盖默认（默认此段本为 1.0）
    custom = MultiplierRule("特殊", 9 * 60, 10 * 60, Decimal("3.0"), priority=100)
    r = compute_event_task_hours(dt(hh=9), dt(hh=10), DEFAULT_RULES + [custom])
    assert r.weighted_minutes_before_round == Decimal("180")


def test_same_priority_overlap_rejected():
    a = MultiplierRule("A", 9 * 60, 11 * 60, Decimal("2.0"), priority=5)
    b = MultiplierRule("B", 10 * 60, 12 * 60, Decimal("2.0"), priority=5)
    with pytest.raises(MultiplierConfigError):
        validate_multiplier_rules([a, b])


def test_exact_multiple_of_30_no_extra_rounding():
    assert round_up_30(Decimal("90")) == 90
    assert round_up_30(Decimal("120")) == 120


def test_one_minute_over_rounds_up():
    assert round_up_30(Decimal("61")) == 90
    assert round_up_30(Decimal("91")) == 120
    assert round_up_30(Decimal("125")) == 150


def test_prep_and_cleanup_30_minutes():
    # 预约 09:30-10:30，提前 30、收尾 30 → 完整值班 09:00-11:00 = 120 分钟普通时段
    r = compute_event_task_hours(dt(hh=9), dt(hh=11), DEFAULT_RULES)
    assert r.raw_minutes == 120
    assert r.credited_minutes == 120


def test_no_split_rounding():
    # 18:20-19:20：18:20-19:00(40min ×1=40) + 19:00-19:20(20min ×2=40)=80 → 汇总取整=90。
    # 若错误地分段分别取整会得到 ceil(40/30)*30 + ceil(40/30)*30 = 60+60 = 120。
    r = compute_event_task_hours(dt(hh=18, mm=20), dt(hh=19, mm=20), DEFAULT_RULES)
    assert r.weighted_minutes_before_round == Decimal("80")
    assert r.credited_minutes == 90


def test_no_rule_matched_defaults_to_1():
    _, weighted, _ = segment_weighted_minutes(dt(hh=12), dt(hh=13), DEFAULT_RULES)
    assert weighted == Decimal("60")
