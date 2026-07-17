"""按日期解析黄楼班次所需人数（方案 2.2）。

优先级：特殊日期覆盖 > 周末规则 > 工作日规则。
- 停班 closed -> 0
- 自定义 custom -> custom_required_people
- 调休工作日 workday -> 工作日人数
- 法定节假日/周末规则 weekend_rule -> 周末人数
- 无特殊日期：周一至周五=工作日人数，周六周日=周末人数
"""
from __future__ import annotations

from datetime import date

from app.models.enums import DayType
from app.models.special_date import SpecialDate
from app.models.venue import ShiftTemplate


def resolve_required_people(
    day: date, shift: ShiftTemplate, special: SpecialDate | None
) -> int:
    if special is not None:
        if special.day_type == DayType.closed:
            return 0
        if special.day_type == DayType.custom:
            return special.custom_required_people or 0
        if special.day_type == DayType.workday:
            return shift.weekday_required_people
        if special.day_type == DayType.weekend_rule:
            return shift.weekend_required_people
    # 无特殊日期：ISO 周一=1 .. 周日=7
    if day.isoweekday() >= 6:
        return shift.weekend_required_people
    return shift.weekday_required_people
