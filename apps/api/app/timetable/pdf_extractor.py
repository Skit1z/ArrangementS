"""学校教务系统 PDF 课表抽取器（方案见 docs/superpowers/specs/2026-07-19-pdf-timetable-upload-design.md）。

聚焦本校教务系统格式：页面 rotation=90，星期列头在 raw 坐标系的 y 轴上分布（每列约
间隔 104pt），课程描述形如 ``(3-4节)2-13周/校区:黄岛校区/场地:B608/...``。文本层完整，
无需 OCR。

公开入口：``PdfTimetableExtractor().extract(file_bytes, file_name) -> ExtractResult``。
"""
from __future__ import annotations

from dataclasses import dataclass

import pymupdf

from app.timetable.extractor import ExtractResult, RawCourseEntry

# 星期中文 -> 数字（1=周一 .. 7=周日）
_WEEKDAY_CN = {
    "星期一": 1, "星期二": 2, "星期三": 3, "星期四": 4,
    "星期五": 5, "星期六": 6, "星期日": 7,
}


@dataclass
class WeekdayAnchor:
    """星期列头在 raw PDF 坐标系下的位置。"""

    weekday: int
    y_center: float  # 列头垂直中心（raw y）
    x_center: float  # 列头水平中心（raw x）


def find_weekday_anchors(page_dict: dict) -> dict[int, WeekdayAnchor]:
    """从 ``page.get_text("dict")`` 的结果中找 7 个星期列头。

    返回 ``{weekday_int: WeekdayAnchor}``。若找不到全部 7 个，返回部分结果（调用方决定
    是否视为「非本校格式」错误）。
    """
    found: dict[int, WeekdayAnchor] = {}
    for block in page_dict.get("blocks", []):
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = (span.get("text") or "").strip()
                if text in _WEEKDAY_CN:
                    wd = _WEEKDAY_CN[text]
                    x0, y0, x1, y1 = span["bbox"]
                    found[wd] = WeekdayAnchor(
                        weekday=wd,
                        y_center=(y0 + y1) / 2,
                        x_center=(x0 + x1) / 2,
                    )
    return found


class PdfTimetableExtractor:
    """学校教务系统 PDF 课表抽取器。"""

    def _first_page_dict(self, file_bytes: bytes) -> dict:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        if doc.page_count == 0:
            raise ValueError("PDF 无页面")
        # rotation 不影响 get_text("dict") 的原始坐标
        return doc[0].get_text("dict")

    def extract(self, file_bytes: bytes, file_name: str = "timetable.pdf") -> ExtractResult:
        """主入口。Task 3 起补全课程抽取逻辑，当前只识别星期列头。"""
        page_dict = self._first_page_dict(file_bytes)
        anchors = find_weekday_anchors(page_dict)
        result = ExtractResult()
        if len(anchors) < 7:
            result.warnings.append("无法识别全部 7 个星期列头，可能非本校教务系统格式")
        return result
