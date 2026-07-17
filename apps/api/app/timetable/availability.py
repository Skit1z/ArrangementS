"""课程规则 -> 具体日期不可值班区间（方案 4.1 / 4.7）。

纯函数，便于单元测试。时间解析依据学期课程节次规则，日期依据第一周星期一。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

from app.models.enums import BuildingType


@dataclass
class PeriodTime:
    period_start: int
    period_end: int
    building_type: BuildingType
    start_time: time
    end_time: time


def _parse_group(group: str) -> tuple[int, int]:
    parts = group.replace("节", "").split("-")
    if len(parts) == 2:
        return int(parts[0]), int(parts[1])
    v = int(parts[0])
    return v, v


def period_time_from_rule(rule) -> PeriodTime:
    """将 ORM CoursePeriodRule（含 period_group 字符串）转换为 PeriodTime。"""
    lo, hi = _parse_group(rule.period_group)
    return PeriodTime(lo, hi, rule.building_type, rule.start_time, rule.end_time)


def resolve_period_time(
    period_rules: list[PeriodTime],
    building_type: BuildingType,
    period_start: int,
    period_end: int,
) -> tuple[time, time] | None:
    """按建筑类型（精确优先，其次 all）解析课程起止时间。未命中返回 None。"""

    def find_time(bt: BuildingType, period: int, which: str) -> time | None:
        for r in period_rules:
            if r.building_type == bt and r.period_start <= period <= r.period_end:
                return r.start_time if which == "start" else r.end_time
        return None

    start = find_time(building_type, period_start, "start")
    end = find_time(building_type, period_end, "end")
    if start is None:
        start = find_time(BuildingType.all, period_start, "start")
    if end is None:
        end = find_time(BuildingType.all, period_end, "end")
    if start is None or end is None:
        return None
    return start, end


def course_date(first_monday: date, week: int, weekday: int) -> date:
    """weekday: 1=周一 .. 7=周日。"""
    return first_monday + timedelta(days=(week - 1) * 7 + (weekday - 1))


def generate_intervals(
    first_monday: date,
    weekday: int,
    start_time: time,
    end_time: time,
    weeks: list[int],
    buffer_minutes: int = 0,
) -> list[tuple[datetime, datetime]]:
    """为每个教学周生成一条不可值班区间，含课程冲突缓冲。"""
    intervals: list[tuple[datetime, datetime]] = []
    delta = timedelta(minutes=buffer_minutes)
    for week in sorted(set(weeks)):
        d = course_date(first_monday, week, weekday)
        start = datetime.combine(d, start_time) - delta
        end = datetime.combine(d, end_time) + delta
        intervals.append((start, end))
    return intervals
