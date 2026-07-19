# PDF 课表上传与解析 — 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用户/admin 上传学校教务系统 PDF 课表，系统解析后自动反映到「有课表/无课表」（即可用性矩阵），无需 admin 审核。

**Architecture:** PDF 文本层抽取（PyMuPDF）→ 按星期列头坐标归属 → 正则抽节次/周次/场地 → 复用现有 `week_parser` / `availability` / `timetable_service` 流水线，跳过 admin 审核直接生效。拆三个端点 `/parse-pdf` → `/upload` → `/approve`，复用现有路径以保留「上传前预览确认」语义。

**Tech Stack:** Python 3.12 / FastAPI / SQLAlchemy 2 / PyMuPDF（新增运行时依赖）/ pytest；React + TypeScript + Ant Design + react-query。

**Spec:** [`docs/superpowers/specs/2026-07-19-pdf-timetable-upload-design.md`](../specs/2026-07-19-pdf-timetable-upload-design.md)

---

## 关键技术调研结论（已用样例 PDF 验证）

样例 PDF `apps/api/tests/fixtures/sample_timetable.pdf` 几何：
- 页面 `rotation=90`，mediabox `(0,0,595,842)`，rect `(0,0,842,595)`
- **星期列头**（星期一..星期日）在 raw 坐标系下分布在 y 轴上，每列约间隔 104pt：
  - 星期日 y≈49.9，星期六 y≈153.8，星期五 y≈257.6，星期四 y≈361.5，星期三 y≈465.3，星期二 y≈569.2，星期一 y≈673.0
- **课程描述块**首行形如 `(3-4节)2-13周/校区:黄岛校...`，y0 在 227–645 之间
- **课程名**（如 `供应链管理基础B★`）是**独立的另一个 block**，位于描述块上方约 15–25pt 处
- 用 `page.get_text("dict")` 取原始坐标即可，**不要**依赖 `page.rotation`

每个课程单元格的元数据用 `/` 分隔，稳定结构：
```
(N-N节)X-Y周/校区:黄岛校区/场地:B608/教师:武华华/教学班:.../学分:2.5/重修标记:
```
节次、周次（含单/双周）、场地（location_code）、校区均可正则抽取。

---

## 文件清单

### 新建
| 路径 | 职责 |
|---|---|
| `apps/api/app/timetable/pdf_extractor.py` | PDF bytes → `list[RawCourseEntry]`（核心解析器） |
| `apps/api/tests/test_pdf_extractor.py` | 解析器单元测试 |
| `apps/api/tests/test_timetable_upload_pdf_api.py` | PDF 上传端到端 API 测试 |
| `apps/api/tests/fixtures/sample_timetable.pdf` | 测试样例 PDF（**已就位**） |
| `apps/web/src/pages/user/UploadTimetablePage.tsx` | 用户上传 + 预览确认 UI |

### 修改
| 路径 | 改动 |
|---|---|
| `apps/api/pyproject.toml` | `pymupdf>=1.24` 从 optional `[timetable]` 移到必装 `dependencies` |
| `apps/api/app/timetable/extractor.py` | `get_pdf_extractor()` 已存在，无需改 |
| `apps/api/app/schemas/timetable.py` | 新增 `ParsedPdfOut`（解析结果不入库的响应） |
| `apps/api/app/api/v1/timetables.py` | 新增 `POST /timetables/parse-pdf`；放开 `/approve` 给「admin 或 upload 本人」 |
| `apps/api/app/services/people_service.py` | 复用已有 `get_person_by_user`，无需改 |
| `apps/web/src/features/me/api.ts` | 新增 `meApi.timetable.parsePdf / upload / approve / myActive` |
| `apps/web/src/router.tsx` | 注册 `/app/timetable` 路由 |
| `apps/web/src/layouts/UserLayout.tsx` | 移动端底栏加「课表」入口 |
| `apps/web/src/pages/user/HomePage.tsx` | 首页加「上传我的课表」快捷入口卡片 |
| `apps/web/src/pages/admin/TimetablesPage.tsx` | admin 视图加「为某人代传课表」按钮 |

---

## Task 1：把 pymupdf 提升为必装依赖并验证可导入

**Files:**
- Modify: `apps/api/pyproject.toml`

- [ ] **Step 1: 修改 pyproject.toml**

把 `pymupdf` 从 `[project.optional-dependencies].timetable` 移到 `dependencies`。

打开 `apps/api/pyproject.toml`，找到：

```toml
    "apscheduler>=3.10",
]

[project.optional-dependencies]
timetable = ["pymupdf>=1.24", "pdfplumber>=0.11"]
dev = [
```

改为：

```toml
    "apscheduler>=3.10",
    "pymupdf>=1.24",
]

[project.optional-dependencies]
dev = [
```

（删除 `timetable` optional group 整行；`pdfplumber` 不再需要，PyMuPDF 已够用。）

- [ ] **Step 2: 安装新依赖**

Run:
```bash
cd apps/api && uv pip install -e ".[dev]"
```
Expected: 安装成功，`pymupdf` 出现在依赖列表中。

- [ ] **Step 3: 验证可导入**

Run:
```bash
cd apps/api && .venv/bin/python -c "import pymupdf; print(pymupdf.__version__)"
```
Expected: 打印版本号（≥1.24），无 ImportError。

- [ ] **Step 4: 跑一遍现有测试确保未破坏**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```
Expected: 全部通过。

- [ ] **Step 5: Commit**

```bash
git add apps/api/pyproject.toml apps/api/uv.lock
git commit -m "deps: promote pymupdf to required dependency for PDF timetable parsing"
```

---

## Task 2：PDF 解析器骨架 + 星期列头识别（TDD）

**Files:**
- Create: `apps/api/app/timetable/pdf_extractor.py`
- Create: `apps/api/tests/test_pdf_extractor.py`
- Test fixture: `apps/api/tests/fixtures/sample_timetable.pdf`（已就位）

本 Task 只实现「打开 PDF + 识别 7 个星期列头 + 返回 weekday→y_center 映射」，作为后续抽取的地基。

- [ ] **Step 1: 写失败测试 — 能打开样例 PDF 并识别 7 个星期列头**

创建 `apps/api/tests/test_pdf_extractor.py`：

```python
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
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_pdf_extractor.py -v
```
Expected: FAIL，`ModuleNotFoundError: No module named 'app.timetable.pdf_extractor'`。

- [ ] **Step 3: 实现骨架**

创建 `apps/api/app/timetable/pdf_extractor.py`：

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_pdf_extractor.py -v
```
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/timetable/pdf_extractor.py apps/api/tests/test_pdf_extractor.py apps/api/tests/fixtures/sample_timetable.pdf
git commit -m "feat(timetable): PDF extractor skeleton with weekday anchor detection"
```

---

## Task 3：课程描述块抽取（节次/周次/场地）

**Files:**
- Modify: `apps/api/app/timetable/pdf_extractor.py`
- Modify: `apps/api/tests/test_pdf_extractor.py`

实现核心：从每个课程描述块抽出 `(period_start, period_end, week_expr, location_code)`，按 y 坐标归属 weekday。课程名作为可选字段，best-effort 抽取。

- [ ] **Step 1: 写失败测试 — 抽出样例 PDF 的全部 10 条课程**

追加到 `apps/api/tests/test_pdf_extractor.py` 末尾：

```python
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

    # 周三 3-4 节，3-13周(单)（供应链管理基础B 单周）
    wed_34 = [e for e in entries if e.weekday == 3 and e.period_start == 3]
    assert len(wed_34) == 1
    assert wed_34[0].week_expr == "3-13周(单)"
    assert wed_34[0].location_code == "B608"

    # 周四 3-4 节有「电子商务 1-8周」和「信息系统分析与设计 9-16周」两条
    thu_34 = [e for e in entries if e.weekday == 4 and e.period_start == 3]
    assert len(thu_34) == 2
    week_exprs = {e.week_expr for e in thu_34}
    assert week_exprs == {"1-8周", "9-16周"}

    # 周四 5-6 节有「信息系统分析与设计 9-16周」和「客户关系管理 2-17周」两条
    thu_56 = [e for e in entries if e.weekday == 4 and e.period_start == 5]
    assert len(thu_56) == 2
    assert {e.week_expr for e in thu_56} == {"9-16周", "2-17周"}

    # 周四 7-8 节「就业指导 2-5周」
    thu_78 = [e for e in entries if e.weekday == 4 and e.period_start == 7]
    assert len(thu_78) == 1
    assert thu_78[0].week_expr == "2-5周"


def test_student_no_extracted():
    """学号从 PDF 头部抽取（用于前端核对，非业务必填）。"""
    from app.timetable.pdf_extractor import PdfTimetableExtractor

    result = PdfTimetableExtractor().extract(_bytes())
    assert result.student_no == "202301070410"
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_pdf_extractor.py -v
```
Expected: 3 个新测试 FAIL（`entries` 为空）。

- [ ] **Step 3: 实现核心抽取逻辑**

在 `apps/api/app/timetable/pdf_extractor.py` 顶部 import 区后追加常量与正则：

```python
import re

# 课程描述行： (3-4节)2-13周 或 (3-4节)3-13周(单) 或 (1-2节)10-12周
# 周次支持： X-Y周 / X-Y周(单) / X-Y周(双) / X周
_COURSE_DESC_RE = re.compile(
    r"\((\d{1,2})-(\d{1,2})节\)\s*"            # (3-4节)
    r"(\d+(?:-\d+)?周(?:\((?:单|双)\))?)"        # 2-13周 / 3-13周(单)
)
_LOCATION_RE = re.compile(r"/场地:([^/]+?)/")
_CAMPUS_RE = re.compile(r"/校区:([^/]+?)/")
_STUDENT_NO_RE = re.compile(r"学号[：:]\s*(\d+)")
# 课程名行：以中英文开头，末尾常带 ★○●◇◆ 标记
_COURSE_NAME_TAIL_RE = re.compile(r"[★○●◇◆：:]+$")
# 应忽略的非课程文本块首行
_IGNORE_LINE_KEYWORDS = ("时间段", "节次", "上午", "下午", "晚上", "学号", "学期", "课表", "打印时间")
```

把 `PdfTimetableExtractor.extract` 替换为以下完整实现（同时保留 `_first_page_dict` 不变）：

```python
    def extract(self, file_bytes: bytes, file_name: str = "timetable.pdf") -> ExtractResult:
        page_dict = self._first_page_dict(file_bytes)
        result = ExtractResult()

        anchors = find_weekday_anchors(page_dict)
        if len(anchors) < 7:
            result.warnings.append("无法识别全部 7 个星期列头，可能非本校教务系统格式")
            return result

        # 把 blocks 按出现顺序排好（按 y0 升序，raw 坐标系下 y 越小越靠「星期日」）
        blocks = [b for b in page_dict.get("blocks", []) if "lines" in b]

        # 第一遍：抽学号
        for block in blocks:
            for line in block["lines"]:
                line_text = "".join(s.get("text", "") for s in line["spans"])
                m = _STUDENT_NO_RE.search(line_text)
                if m:
                    result.student_no = m.group(1)
                    break
            if result.student_no:
                break

        # 准备课程名候选：所有首行不是描述行、不含忽略词、长度 ≤30 的文本块，
        # 按 (y_center, x_center) 索引，供描述块向上查找课程名
        name_candidates: list[tuple[float, float, str]] = []
        for block in blocks:
            if not block["lines"]:
                continue
            first_line = "".join(s.get("text", "") for s in block["lines"][0]["spans"]).strip()
            if not first_line or _COURSE_DESC_RE.search(first_line):
                continue
            if any(k in first_line for k in _IGNORE_LINE_KEYWORDS):
                continue
            if first_line.isdigit():  # 节次行号如 "3"
                continue
            cleaned = _COURSE_NAME_TAIL_RE.sub("", first_line).strip()
            if not cleaned or len(cleaned) > 30:
                continue
            bx0, by0, bx1, by1 = block["bbox"]
            name_candidates.append(((by0 + by1) / 2, (bx0 + bx1) / 2, cleaned))

        # 第二遍：对每个含描述行的 block 抽课程
        entries: list[RawCourseEntry] = []
        for block in blocks:
            block_text = "".join(
                s.get("text", "")
                for line in block.get("lines", [])
                for s in line.get("spans", [])
            )
            m = _COURSE_DESC_RE.search(block_text)
            if not m:
                continue
            period_start = int(m.group(1))
            period_end = int(m.group(2))
            week_expr = m.group(3)

            bx0, by0, bx1, by1 = block["bbox"]
            block_y = (by0 + by1) / 2
            block_x = (bx0 + bx1) / 2
            weekday = _match_weekday(anchors, block_y)
            if weekday is None:
                result.warnings.append(
                    f"无法归属星期：节次{period_start}-{period_end} 周{week_expr} (y={block_y:.1f})"
                )
                continue

            loc_m = _LOCATION_RE.search(block_text)
            location_code = loc_m.group(1).strip() if loc_m else None

            # best-effort 课程名：往上找最近的 name_candidate（y 比本块小、x 重叠）
            course_name = _find_course_name(name_candidates, block_y, block_x, by0)

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

        if not entries:
            result.warnings.append("未在 PDF 中识别到任何课程")
        result.entries = entries
        return result


def _match_weekday(anchors: dict[int, WeekdayAnchor], y: float) -> int | None:
    """按 y 坐标找最近的星期列头。"""
    if not anchors:
        return None
    best = min(anchors.values(), key=lambda a: abs(a.y_center - y))
    # 容忍 60pt（半列间距），超出说明该块不在任何星期列
    if abs(best.y_center - y) > 60:
        return None
    return best.weekday


def _find_course_name(
    candidates: list[tuple[float, float, str]],
    block_y: float,
    block_x: float,
    block_top: float,
) -> str | None:
    """从候选课程名块中，找「在描述块上方且水平重叠」的最近一个。

    candidates: list of (y_center, x_center, name)
    """
    best: tuple[float, str] | None = None
    for cy, cx, name in candidates:
        if cy >= block_y:  # 必须在描述块上方
            continue
        # 水平重叠：候选 x 在描述块 x 附近（容差 50pt，因单元格可能较宽）
        if abs(cx - block_x) > 80:
            continue
        distance = block_top - cy
        if distance < 0 or distance > 60:  # 课程名应紧贴描述块上方 0-60pt
            continue
        if best is None or distance < best[0]:
            best = (distance, name)
    return best[1] if best else None
```

- [ ] **Step 4: 运行测试确认通过**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_pdf_extractor.py -v
```
Expected: 全部 PASS。如果某个 `week_expr` 断言失败（如期望 `3-13周(单)` 实得 `3-13周`），检查 `_COURSE_DESC_RE` 的 `(单|双)` 捕获。

- [ ] **Step 5: 调试 — 如有课程名匹配错位**

如果 `course_name` 误把「区/场地:B132/教师:化磊」这种残串当课程名（旧版 bug），是因为 `_find_course_name` 把描述块自身的多行串当候选。验证：在测试里临时加：

```python
def test_course_names_reasonable():
    from app.timetable.pdf_extractor import PdfTimetableExtractor
    for e in PdfTimetableExtractor().extract(_bytes()).entries:
        if e.course_name:
            # 不应包含 "/" 或 "教师"
            assert "/" not in e.course_name, e.course_name
            assert "教师" not in e.course_name, e.course_name
```

如果失败，原因是某些 PDF 导出会把课程名和描述合进一个 block 的不同 line。修复：`name_candidates` 收集时，跳过那些 block 的**任何 line** 命中 `_COURSE_DESC_RE` 的 block（当前实现已在第一行过滤，需扩展为整 block 文本过滤）。把第一遍循环里的过滤条件改为：

```python
            block_text_for_check = "".join(
                s.get("text", "") for line in block["lines"] for s in line["spans"]
            )
            if _COURSE_DESC_RE.search(block_text_for_check):
                continue
```

重跑测试。

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/timetable/pdf_extractor.py apps/api/tests/test_pdf_extractor.py
git commit -m "feat(timetable): extract courses from PDF with weekday归属 and best-effort course name"
```

---

## Task 4：异常输入鲁棒性测试

**Files:**
- Modify: `apps/api/tests/test_pdf_extractor.py`

- [ ] **Step 1: 追加异常测试**

在 `apps/api/tests/test_pdf_extractor.py` 末尾追加：

```python
def test_empty_bytes_raises():
    import pytest
    from app.timetable.pdf_extractor import PdfTimetableExtractor

    with pytest.raises(Exception):
        PdfTimetableExtractor().extract(b"", "empty.pdf")


def test_non_pdf_bytes_raises():
    import pytest
    from app.timetable.pdf_extractor import PdfTimetableExtractor

    # 不是 PDF 的字节流
    with pytest.raises(Exception):
        PdfTimetableExtractor().extract(b"not a pdf " * 100, "fake.pdf")


def test_pdf_without_weekday_headers_returns_warning():
    """构造一个不含星期列头的 PDF（空白页），应返回空 entries + warning。"""
    import pymupdf
    from app.timetable.pdf_extractor import PdfTimetableExtractor

    doc = pymupdf.open()
    doc.new_page()
    empty_bytes = doc.tobytes()

    result = PdfTimetableExtractor().extract(empty_bytes, "blank.pdf")
    assert result.entries == []
    assert any("星期" in w for w in result.warnings)
```

- [ ] **Step 2: 运行测试**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_pdf_extractor.py -v
```
Expected: 全部 PASS。若 `test_non_pdf_bytes_raises` 因 pymupdf 不抛错而失败，把 `extract` 的 `_first_page_dict` 调用包一层显式检查：

在 `extract` 方法开头把 `_first_page_dict` 调用改为：

```python
        try:
            page_dict = self._first_page_dict(file_bytes)
        except Exception as exc:
            raise ValueError(f"PDF 文件无法读取: {exc}") from exc
```

重跑。

- [ ] **Step 3: Commit**

```bash
git add apps/api/tests/test_pdf_extractor.py
git commit -m "test(timetable): cover malformed/empty PDF inputs"
```

---

## Task 5：新增 `POST /timetables/parse-pdf` 端点

**Files:**
- Modify: `apps/api/app/schemas/timetable.py`
- Modify: `apps/api/app/api/v1/timetables.py`
- Create: `apps/api/tests/test_timetable_upload_pdf_api.py`

端点收 multipart PDF，解析后返回 `ParsedPdfOut`（**不入库**），供前端预览。前端拿到 entries 后再调现有 `/upload` → `/approve`。

- [ ] **Step 1: 写失败测试**

创建 `apps/api/tests/test_timetable_upload_pdf_api.py`：

```python
"""PDF 课表解析端点测试。"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from app.services import semester_service
from tests.conftest import csrf_headers, login

FIXTURE = Path(__file__).parent / "fixtures" / "sample_timetable.pdf"


def _seed_user(db):
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User

    u = User(username="202301070410", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id, student_no="202301070410", class_name="信管231", full_name="王文博", phone="13800000000"
    )
    db.add(p)
    db.commit()
    return u, p


def test_parse_pdf_returns_entries(client, seed_admin, db_session):
    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        data={"semester_id": str(sem.id)},
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["student_no"] == "202301070410"
    assert len(body["entries"]) == 10
    # 每条 entry 有前端入库所需字段
    e0 = body["entries"][0]
    assert {"weekday", "period_start", "period_end", "week_expr", "location_code"} <= set(e0.keys())


def test_parse_pdf_rejects_non_pdf(client, seed_admin, db_session):
    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        data={"semester_id": str(sem.id)},
        files={"file": ("not.pdf", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400
    assert "PDF" in resp.json()["detail"] or "pdf" in resp.json()["detail"].lower()


def test_parse_pdf_requires_login(client, db_session):
    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        data={"semester_id": str(sem.id)},
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )
    assert resp.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_timetable_upload_pdf_api.py -v
```
Expected: FAIL，404 或 422（端点不存在）。

- [ ] **Step 3: 添加 schema**

在 `apps/api/app/schemas/timetable.py` 末尾追加：

```python
class ParsedEntryOut(BaseModel):
    """PDF 解析出的单条课程（供前端预览，未入库）。"""

    weekday: int
    period_start: int
    period_end: int
    week_expr: str
    location_code: str | None = None
    course_name: str | None = None


class ParsedPdfOut(BaseModel):
    student_no: str | None = None
    full_name: str | None = None
    entries: list[ParsedEntryOut]
    warnings: list[str]
```

- [ ] **Step 4: 添加端点**

在 `apps/api/app/api/v1/timetables.py` 顶部 import 区追加：

```python
from fastapi import File, Form, UploadFile

from app.timetable.extractor import ManualEntryExtractor, get_pdf_extractor
from app.schemas.timetable import (
    # ... 已有 import 后追加：
    ParsedPdfOut,
)
```

把已有的 `from app.timetable.extractor import ManualEntryExtractor` 这行替换为：

```python
from app.timetable.extractor import ManualEntryExtractor, get_pdf_extractor
```

在 `apps/api/app/schemas/timetable.py` 顶部确认 `ParsedPdfOut` 已加，然后在 `apps/api/app/api/v1/timetables.py` 现有的 `from app.schemas.timetable import (...)` 块里加上 `ParsedPdfOut`。

然后在 `upload` 端点（`@router.post("/upload", ...)`）**之前**插入新端点：

```python
MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/parse-pdf", response_model=ParsedPdfOut)
def parse_pdf(
    semester_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedPdfOut:
    """解析 PDF 课表但不入库，返回 entries 供前端预览。

    前端拿到 entries 后调 ``POST /timetables/upload`` 创建 draft，再调
    ``POST /timetables/{id}/approve`` 生效。
    """
    # 校验文件大小
    file_bytes = file.file.read()
    if len(file_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="文件过大（>10MB）")

    # 校验是 PDF（按内容 magic bytes，不信任扩展名/mime）
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 校验学期存在
    from app.models.semester import Semester
    if db.get(Semester, semester_id) is None:
        raise HTTPException(status_code=404, detail="学期不存在")

    try:
        extractor = get_pdf_extractor()
        result = extractor.extract(file_bytes, file.filename or "timetable.pdf")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"PDF 解析失败：{exc}") from exc
    except Exception as exc:  # pymupdf 解析失败等
        raise HTTPException(status_code=400, detail=f"PDF 文件无法读取：{exc}") from exc

    if not result.entries:
        detail = "未识别到课程：" + "；".join(result.warnings) if result.warnings else "未识别到课程，请确认是学校教务系统导出的 PDF"
        raise HTTPException(status_code=400, detail=detail)

    return ParsedPdfOut(
        student_no=result.student_no,
        full_name=result.full_name,
        entries=[
            {"weekday": e.weekday, "period_start": e.period_start, "period_end": e.period_end,
             "week_expr": e.week_expr, "location_code": e.location_code, "course_name": e.course_name}
            for e in result.entries
        ],
        warnings=result.warnings,
    )
```

- [ ] **Step 5: 运行测试确认通过**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_timetable_upload_pdf_api.py -v
```
Expected: 3 个测试全 PASS。

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/schemas/timetable.py apps/api/app/api/v1/timetables.py apps/api/tests/test_timetable_upload_pdf_api.py
git commit -m "feat(timetable): POST /timetables/parse-pdf endpoint for PDF preview"
```

---

## Task 6：放开 `/approve` 给 upload 本人

**Files:**
- Modify: `apps/api/app/api/v1/timetables.py`
- Modify: `apps/api/tests/test_timetable_upload_pdf_api.py`

**背景**：用户决策「上传即生效」。现有 `/approve` 是 admin only，需要放开为「admin 或 upload 的 person 本人」。

- [ ] **Step 1: 写失败测试 — 普通用户能 approve 自己的 upload**

追加到 `apps/api/tests/test_timetable_upload_pdf_api.py`：

```python
def test_user_can_approve_own_upload(client, seed_admin, db_session):
    """用户上传后可直接 approve 自己的课表（上传即生效）。"""
    from sqlalchemy import select
    from app.models.availability import AvailabilityBlock

    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")

    # 1) 解析 PDF
    parsed = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        data={"semester_id": str(sem.id)},
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    ).json()

    # 2) 用解析结果创建 upload
    upload = client.post(
        "/api/v1/timetables/upload",
        headers=csrf_headers(token),
        json={
            "semester_id": str(sem.id),
            "file_name": "sample.pdf",
            "entries": parsed["entries"],
        },
    ).json()
    upload_id = upload["id"]

    # 3) 普通用户 approve 自己的（之前会 403，现在应 200）
    resp = client.post(f"/api/v1/timetables/{upload_id}/approve", headers=csrf_headers(token))
    assert resp.status_code == 200, resp.text

    # 4) 验证已生成不可值班区间（10 条课程规则，按各自周次展开）
    blocks = list(db_session.scalars(select(AvailabilityBlock)))
    assert len(blocks) > 0


def test_user_cannot_approve_others_upload(client, seed_admin, db_session):
    """普通用户不能 approve 别人的 upload。"""
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User

    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _, p_owner = _seed_user(db_session)

    # 另一个用户
    u2 = User(username="20250002", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True)
    db_session.add(u2)
    db_session.flush()
    db_session.add(PersonProfile(user_id=u2.id, student_no="20250002", class_name="一班", full_name="乙", phone="13800000001"))
    db_session.commit()

    # owner 上传
    token_owner = login(client, "202301070410", "pw123456")
    upload = client.post(
        "/api/v1/timetables/upload",
        headers=csrf_headers(token_owner),
        json={
            "semester_id": str(sem.id),
            "file_name": "t.pdf",
            "entries": [{"weekday": 1, "period_start": 1, "period_end": 2, "week_expr": "1-4周", "location_code": "B101"}],
        },
    ).json()

    # 乙尝试 approve 甲的
    token_other = login(client, "20250002", "pw123456")
    resp = client.post(f"/api/v1/timetables/{upload['id']}/approve", headers=csrf_headers(token_other))
    assert resp.status_code == 403
```

- [ ] **Step 2: 运行确认失败**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_timetable_upload_pdf_api.py::test_user_can_approve_own_upload -v
```
Expected: FAIL，403（现有 approve 是 `require_admin`）。

- [ ] **Step 3: 改造 approve 端点**

在 `apps/api/app/api/v1/timetables.py` 中找到现有的 `approve` 端点：

```python
@router.post("/{upload_id}/approve", response_model=MessageOut)
def approve(
    upload_id: uuid.UUID, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    timetable_service.approve(db, upload_id, actor.id)
    db.commit()
    return MessageOut(message="课表已生效")
```

替换为：

```python
@router.post("/{upload_id}/approve", response_model=MessageOut)
def approve(
    upload_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    """生效课表：admin 或 upload 本人可调。

    用户决策「上传即生效」，因此放开为本人可调；admin 仍可代审。
    """
    up = timetable_service._get_upload(db, upload_id)
    if current.role != UserRole.admin:
        prof = people_service.get_person_by_user(db, current.id)
        if up.person_id != prof.id:
            raise HTTPException(status_code=403, detail="无权操作他人课表")
    timetable_service.approve(db, upload_id, current.id)
    db.commit()
    return MessageOut(message="课表已生效")
```

- [ ] **Step 4: 同样改造 reject 端点（保持一致）**

找到：

```python
@router.post("/{upload_id}/reject", response_model=MessageOut)
def reject(
    upload_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    timetable_service.reject(db, upload_id)
    db.commit()
    return MessageOut(message="课表已驳回")
```

替换为：

```python
@router.post("/{upload_id}/reject", response_model=MessageOut)
def reject(
    upload_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    up = timetable_service._get_upload(db, upload_id)
    if current.role != UserRole.admin:
        prof = people_service.get_person_by_user(db, current.id)
        if up.person_id != prof.id:
            raise HTTPException(status_code=403, detail="无权操作他人课表")
    timetable_service.reject(db, upload_id)
    db.commit()
    return MessageOut(message="课表已驳回")
```

- [ ] **Step 5: 运行测试**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_timetable_upload_pdf_api.py -v
```
Expected: 全部 PASS。

- [ ] **Step 6: 跑现有 test_timetable_api.py 确保未破坏**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_timetable_api.py -v
```

**重要**：现有 `test_user_upload_and_admin_approve` 第 50 行断言「普通用户不能审核 → 403」。改造后**普通用户可以 approve 自己的**，所以这一行需要修改。

打开 `apps/api/tests/test_timetable_api.py`，找到：

```python
    # 普通用户不能审核
    assert client.post(f"/api/v1/timetables/{upload_id}/approve", headers=csrf_headers(token)).status_code == 403
```

这里 `token` 是上传者自己的 token，按新规则可以 approve，所以这行断言不再成立。但这个测试的意图是验证「admin 审核」流程仍能工作，需要改用一个**其他普通用户**来测 403。改为：

```python
    # 另一个普通用户不能审核别人的
    other = User(username="20250099", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True)
    db_session.add(other)
    db_session.flush()
    db_session.add(PersonProfile(user_id=other.id, student_no="20250099", class_name="一班", full_name="丙", phone="13800000002"))
    db_session.commit()
    other_token = login(client, "20250099", "pw123456")
    assert client.post(f"/api/v1/timetables/{upload_id}/approve", headers=csrf_headers(other_token)).status_code == 403
```

并确保测试文件顶部已 import（已有 `from app.core.security import hash_password`、`User`、`PersonProfile`、`UserRole`，检查补齐）。

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_timetable_api.py -v
```
Expected: 全部 PASS。

- [ ] **Step 7: 跑全套测试确保没破坏其他**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest -x -q
```
Expected: 全部 PASS。

- [ ] **Step 8: Commit**

```bash
git add apps/api/app/api/v1/timetables.py apps/api/tests/test_timetable_upload_pdf_api.py apps/api/tests/test_timetable_api.py
git commit -m "feat(timetable): allow upload owner to approve their own timetable (upload-and-apply)"
```

---

## Task 7：前端 API client — 添加 timetable 方法

**Files:**
- Modify: `apps/web/src/features/me/api.ts`

- [ ] **Step 1: 添加类型与方法**

在 `apps/web/src/features/me/api.ts` 中找到 `meApi` 对象定义（约第 78 行）。在 `meApi` 对象内（与其他方法同级，建议放 `availabilityRequests` 之后、闭合 `}` 之前）追加课表相关方法：

首先在文件顶部（与其他 interface 同区）追加类型：

```typescript
// --- 课表 ---
export interface ParsedEntry {
  weekday: number;
  period_start: number;
  period_end: number;
  week_expr: string;
  location_code: string | null;
  course_name: string | null;
}

export interface ParsedPdf {
  student_no: string | null;
  full_name: string | null;
  entries: ParsedEntry[];
  warnings: string[];
}

export interface MyTimetable {
  upload_id: string;
  uploaded_at: string;
  review_status: string;
  entries: ParsedEntry[];
}
```

然后在 `meApi` 对象内追加：

```typescript
  // 课表
  timetable: {
    parsePdf: async (semesterId: string, file: File) => {
      const form = new FormData();
      form.append("semester_id", semesterId);
      form.append("file", file);
      const res = await api.post<ParsedPdf>("/timetables/parse-pdf", form, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      return res.data;
    },
    upload: async (semesterId: string, fileName: string, entries: ParsedEntry[]) =>
      (await api.post<{ id: string }>("/timetables/upload", {
        semester_id: semesterId,
        file_name: fileName,
        entries,
      })).data,
    approve: async (uploadId: string) =>
      (await api.post<{ message: string }>(`/timetables/${uploadId}/approve`)).data,
    myActive: async () => (await api.get<MyTimetable | null>("/me/timetable")).data,
  },
```

- [ ] **Step 2: 运行 typecheck**

Run:
```bash
cd apps/web && pnpm typecheck
```
Expected: 无错误。

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/features/me/api.ts
git commit -m "feat(web): add meApi.timetable parsePdf/upload/approve/myActive methods"
```

---

## Task 8：后端 `GET /me/timetable` 端点（查本人当前生效课表）

**Files:**
- Modify: `apps/api/app/api/v1/me.py`
- Modify: `apps/api/tests/test_me.py`

前端 `myActive` 需要一个端点返回「本人本学期的当前生效课表」，供上传页判断「是否已有课表」以触发覆盖确认弹窗。

- [ ] **Step 1: 查看现有 me.py 结构**

Run:
```bash
cd apps/api && head -50 app/api/v1/me.py
```
了解路由前缀（应为 `/me`）和现有依赖。

- [ ] **Step 2: 写失败测试**

追加到 `apps/api/tests/test_me.py` 末尾（若无此文件参考 `test_people_api.py` 风格创建；文件已存在则追加）：

```python
def test_me_timetable_returns_active(client, seed_admin, db_session):
    """登录用户调用 /me/timetable 返回本人当前学期的生效课表。"""
    from datetime import date
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User
    from app.services import semester_service, timetable_service
    from app.timetable.extractor import RawCourseEntry

    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    u = User(username="202301070410", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True)
    db_session.add(u); db_session.flush()
    p = PersonProfile(user_id=u.id, student_no="202301070410", class_name="信管231", full_name="王文博", phone="13800000000")
    db_session.add(p); db_session.commit()

    entries = [RawCourseEntry(weekday=1, period_start=1, period_end=2, week_expr="1-4周", location_code="B101")]
    up = timetable_service.create_upload_from_entries(
        db_session, person_id=p.id, semester_id=sem.id, uploader_user_id=None,
        file_name="t.pdf", entries=entries,
    )
    timetable_service.approve(db_session, up.id, reviewer_id=None)
    db_session.commit()

    from tests.conftest import login, csrf_headers
    login(client, "202301070410", "pw123456")
    resp = client.get("/api/v1/me/timetable")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body is not None
    assert body["upload_id"] == str(up.id)
    assert body["review_status"] == "approved"
    assert len(body["entries"]) == 1
    assert body["entries"][0]["weekday"] == 1


def test_me_timetable_null_when_none(client, seed_admin, db_session):
    """无课表时返回 null。"""
    from datetime import date
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User
    from app.services import semester_service

    semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    u = User(username="202301070410", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True)
    db_session.add(u); db_session.flush()
    db_session.add(PersonProfile(user_id=u.id, student_no="202301070410", class_name="信管231", full_name="王文博", phone="13800000000"))
    db_session.commit()

    from tests.conftest import login
    login(client, "202301070410", "pw123456")
    resp = client.get("/api/v1/me/timetable")
    assert resp.status_code == 200
    assert resp.json() is None
```

- [ ] **Step 3: 运行确认失败**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_me.py::test_me_timetable_returns_active -v
```
Expected: FAIL，404 或 AttributeError。

- [ ] **Step 4: 实现端点**

在 `apps/api/app/api/v1/me.py` 末尾追加（注意 import 视现有文件顶部补齐 `select`、`selectinload`、`ReviewStatus`、`TimetableUpload`、`CourseRule` 等）：

```python
@router.get("/timetable", response_model=MyTimetableOut | None)
def get_my_timetable(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MyTimetableOut | None:
    """返回当前用户本学期已生效的课表（approved 状态），无则返回 null。"""
    from app.models.enums import ReviewStatus
    from app.models.timetable import TimetableUpload
    from app.services import people_service, semester_service
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    prof = people_service.get_person_by_user(db, current.id)
    if prof is None:
        return None
    sem = semester_service.get_current_semester(db)
    if sem is None:
        return None

    stmt = (
        select(TimetableUpload)
        .where(
            TimetableUpload.person_id == prof.id,
            TimetableUpload.semester_id == sem.id,
            TimetableUpload.review_status == ReviewStatus.approved,
        )
        .options(selectinload(TimetableUpload.course_rules))
        .order_by(TimetableUpload.confirmed_at.desc().nulls_last())
        .limit(1)
    )
    up = db.scalars(stmt).first()
    if up is None:
        return None
    return MyTimetableOut(
        upload_id=up.id,
        uploaded_at=up.created_at,
        review_status=up.review_status.value,
        entries=[
            {
                "weekday": r.weekday, "period_start": r.period_start, "period_end": r.period_end,
                "week_expr": _rule_week_expr(r), "location_code": r.location_code,
                "course_name": r.course_name,
            }
            for r in up.course_rules
        ],
    )


def _rule_week_expr(rule) -> str:
    """从 CourseRule 反推展示用周次表达。"""
    if rule.explicit_weeks:
        ws = rule.explicit_weeks
        if len(ws) <= 1:
            return f"{ws[0]}周"
        # 简单连续区间
        if ws == list(range(ws[0], ws[-1] + 1)):
            base = f"{ws[0]}-{ws[-1]}周"
            if rule.week_parity == "odd":
                base += "(单)"
            elif rule.week_parity == "even":
                base += "(双)"
            return base
        return ",".join(str(w) for w in ws) + "周"
    return ""
```

并在 `apps/api/app/schemas/timetable.py` 末尾追加响应模型：

```python
class MyTimetableEntryOut(BaseModel):
    weekday: int
    period_start: int
    period_end: int
    week_expr: str
    location_code: str | None = None
    course_name: str | None = None


class MyTimetableOut(BaseModel):
    upload_id: uuid.UUID
    uploaded_at: datetime
    review_status: str
    entries: list[MyTimetableEntryOut]
```

并在 `me.py` 顶部 import：

```python
from app.schemas.timetable import MyTimetableOut
```

- [ ] **Step 5: 运行测试**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_me.py -v
```
Expected: 全部 PASS。如果 `uploaded_at` 序列化报错（datetime 需 tz），把 schema 改用 `from datetime import datetime` 字段，Pydantic v2 会自动 ISO 化；若 SQLite 测试无 tz 触发 Pydantic warning，可在 `MyTimetableOut` 加 `model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}` 或忽略。

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/v1/me.py apps/api/app/schemas/timetable.py apps/api/tests/test_me.py
git commit -m "feat(me): GET /me/timetable returns user's current active timetable"
```

---

## Task 9：前端上传页 `UploadTimetablePage.tsx`

**Files:**
- Create: `apps/web/src/pages/user/UploadTimetablePage.tsx`
- Modify: `apps/web/src/router.tsx`
- Modify: `apps/web/src/layouts/UserLayout.tsx`
- Modify: `apps/web/src/pages/user/HomePage.tsx`

用户进入页面 → 拖拽/选择 PDF → 调 `parsePdf` 预览 → 显示解析出的时段表 → 点「确认生效」→ 检查是否已有课表（有则弹覆盖确认）→ `upload` + `approve` → 跳回首页。

- [ ] **Step 1: 创建上传页**

创建 `apps/web/src/pages/user/UploadTimetablePage.tsx`：

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { App, Button, Card, Empty, Modal, Table, Tag, Typography, Upload } from "antd";
import type { UploadFile } from "antd";
import dayjs from "dayjs";
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import { errorMessage } from "@/api/client";
import { meApi, type ParsedEntry } from "@/features/me/api";
import { useAuth } from "@/stores/auth";

const WEEKDAY_LABEL = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

export default function UploadTimetablePage() {
  const { message, modal } = App.useApp();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const user = useAuth((s) => s.user);

  const [parsed, setParsed] = useState<ParsedEntry[] | null>(null);
  const [fileName, setFileName] = useState<string>("");

  // 当前学期（取任意一个 admin 接口的 semester 列表第一项 is_current）
  // 简化：用 meApi.timetable.myActive 探测，后端用当前学期
  const activeQuery = useQuery({
    queryKey: ["me", "timetable", "active"],
    queryFn: meApi.timetable.myActive,
  });

  const parseMut = useMutation({
    mutationFn: async (file: File) => {
      // 学期 id 由后端按当前学期推断；前端不传 semester_id 的话需要传——
      // 这里用 active 的 semester？为简化，前端先取一个固定端点 /me/current-semester
      // 但当前没有。所以暂时让用户从首页跳转时带 semesterId，或后端 parse-pdf 不要求 semester_id
      // 实现方案：让 parse-pdf 的 semester_id 可选，缺省用当前学期（Task 10 改）
      return meApi.timetable.parsePdf("", file);
    },
    onSuccess: (data) => {
      if (data.entries.length === 0) {
        message.error("未在 PDF 中识别到课程");
        return;
      }
      setParsed(data.entries);
      message.success(`已解析出 ${data.entries.length} 条课程时段`);
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const confirmMut = useMutation({
    mutationFn: async () => {
      // 1. 创建 upload
      const up = await meApi.timetable.upload("", fileName, parsed!);
      // 2. approve 生效
      await meApi.timetable.approve(up.id);
    },
    onSuccess: () => {
      message.success("课表已生效");
      qc.invalidateQueries({ queryKey: ["me"] });
      navigate("/app/home");
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const handleConfirm = () => {
    if (activeQuery.data) {
      modal.confirm({
        title: "确认覆盖现有课表",
        content: `你已于 ${dayjs(activeQuery.data.uploaded_at).format("YYYY-MM-DD")} 上传过课表，新上传将覆盖旧课表。是否继续？`,
        okText: "覆盖并生效",
        cancelText: "取消",
        okButtonProps: { danger: true },
        onOk: () => confirmMut.mutate(),
      });
    } else {
      confirmMut.mutate();
    }
  };

  return (
    <div>
      <Typography.Title level={4} style={{ marginTop: 0 }}>
        上传我的课表
      </Typography.Title>
      <Card size="small" style={{ marginBottom: 12 }}>
        <Upload.Dragger
          accept=".pdf"
          maxCount={1}
          beforeUpload={(file) => {
            setFileName(file.name);
            parseMut.mutate(file);
            return false; // 阻止自动上传
          }}
          showUploadList={false}
          disabled={parseMut.isPending}
        >
          <p style={{ fontSize: 40, color: "#1677ff", margin: "8px 0" }}>📄</p>
          <p>点击或拖拽学校教务系统导出的 PDF 课表至此</p>
          <p style={{ color: "#888", fontSize: 12 }}>仅支持 PDF，10MB 以内</p>
        </Upload.Dragger>
        {parseMut.isPending && <Tag color="blue" style={{ marginTop: 8 }}>解析中…</Tag>}
      </Card>

      {parsed && (
        <Card
          size="small"
          title={`解析结果（${parsed.length} 条）`}
          extra={
            <Button type="primary" loading={confirmMut.isPending} onClick={handleConfirm}>
              确认生效
            </Button>
          }
        >
          <Table
            size="small"
            pagination={false}
            scroll={{ y: 300 }}
            dataSource={parsed.map((e, i) => ({ ...e, key: i }))}
            columns={[
              { title: "星期", dataIndex: "weekday", render: (v: number) => WEEKDAY_LABEL[v], width: 70 },
              { title: "节次", render: (_, r) => `第 ${r.period_start}-${r.period_end} 节`, width: 100 },
              { title: "周次", dataIndex: "week_expr", width: 120 },
              { title: "场地", dataIndex: "location_code", width: 100 },
            ]}
          />
          <div style={{ marginTop: 8, color: "#888", fontSize: 12 }}>
            * 仅记录时段占用用于排班，不存储课程名等业务信息。
          </div>
        </Card>
      )}
    </div>
  );
}
```

> **注意**：上面 `parsePdf("", file)` 和 `upload("", ...)` 传了空 `semesterId`。这要求后端 `parse-pdf` 的 `semester_id` 改为可选，缺省取当前学期。Task 10 会改后端。如果不想改后端，先在 Task 10 让前端从 `/semesters` 取 `is_current` 的那个 id（但 `/semesters` 是 admin only）。**推荐 Task 10 改后端为可选**。

- [ ] **Step 2: 注册路由**

修改 `apps/web/src/router.tsx`，在 `import MySchedulePage` 后加：

```tsx
import UploadTimetablePage from "@/pages/user/UploadTimetablePage";
```

在 `/app` children 里加：

```tsx
          { path: "timetable", element: <UploadTimetablePage /> },
```

（放在 `{ path: "availability", ... }` 后面）

- [ ] **Step 3: 加底栏入口**

修改 `apps/web/src/layouts/UserLayout.tsx`，在 `tabs` 数组里加（建议放「排班」后）：

```tsx
  { key: "/app/timetable", icon: <FileTextOutlined />, label: "课表" },
```

并在顶部 import 加：

```tsx
import { FileTextOutlined } from "@ant-design/icons";
```

- [ ] **Step 4: 首页加快捷入口**

修改 `apps/web/src/pages/user/HomePage.tsx`，在 `<Typography.Title>` 之后、第一次值班 Card 之前加：

```tsx
      <Card
        size="small"
        hoverable
        onClick={() => navigate("/app/timetable")}
        style={{ marginBottom: 12, background: "#e6f4ff", border: "1px solid #91caff" }}
      >
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontWeight: 600 }}>📄 上传我的课表 PDF</span>
          <span style={{ color: "#1677ff" }}>去上传 →</span>
        </div>
      </Card>
```

- [ ] **Step 5: typecheck**

Run:
```bash
cd apps/web && pnpm typecheck
```
Expected: 无错误（可能因 `parsePdf("", file)` 的空字符串 semester_id 类型合法，因为类型是 `string`）。

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/pages/user/UploadTimetablePage.tsx apps/web/src/router.tsx apps/web/src/layouts/UserLayout.tsx apps/web/src/pages/user/HomePage.tsx
git commit -m "feat(web): user-facing PDF timetable upload page with preview & confirm"
```

---

## Task 10：后端 `parse-pdf` 的 `semester_id` 改为可选

**Files:**
- Modify: `apps/api/app/api/v1/timetables.py`
- Modify: `apps/api/tests/test_timetable_upload_pdf_api.py`

- [ ] **Step 1: 改端点签名为可选**

在 `apps/api/app/api/v1/timetables.py` 找到 `parse_pdf` 端点，把：

```python
def parse_pdf(
    semester_id: uuid.UUID = Form(...),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedPdfOut:
```

改为：

```python
def parse_pdf(
    semester_id: uuid.UUID | None = Form(None),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedPdfOut:
```

并把函数体里的学期校验段：

```python
    # 校验学期存在
    from app.models.semester import Semester
    if db.get(Semester, semester_id) is None:
        raise HTTPException(status_code=404, detail="学期不存在")
```

替换为：

```python
    # 校验学期：未传则取当前学期
    from app.models.semester import Semester
    from app.services import semester_service
    if semester_id is not None:
        if db.get(Semester, semester_id) is None:
            raise HTTPException(status_code=404, detail="学期不存在")
    else:
        sem = semester_service.get_current_semester(db)
        if sem is None:
            raise HTTPException(status_code=400, detail="当前无激活学期，请联系管理员")
```

（解析本身不依赖 semester_id，所以函数体其余部分不变。）

- [ ] **Step 2: 追加测试 — 不传 semester_id 也能解析**

追加到 `apps/api/tests/test_timetable_upload_pdf_api.py`：

```python
def test_parse_pdf_without_semester_uses_current(client, seed_admin, db_session):
    from datetime import date
    from app.services import semester_service

    semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23), is_current=True)
    db_session.commit()

    # seed user（复用 _seed_user）
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User
    u = User(username="202301070410", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True)
    db_session.add(u); db_session.flush()
    db_session.add(PersonProfile(user_id=u.id, student_no="202301070410", class_name="信管231", full_name="王文博", phone="13800000000"))
    db_session.commit()

    token = login(client, "202301070410", "pw123456")
    # 不传 semester_id
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["entries"]) == 10
```

- [ ] **Step 3: 跑测试**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest tests/test_timetable_upload_pdf_api.py -v
```
Expected: 全部 PASS。

- [ ] **Step 4: Commit**

```bash
git add apps/api/app/api/v1/timetables.py apps/api/tests/test_timetable_upload_pdf_api.py
git commit -m "feat(timetable): make semester_id optional in parse-pdf, default to current"
```

---

## Task 11：admin 代传入口

**Files:**
- Modify: `apps/web/src/pages/admin/TimetablesPage.tsx`
- Modify: `apps/web/src/features/admin/api.ts`

在 admin「全员课表」页加「为某人代传」按钮，逻辑同用户上传页，但 `upload` 时传 `person_id`。

- [ ] **Step 1: 扩展 adminApi.timetable**

修改 `apps/web/src/features/admin/api.ts`，找到 `timetables` 块：

```typescript
  // 课表
  timetables: {
    active: async () => (await api.get<ActiveTimetableOut[]>("/timetables/active")).data,
  },
```

替换为：

```typescript
  // 课表
  timetables: {
    active: async () => (await api.get<ActiveTimetableOut[]>("/timetables/active")).data,
    parsePdf: async (file: File, semesterId?: string) => {
      const form = new FormData();
      form.append("file", file);
      if (semesterId) form.append("semester_id", semesterId);
      const res = await api.post<{
        student_no: string | null;
        entries: {
          weekday: number; period_start: number; period_end: number;
          week_expr: string; location_code: string | null; course_name: string | null;
        }[];
        warnings: string[];
      }>("/timetables/parse-pdf", form, { headers: { "Content-Type": "multipart/form-data" } });
      return res.data;
    },
    uploadFor: async (personId: string, fileName: string, entries: {
      weekday: number; period_start: number; period_end: number;
      week_expr: string; location_code: string | null;
    }[]) => (await api.post<{ id: string }>("/timetables/upload", {
      person_id: personId, file_name: fileName, entries,
    })).data,
    approve: async (uploadId: string) =>
      (await api.post<{ message: string }>(`/timetables/${uploadId}/approve`)).data,
  },
```

- [ ] **Step 2: 在 TimetablesPage 加代传 Modal**

修改 `apps/web/src/pages/admin/TimetablesPage.tsx`。在文件顶部 import 区加：

```tsx
import { App, Button, Modal, Table, Upload } from "antd";
import { UploadOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "@/api/client";
```

（合并到现有 import；`App, Modal, Table, Upload` 是新增，`Button` 已有则不重复。）

在组件函数内（`const [viewMode, setViewMode] = ...` 附近）加：

```tsx
  const { message } = App.useApp();
  const qc = useQueryClient();
  const [proxyFor, setProxyFor] = useState<{ personId: string; personName: string } | null>(null);
  const [proxyParsed, setProxyParsed] = useState<any[] | null>(null);
  const [proxyFileName, setProxyFileName] = useState("");

  const parseMut = useMutation({
    mutationFn: ({ file }: { file: File }) => adminApi.timetables.parsePdf(file),
    onSuccess: (data) => {
      if (!data.entries.length) { message.error("未识别到课程"); return; }
      setProxyParsed(data.entries);
      message.success(`解析出 ${data.entries.length} 条`);
    },
    onError: (e) => message.error(errorMessage(e)),
  });

  const confirmMut = useMutation({
    mutationFn: async () => {
      const up = await adminApi.timetables.uploadFor(proxyFor!.personId, proxyFileName, proxyParsed!);
      await adminApi.timetables.approve(up.id);
    },
    onSuccess: () => {
      message.success("代传课表已生效");
      setProxyFor(null); setProxyParsed(null); setProxyFileName("");
      qc.invalidateQueries({ queryKey: ["admin", "timetables"] });
    },
    onError: (e) => message.error(errorMessage(e)),
  });
```

在筛选区 `<Space>` 末尾（人员筛选 Select 后）加一个按钮：

```tsx
          <Button icon={<UploadOutlined />} onClick={() => setProxyFor({ personId: "", personName: "" })}>
            为某人代传课表
          </Button>
```

在组件 return 的 `<Card>...</Card>` 闭合后追加代传 Modal：

```tsx
      <Modal
        open={!!proxyFor}
        title="为某人代传课表"
        onCancel={() => { setProxyFor(null); setProxyParsed(null); setProxyFileName(""); }}
        onOk={proxyParsed ? () => confirmMut.mutate() : undefined}
        okText={proxyParsed ? "确认生效" : undefined}
        confirmLoading={confirmMut.isPending}
        okButtonProps={proxyParsed ? {} : { disabled: true }}
        footer={proxyParsed ? undefined : null}
      >
        {!proxyParsed ? (
          <>
            <div style={{ marginBottom: 12 }}>
              <label style={{ display: "block", marginBottom: 6 }}>选择人员:</label>
              <select
                style={{ width: "100%", padding: 8 }}
                value={proxyFor?.personId ?? ""}
                onChange={(e) => {
                  const p = allPeople.find((x) => x.person_id === e.target.value);
                  setProxyFor({ personId: e.target.value, personName: p?.person_name ?? "" });
                }}
              >
                <option value="">请选择…</option>
                {allPeople.map((p) => (
                  <option key={p.person_id} value={p.person_id}>{p.person_name}</option>
                ))}
              </select>
            </div>
            <Upload
              accept=".pdf"
              maxCount={1}
              showUploadList={false}
              beforeUpload={(file) => {
                if (!proxyFor?.personId) { message.error("请先选择人员"); return false; }
                setProxyFileName(file.name);
                parseMut.mutate({ file });
                return false;
              }}
            >
              <Button icon={<UploadOutlined />} loading={parseMut.isPending} disabled={!proxyFor?.personId}>
                选择 PDF 文件
              </Button>
            </Upload>
          </>
        ) : (
          <Table
            size="small"
            pagination={false}
            scroll={{ y: 300 }}
            dataSource={proxyParsed.map((e, i) => ({ ...e, key: i }))}
            columns={[
              { title: "星期", dataIndex: "weekday", render: (v: number) => ["","周一","周二","周三","周四","周五","周六","周日"][v], width: 70 },
              { title: "节次", render: (_, r) => `第 ${r.period_start}-${r.period_end} 节`, width: 100 },
              { title: "周次", dataIndex: "week_expr", width: 120 },
            ]}
          />
        )}
      </Modal>
```

并把最外层 `<Card>` 包进 `<App>`（如果整个 admin layout 已在 `<App>` 内，则跳过；admin layout 通常已有 antd App context）。

- [ ] **Step 3: typecheck + test**

Run:
```bash
cd apps/web && pnpm typecheck
```
Expected: 无错误。

如果有现成的前端测试，跑：
```bash
cd apps/web && pnpm test
```

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/pages/admin/TimetablesPage.tsx apps/web/src/features/admin/api.ts
git commit -m "feat(web): admin proxy-upload timetable PDF for any person"
```

---

## Task 12：文档更新 + 全量回归

**Files:**
- Modify: `README.md`
- Modify: `docs/deployment.md`（如存在）

- [ ] **Step 1: 更新 README 阶段三状态**

在 `README.md` 找到阶段三那行（约第 20 行）：

```
- [x] 阶段三 课表识别：周次表达解析、节次时间解析、课程规则→不可值班区间（含缓冲）、审核后生效、旧课表逻辑失效；PDF/OCR 抽取层已抽象（待样例接入）
```

改为：

```
- [x] 阶段三 课表识别：周次表达解析、节次时间解析、课程规则→不可值班区间（含缓冲）、PDF 课表上传即解析即生效、旧课表逻辑失效；本校教务系统 PDF 解析器已接入（PyMuPDF）
```

- [ ] **Step 2: 全量后端测试**

Run:
```bash
cd apps/api && .venv/bin/python -m pytest -v
```
Expected: 全部 PASS。若有失败，回到对应 Task 修复。

- [ ] **Step 3: 全量前端 typecheck + build**

Run:
```bash
cd apps/web && pnpm typecheck && pnpm build
```
Expected: 无错误，`dist/` 产物生成。

- [ ] **Step 4: 手动冒烟（可选，需起服务）**

```bash
cd apps/api && .venv/bin/uvicorn app.main:app --reload &
cd apps/web && pnpm dev
```
浏览器打开 `http://localhost:5173`，登录普通用户，点首页「上传我的课表」，拖入样例 PDF，确认解析出 10 条，点「确认生效」，回到 admin「全员课表」页验证该用户出现在有课表。

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: update README phase-3 status to reflect PDF parser integration"
```

---

## 验收清单

实现完成后逐项核验：

- [ ] `apps/api/app/timetable/pdf_extractor.py` 能从样例 PDF 抽出 10 条课程
- [ ] `POST /api/v1/timetables/parse-pdf` 返回解析结果（不入库）
- [ ] `POST /api/v1/timetables/{id}/approve` 普通 upload 本人可调（之前 admin only）
- [ ] `GET /api/v1/me/timetable` 返回本人当前生效课表
- [ ] 用户上传页：拖拽 PDF → 预览 → 确认生效（含覆盖确认弹窗）
- [ ] admin 全员课表页有「为某人代传」入口
- [ ] `pytest -v` 全绿
- [ ] `pnpm typecheck && pnpm build` 全绿
- [ ] 同人重复上传 → 旧课表自动 superseded（依赖现有 `_supersede_previous`）

## 已知限制（不在本期范围）

- ❌ 不支持 OCR（PDF 必须有文本层）
- ❌ 不支持非本校教务系统 PDF 格式
- ❌ 不支持 Excel/ICS 课表导入
- ❌ 课程名/教师等附加信息仅 best-effort 抽取，前端不展示
