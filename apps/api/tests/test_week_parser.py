"""周次表达解析测试（方案 4.5）。"""

from __future__ import annotations

import pytest

from app.timetable.week_parser import WeekParseError, parse_weeks


def test_simple_range():
    assert parse_weeks("1-8周").explicit_weeks == list(range(1, 9))


def test_full_range():
    spec = parse_weeks("2-17周")
    assert spec.week_start == 2 and spec.week_end == 17
    assert len(spec.explicit_weeks) == 16


def test_odd_weeks():
    spec = parse_weeks("3-13周(单)")
    assert spec.parity == "odd"
    assert spec.explicit_weeks == [3, 5, 7, 9, 11, 13]


def test_even_weeks():
    spec = parse_weeks("2-14周(双)")
    assert spec.parity == "even"
    assert spec.explicit_weeks == [2, 4, 6, 8, 10, 12, 14]


def test_explicit_list():
    assert parse_weeks("1,3,5,7周").explicit_weeks == [1, 3, 5, 7]


def test_mixed_ranges():
    assert parse_weeks("1-4,6-8周").explicit_weeks == [1, 2, 3, 4, 6, 7, 8]


def test_single_week():
    assert parse_weeks("9周").explicit_weeks == [9]


def test_chinese_comma_and_paren():
    spec = parse_weeks("3-13周（单）")
    assert spec.explicit_weeks == [3, 5, 7, 9, 11, 13]


def test_out_of_range_warns_and_clips():
    spec = parse_weeks("18-25周")
    assert spec.warnings
    assert spec.explicit_weeks == [18, 19, 20]


def test_invalid_raises():
    with pytest.raises(WeekParseError):
        parse_weeks("abc")
    with pytest.raises(WeekParseError):
        parse_weeks("")
