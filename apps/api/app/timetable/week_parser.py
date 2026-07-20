"""周次表达解析（方案 4.5）。

支持：
- ``1-8周`` / ``2-17周``
- ``3-13周(单)`` / ``2-14周(双)``
- ``1,3,5,7周``
- ``1-4,6-8周``
- 单个周次

输出规范化为具体周次集合（受 max_week 限制），并保留 parity 与首尾周供展示。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_MAX_WEEK = 20

_PARITY_ODD = {"单", "单周", "odd"}
_PARITY_EVEN = {"双", "双周", "even"}
_RANGE_RE = re.compile(r"^(\d+)\s*[-~—]\s*(\d+)$")
_SINGLE_RE = re.compile(r"^(\d+)$")
_PARITY_RE = re.compile(r"[（(]\s*(单|双|单周|双周)\s*[)）]")


class WeekParseError(ValueError):
    pass


@dataclass
class WeekSpec:
    weeks: set[int]
    parity: str = "all"  # all / odd / even
    week_start: int | None = None
    week_end: int | None = None
    explicit_weeks: list[int] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def parse_weeks(expr: str, max_week: int = DEFAULT_MAX_WEEK) -> WeekSpec:
    if not expr or not expr.strip():
        raise WeekParseError("空周次表达")

    text = expr.strip()
    parity = "all"
    m = _PARITY_RE.search(text)
    if m:
        marker = m.group(1)
        parity = "odd" if marker in _PARITY_ODD else "even"
        text = _PARITY_RE.sub("", text)

    # 去除“周”“第”及空白
    text = text.replace("周", "").replace("第", "").replace("节", "").strip()
    text = text.replace("，", ",")

    weeks: set[int] = set()
    warnings: list[str] = []
    for token in filter(None, (t.strip() for t in text.split(","))):
        rng = _RANGE_RE.match(token)
        if rng:
            a, b = int(rng.group(1)), int(rng.group(2))
            if a > b:
                a, b = b, a
            for w in range(a, b + 1):
                weeks.add(w)
            continue
        single = _SINGLE_RE.match(token)
        if single:
            weeks.add(int(single.group(1)))
            continue
        raise WeekParseError(f"无法解析周次片段：{token!r}")

    if parity == "odd":
        weeks = {w for w in weeks if w % 2 == 1}
    elif parity == "even":
        weeks = {w for w in weeks if w % 2 == 0}

    out_of_range = sorted(w for w in weeks if w < 1 or w > max_week)
    if out_of_range:
        warnings.append(f"周次 {out_of_range} 超出 1-{max_week} 范围，已忽略")
    weeks = {w for w in weeks if 1 <= w <= max_week}

    if not weeks:
        raise WeekParseError(f"解析后无有效周次：{expr!r}")

    ordered = sorted(weeks)
    return WeekSpec(
        weeks=weeks,
        parity=parity,
        week_start=ordered[0],
        week_end=ordered[-1],
        explicit_weeks=ordered,
        warnings=warnings,
    )
