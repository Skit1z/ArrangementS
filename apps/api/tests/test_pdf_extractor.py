"""PDF 课表解析器测试。

样例 fixture: tests/fixtures/sample_timetable.pdf
（学校教务系统导出，rotation=90，文本层完整）
"""
from __future__ import annotations

from pathlib import Path

FIXTURE = Path(__file__).parent / "fixtures" / "sample_timetable.pdf"


def _bytes() -> bytes:
    return FIXTURE.read_bytes()


def test_open_pdf_and_find_weekday_headers():
    from app.timetable.pdf_extractor import PdfTimetableExtractor, find_weekday_anchors

    extractor = PdfTimetableExtractor()
    raw = _bytes()
    anchors = find_weekday_anchors(extractor._first_page_dict(raw))

    # 样例 PDF 包含完整 7 天列头
    assert set(anchors.keys()) == {1, 2, 3, 4, 5, 6, 7}
    # 星期一 y 最大（raw 坐标系下，因 rotation=90）
    assert anchors[1].y_center > anchors[7].y_center
    # 列头之间间隔应在 90–120pt 之间
    ys = sorted(a.y_center for a in anchors.values())
    gaps = [ys[i + 1] - ys[i] for i in range(len(ys) - 1)]
    assert all(80 < g < 130 for g in gaps), gaps


def test_extract_all_courses_from_sample():
    from app.timetable.pdf_extractor import PdfTimetableExtractor

    result = PdfTimetableExtractor().extract(_bytes(), "sample.pdf")
    # 样例 PDF 共 10 条课程条目
    assert len(result.entries) == 10, [str(e) for e in result.entries]
    assert not result.warnings, result.warnings


def test_extract_key_fields():
    from app.timetable.pdf_extractor import PdfTimetableExtractor

    entries = PdfTimetableExtractor().extract(_bytes()).entries

    # 周一 1-2 节，10-12 周，B132（形势与政策6）
    mon_12 = [e for e in entries if e.weekday == 1 and e.period_start == 1]
    assert len(mon_12) == 1
    e = mon_12[0]
    assert e.period_end == 2
    assert e.week_expr == "10-12周"
    assert e.location_code == "B132"

    # 周一 3-4 节，2-13 周，B608（供应链管理基础B）
    mon_34 = [e for e in entries if e.weekday == 1 and e.period_start == 3]
    assert len(mon_34) == 1
    assert mon_34[0].week_expr == "2-13周"
    assert mon_34[0].location_code == "B608"

    # 周三 3-4 节，3-13周(单)（供应链管理基础B 单周）
    wed_34 = [e for e in entries if e.weekday == 3 and e.period_start == 3]
    assert len(wed_34) == 1
    assert wed_34[0].week_expr == "3-13周(单)"
    assert wed_34[0].location_code == "B608"

    # 周二 5-6 节「电子商务 1-8周」+ 7-8 节「信息系统分析与设计 9-16周」
    tue_56 = [e for e in entries if e.weekday == 2 and e.period_start == 5]
    assert len(tue_56) == 1
    assert tue_56[0].week_expr == "1-8周"
    assert tue_56[0].location_code == "02-602"
    tue_78 = [e for e in entries if e.weekday == 2 and e.period_start == 7]
    assert len(tue_78) == 1
    assert tue_78[0].week_expr == "9-16周"
    assert tue_78[0].location_code == "02-501"

    # 周四 3-4 / 5-6 / 7-8 各一条
    thu = [e for e in entries if e.weekday == 4]
    assert {e.period_start for e in thu} == {3, 5, 7}
    thu_78 = [e for e in thu if e.period_start == 7]
    assert len(thu_78) == 1
    assert thu_78[0].week_expr == "2-5周"
    assert thu_78[0].location_code == "B203"

    # 周五 3-4 节「GIS 1-10周」+ 5-6 节「客户关系管理 2-17周」
    fri = [e for e in entries if e.weekday == 5]
    assert {e.period_start for e in fri} == {3, 5}
    fri_56 = [e for e in fri if e.period_start == 5]
    assert fri_56[0].week_expr == "2-17周"
    assert fri_56[0].location_code == "02-511"


def test_student_no_extracted():
    """学号从 PDF 头部抽取（用于前端核对，非业务必填）。"""
    from app.timetable.pdf_extractor import PdfTimetableExtractor

    result = PdfTimetableExtractor().extract(_bytes())
    assert result.student_no == "202301070410"
