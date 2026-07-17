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
    """区间相交判断：任何大于 0 的重叠视为相交（半开区间语义）。"""
    return a_start < b_end and b_start < a_end
