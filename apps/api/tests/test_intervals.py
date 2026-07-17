"""区间合并与相交测试。"""
from __future__ import annotations

from datetime import datetime

from app.services.intervals import merge_intervals, overlaps


def d(hh, mm=0):
    return datetime(2026, 8, 1, hh, mm)


def test_merge_overlapping():
    result = merge_intervals([(d(9), d(11)), (d(10), d(12))])
    assert result == [(d(9), d(12))]


def test_merge_adjacent():
    result = merge_intervals([(d(9), d(10)), (d(10), d(11))])
    assert result == [(d(9), d(11))]


def test_merge_disjoint_sorted():
    result = merge_intervals([(d(14), d(15)), (d(9), d(10))])
    assert result == [(d(9), d(10)), (d(14), d(15))]


def test_merge_drops_empty():
    assert merge_intervals([(d(9), d(9)), (d(10), d(9))]) == []


def test_overlaps():
    assert overlaps(d(9), d(11), d(10), d(12))
    assert not overlaps(d(9), d(10), d(10), d(11))  # 半开区间相邻不算相交
