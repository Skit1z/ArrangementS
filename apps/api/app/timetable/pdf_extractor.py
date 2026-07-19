"""学校教务系统 PDF 课表抽取器（方案见 docs/superpowers/specs/2026-07-19-pdf-timetable-upload-design.md）。

聚焦本校教务系统格式：页面 rotation=90，文本以「旋转列」形式排版 —— 每个课程描述
行的不同片段是独立的 block，按 x 坐标递增分布；星期列头在 raw 坐标系的 y 轴上
每列约间隔 104pt。

抽取策略：
1. 用星期列头 y 坐标做锚点，把所有文本 span 按其 y 归属到 7 个星期桶（容差 52pt）。
2. 每个星期桶内按 (x, y) 排序后拼接，得到该星期完整的阅读顺序文本。
3. 用正则 ``\\((\\d+)-(\\d+)节\\)\\s*(周次表达)`` 找课程描述行，再在后续文本里
   找 ``/场地:CODE/``。课程名作为 best-effort 字段（取描述行前最近一个带 ★/○/●/◇/◆
   标记的文本），前端不展示。

公开入口：``PdfTimetableExtractor().extract(file_bytes, file_name) -> ExtractResult``。
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

import pymupdf

from app.timetable.extractor import ExtractResult, RawCourseEntry

# 星期中文 -> 数字（1=周一 .. 7=周日）
_WEEKDAY_CN = {
    "星期一": 1, "星期二": 2, "星期三": 3, "星期四": 4,
    "星期五": 5, "星期六": 6, "星期日": 7,
}

# 课程描述行：(3-4节)2-13周 或 (3-4节)3-13周(单) 或 (1-2节)10-12周
_COURSE_DESC_RE = re.compile(
    r"\((\d{1,2})-(\d{1,2})节\)\s*"
    r"(\d+(?:-\d+)?周(?:\((?:单|双)\))?)"
)
# 场地代码：在描述行之后的文本里找 /场地:XXX/
_LOCATION_RE = re.compile(r"/场地:([^/]+?)/")
# 学号
_STUDENT_NO_RE = re.compile(r"学号[：:]\s*(\d+)")
# 课程名标记符号
_COURSE_MARKERS = "★○●◇◆"
# 课程名：带标记符号结尾的中文串（标记符号用作定位锚点）
_COURSE_NAME_RE = re.compile(r"([^()/：:\d][^()/：:]{1,29}?)([★○●◇◆])")
# 课程名清理：去掉前导的星期头、节次相关残留
_NAME_PREFIX_NOISE = (
    "星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日",
    "重修", "标记", "课表",
)
# 课程名中可能残留的学生姓名 + 「课表」标题（如 "王文博课表星期四电子商务"）
# 由于课程名只是 best-effort 辅助字段、前端不展示，这里只做基础清理。


@dataclass
class WeekdayAnchor:
    """星期列头在 raw PDF 坐标系下的位置。"""

    weekday: int
    y_center: float
    x_center: float


def find_weekday_anchors(page_dict: dict) -> dict[int, WeekdayAnchor]:
    """从 ``page.get_text("dict")`` 的结果中找 7 个星期列头。

    返回 ``{weekday_int: WeekdayAnchor}``。若找不到全部 7 个，返回部分结果。
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


# 每个星期桶的 y 容差（半个列间距）
_WEEKDAY_Y_TOLERANCE = 52.0


class PdfTimetableExtractor:
    """学校教务系统 PDF 课表抽取器。"""

    def _first_page_dict(self, file_bytes: bytes) -> dict:
        doc = pymupdf.open(stream=file_bytes, filetype="pdf")
        if doc.page_count == 0:
            raise ValueError("PDF 无页面")
        # rotation 不影响 get_text("dict") 的原始坐标
        return doc[0].get_text("dict")

    def extract(self, file_bytes: bytes, file_name: str = "timetable.pdf") -> ExtractResult:
        """主入口：PDF bytes -> ExtractResult。"""
        page_dict = self._first_page_dict(file_bytes)
        result = ExtractResult()

        anchors = find_weekday_anchors(page_dict)
        if len(anchors) < 7:
            result.warnings.append("无法识别全部 7 个星期列头，可能非本校教务系统格式")
            return result

        # 学号：扫所有 span
        student_no: str | None = None
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                line_text = "".join(s.get("text", "") for s in line["spans"])
                m = _STUDENT_NO_RE.search(line_text)
                if m:
                    student_no = m.group(1)
                    break
            if student_no:
                break
        result.student_no = student_no

        # 把 span 按 y 归属到星期桶
        by_weekday: dict[int, list[tuple[float, float, str]]] = defaultdict(list)
        for block in page_dict.get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "")
                    if not text:
                        continue
                    y = (span["bbox"][1] + span["bbox"][3]) / 2
                    x = span["bbox"][0]
                    wd = _match_weekday(anchors, y)
                    if wd is None:
                        continue
                    by_weekday[wd].append((x, y, text))

        entries: list[RawCourseEntry] = []
        for wd, items in by_weekday.items():
            # 旋转排版：同一天的课程描述行片段按 x 递增；按 (x, y) 排序还原阅读顺序
            items.sort(key=lambda it: (it[0], it[1]))
            full_text = "".join(t for _, _, t in items)
            entries.extend(self._extract_from_weekday_text(wd, full_text, result.warnings))

        if not entries and not result.warnings:
            result.warnings.append("未在 PDF 中识别到任何课程")
        result.entries = entries
        return result

    def _extract_from_weekday_text(
        self, weekday: int, full_text: str, warnings: list[str]
    ) -> list[RawCourseEntry]:
        """从单个星期的拼接文本里抽课程条目。"""
        # 预扫课程名锚点（带标记符号的中文串）
        name_hits = list(_COURSE_NAME_RE.finditer(full_text))

        entries: list[RawCourseEntry] = []
        for m in _COURSE_DESC_RE.finditer(full_text):
            period_start = int(m.group(1))
            period_end = int(m.group(2))
            week_expr = m.group(3)

            # 场地在描述行之后的 200 字符内查找
            tail = full_text[m.end():m.end() + 200]
            loc_m = _LOCATION_RE.search(tail)
            location_code = loc_m.group(1).strip() if loc_m else None

            # 课程名：描述行之前最近的带标记符号的文本
            course_name = None
            for nh in name_hits:
                if nh.end() <= m.start():
                    candidate = nh.group(1).strip()
                    # 去掉前导噪声（星期头、重修残留等）
                    for noise in _NAME_PREFIX_NOISE:
                        if candidate.startswith(noise):
                            candidate = candidate[len(noise):]
                    candidate = candidate.strip()
                    if candidate:
                        course_name = candidate
                else:
                    break

            entries.append(
                RawCourseEntry(
                    weekday=weekday,
                    period_start=period_start,
                    period_end=period_end,
                    week_expr=week_expr,
                    location_code=location_code,
                    course_name=course_name,
                    confidence=1.0 if location_code else 0.8,
                )
            )
        return entries


def _match_weekday(anchors: dict[int, WeekdayAnchor], y: float) -> int | None:
    """按 y 坐标找最近的星期列头（容差 _WEEKDAY_Y_TOLERANCE）。"""
    if not anchors:
        return None
    best = min(anchors.values(), key=lambda a: abs(a.y_center - y))
    if abs(best.y_center - y) > _WEEKDAY_Y_TOLERANCE:
        return None
    return best.weekday
