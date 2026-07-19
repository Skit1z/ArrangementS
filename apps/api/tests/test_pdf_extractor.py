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
