"""工时计算引擎（方案 2.2 / 2.3 / 2.6 / 2.7）。

核心规则：
- 黄楼固定班次：直接采用固定 credited_minutes，不参与倍率与取整。
- 临时任务：完整值班时间 -> 倍率分段 -> 汇总加权分钟 -> 单次向上取整到 30 分钟。
- 倍率不叠乘；同一时刻命中多条规则时取优先级最高者；未命中按 1.0。
- 绝不对倍率分段分别取整，也绝不在月末合计后统一取整。

本模块为纯函数，不依赖数据库，便于单元测试。
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal

ROUND_UNIT_MINUTES = 30


@dataclass(frozen=True)
class MultiplierRule:
    """引擎级倍率规则（时间以“距零点分钟数”表达，[start_min, end_min)）。"""

    name: str
    start_min: int
    end_min: int  # 允许到 1440（表示 24:00）
    multiplier: Decimal
    priority: int  # 数值越大优先级越高
    venue_id: str | None = None  # None 表示适用全部场地
    weekdays: frozenset[int] | None = None  # 1=周一 .. 7=周日；None 表示全部
    effective_start_date: date | None = None
    effective_end_date: date | None = None
    is_active: bool = True

    def matches_instant(self, when: datetime, venue_id: str | None) -> bool:
        if not self.is_active:
            return False
        if self.venue_id is not None and self.venue_id != venue_id:
            return False
        iso_weekday = when.isoweekday()  # 1..7
        if self.weekdays is not None and iso_weekday not in self.weekdays:
            return False
        d = when.date()
        if self.effective_start_date is not None and d < self.effective_start_date:
            return False
        if self.effective_end_date is not None and d > self.effective_end_date:
            return False
        minute_of_day = when.hour * 60 + when.minute
        return self.start_min <= minute_of_day < self.end_min


@dataclass
class HourSegment:
    start_at: datetime
    end_at: datetime
    minutes: int
    multiplier: Decimal
    rule_name: str | None

    @property
    def weighted_minutes(self) -> Decimal:
        return Decimal(self.minutes) * self.multiplier


@dataclass
class TaskHourResult:
    raw_minutes: int
    weighted_minutes_before_round: Decimal
    credited_minutes: int
    segments: list[HourSegment] = field(default_factory=list)


class MultiplierConfigError(ValueError):
    """倍率配置非法（如相同优先级重叠）。"""


def _best_rule(when: datetime, rules: list[MultiplierRule], venue_id: str | None) -> MultiplierRule | None:
    best: MultiplierRule | None = None
    for rule in rules:
        if rule.matches_instant(when, venue_id):
            if best is None or rule.priority > best.priority:
                best = rule
    return best


def _breakpoints(duty_start: datetime, duty_end: datetime, rules: list[MultiplierRule]) -> list[datetime]:
    points: set[datetime] = {duty_start, duty_end}
    day = duty_start.date()
    last_day = duty_end.date()
    while day <= last_day:
        base = datetime.combine(day, datetime.min.time(), tzinfo=duty_start.tzinfo)
        for rule in rules:
            for minute in (rule.start_min, rule.end_min):
                pt = base + timedelta(minutes=minute)
                if duty_start < pt < duty_end:
                    points.add(pt)
        day += timedelta(days=1)
    return sorted(points)


def segment_weighted_minutes(
    duty_start: datetime,
    duty_end: datetime,
    rules: list[MultiplierRule],
    venue_id: str | None = None,
) -> tuple[int, Decimal, list[HourSegment]]:
    """将 [duty_start, duty_end) 按倍率规则分段并计算加权分钟。"""
    if duty_end <= duty_start:
        return 0, Decimal(0), []

    active_rules = [r for r in rules if r.is_active]
    points = _breakpoints(duty_start, duty_end, active_rules)
    segments: list[HourSegment] = []
    total_weighted = Decimal(0)
    raw_minutes = 0

    for a, b in zip(points, points[1:]):
        minutes = int((b - a).total_seconds() // 60)
        if minutes <= 0:
            continue
        midpoint = a + (b - a) / 2
        rule = _best_rule(midpoint, active_rules, venue_id)
        multiplier = rule.multiplier if rule else Decimal("1.0")
        seg = HourSegment(a, b, minutes, multiplier, rule.name if rule else None)
        segments.append(seg)
        total_weighted += seg.weighted_minutes
        raw_minutes += minutes

    return raw_minutes, total_weighted, segments


def round_up_30(weighted_minutes: Decimal) -> int:
    """向上取整到 30 分钟：ceil(加权分钟 / 30) * 30。"""
    if weighted_minutes <= 0:
        return 0
    units = math.ceil(weighted_minutes / Decimal(ROUND_UNIT_MINUTES))
    return units * ROUND_UNIT_MINUTES


def compute_event_task_hours(
    duty_start: datetime,
    duty_end: datetime,
    rules: list[MultiplierRule],
    venue_id: str | None = None,
) -> TaskHourResult:
    """临时任务（蓝厅 / 图书馆报告厅）工时：分段加权后单次向上取整。"""
    raw, weighted, segments = segment_weighted_minutes(duty_start, duty_end, rules, venue_id)
    credited = round_up_30(weighted)
    return TaskHourResult(
        raw_minutes=raw,
        weighted_minutes_before_round=weighted,
        credited_minutes=credited,
        segments=segments,
    )


def compute_fixed_shift_hours(credited_minutes: int, duty_start: datetime, duty_end: datetime) -> TaskHourResult:
    """黄楼固定班次：credited 直接采用模板固定值，不倍率、不取整。"""
    raw = int((duty_end - duty_start).total_seconds() // 60) if duty_end > duty_start else 0
    return TaskHourResult(
        raw_minutes=raw,
        weighted_minutes_before_round=Decimal(credited_minutes),
        credited_minutes=credited_minutes,
        segments=[],
    )


def validate_multiplier_rules(rules: list[MultiplierRule]) -> None:
    """相同优先级发生时间重叠时禁止保存（方案 2.6）。

    仅在同一适用场地/星期维度上判定重叠；venue=None 视为覆盖所有场地。
    """
    active = [r for r in rules if r.is_active]
    for i in range(len(active)):
        for j in range(i + 1, len(active)):
            a, b = active[i], active[j]
            if a.priority != b.priority:
                continue
            if not _venue_overlaps(a, b) or not _weekday_overlaps(a, b) or not _date_overlaps(a, b):
                continue
            if a.start_min < b.end_min and b.start_min < a.end_min:
                raise MultiplierConfigError(
                    f"倍率规则「{a.name}」与「{b.name}」在相同优先级 {a.priority} 下时间重叠"
                )


def _venue_overlaps(a: MultiplierRule, b: MultiplierRule) -> bool:
    return a.venue_id is None or b.venue_id is None or a.venue_id == b.venue_id


def _weekday_overlaps(a: MultiplierRule, b: MultiplierRule) -> bool:
    if a.weekdays is None or b.weekdays is None:
        return True
    return bool(a.weekdays & b.weekdays)


def _date_overlaps(a: MultiplierRule, b: MultiplierRule) -> bool:
    a_start = a.effective_start_date or date.min
    a_end = a.effective_end_date or date.max
    b_start = b.effective_start_date or date.min
    b_end = b.effective_end_date or date.max
    return a_start <= b_end and b_start <= a_end
