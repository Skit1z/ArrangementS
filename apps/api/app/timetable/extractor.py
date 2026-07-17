"""课表抽取层抽象（方案 4.4）。

双路径：PDF 文本解析（PyMuPDF/pdfplumber）优先，OCR（PaddleOCR）备用。二者最终都产出
统一的 RawCourseEntry 列表，交给 timetable_service 规范化为 CourseRule 并进入人工预览确认。

本文件定义统一数据结构与协议；具体 PDF/OCR 实现为可选重依赖，接入真实样例时补全。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class RawCourseEntry:
    """抽取出的一条原始课程（尚未解析周次/时间/建筑）。"""

    weekday: int  # 1=周一 .. 7=周日
    period_start: int
    period_end: int
    week_expr: str  # 原始周次表达，如 "3-13周(单)"
    location_code: str | None = None
    course_name: str | None = None
    confidence: float | None = None


@dataclass
class ExtractResult:
    student_no: str | None = None
    full_name: str | None = None
    entries: list[RawCourseEntry] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class TimetableExtractor(Protocol):
    def extract(self, file_bytes: bytes, file_name: str) -> ExtractResult: ...


class ManualEntryExtractor:
    """结构化手工录入 / 已由前端解析后回传的路径（无需重依赖）。"""

    def extract_from_entries(self, entries: list[dict]) -> ExtractResult:
        parsed = [
            RawCourseEntry(
                weekday=int(e["weekday"]),
                period_start=int(e["period_start"]),
                period_end=int(e["period_end"]),
                week_expr=str(e["week_expr"]),
                location_code=e.get("location_code"),
                course_name=e.get("course_name"),
                confidence=e.get("confidence"),
            )
            for e in entries
        ]
        return ExtractResult(entries=parsed)


def get_pdf_extractor() -> TimetableExtractor:
    """延迟导入 PDF 抽取实现（依赖 pymupdf/pdfplumber，可选安装）。"""
    try:
        from app.timetable.pdf_extractor import PdfTimetableExtractor
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "PDF 解析依赖未安装，请 `uv pip install -e '.[timetable]'` 或改用手工录入路径"
        ) from exc
    return PdfTimetableExtractor()
