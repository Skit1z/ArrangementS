"""时间区间工具：合并重叠或相邻区间、判断相交。"""
from __future__ import annotations

from datetime import datetime


def merge_intervals(
    intervals: list[tuple[datetime, datetime]]
) -> list[tuple[datetime, datetime]]:
    """合并重叠或首尾相接的区间，返回按开始时间排序的最小集合。"""
    valid = [(s, e) for s, e in intervals if e > s]
    if not valid:
        return []
    valid.sort(key=lambda iv: iv[0])
    merged: list[tuple[datetime, datetime]] = [valid[0]]
    for start, end in valid[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:  # 重叠或相邻
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    """区间相交判断：任何大于 0 的重叠视为相交（半开区间语义）。

    容错：naive 与 aware datetime 混合时（SQLite 测试后端会丢 tz），
    把 aware 侧剥离 tzinfo 后按 naive 墙上时间比较——生产 Postgres 不会触发此分支。
    """
    vals = [a_start, a_end, b_start, b_end]
    has_naive = any(v.tzinfo is None for v in vals)
    has_aware = any(v.tzinfo is not None for v in vals)
    if has_naive and has_aware:
        # 混合：剥离 tzinfo，按墙上时间比较
        a_start, a_end = a_start.replace(tzinfo=None), a_end.replace(tzinfo=None)
        b_start, b_end = b_start.replace(tzinfo=None), b_end.replace(tzinfo=None)
    return a_start < b_end and b_start < a_end
