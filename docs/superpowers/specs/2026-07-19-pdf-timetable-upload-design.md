# PDF 课表上传与解析 — 设计文档

**日期**：2026-07-19
**主题**：用户/admin 上传学校教务系统 PDF 课表，系统解析后自动落到「有课表/无课表」（即可用性矩阵）

## 1. 背景与目标

### 用户诉求
每个人上传自己学校的课表 PDF，系统解析出该人在哪些时段有课，自动反映到排班的「有课表/无课表」上。不需要保留课程名等业务信息（解析会自然带出，但不强制使用、不依赖）。

### 现状盘点
系统其实已经搭好 80%：

| 模块 | 状态 |
|---|---|
| `app/timetable/week_parser.py` | ✅ 已实现：`3-13周(单)`、`1-4,6-8周` 等周次表达 |
| `app/timetable/availability.py` | ✅ 已实现：节次 → 具体时间区间、按周生成日期区间 |
| `app/services/timetable_service.py` | ✅ 已实现：抽取结果 → 规则 → 审核生效 → 生成 `AvailabilityBlock` |
| `app/api/v1/timetables.py` `POST /upload` | ⚠️ 只收已解析好的 `entries`，**不收 PDF 文件** |
| `app/timetable/extractor.py` `get_pdf_extractor()` | ⚠️ lazy-import 的 `pdf_extractor.py` **不存在** |
| `app/web/src/pages/admin/TimetablesPage.tsx` | ✅「有课表/无课表」视图已存在 |
| 用户端上传 UI | ❌ 不存在 |

### PDF 样例实测结论
对样例 PDF `王文博(2025-2026-2)课表.pdf` 用 PyMuPDF 提取：

- 共 2 页，**文本层完整，无需 OCR**
- 页面 `rotation=90`，逻辑坐标系下：星期列头（星期一..星期日）在**不同的 y 坐标**（每列约间隔 104pt），节次行头在不同 x 坐标
- 每个课程单元格文本结构稳定：
  ```
  <课程名>★
  (3-4节)2-13周/校区:黄岛校区/场地:B608/教师:武华华/教学班:.../学分:2.5/重修标记:
  ```
- 元数据用 `/` 分隔，节次、周次、场地均可正则抽取

### 关于「极简课表」等开源项目
极简课表是 Android App（Kotlin），针对多校教务系统的格式适配库，并非可复用的 Python 解析组件。各家学校 PDF 格式差异极大，强行通用化反而降低可靠性。本设计**聚焦本校教务系统格式**，借鉴极简课表「上传即解析 + 用户预览确认」的交互范式，但不集成其代码。

## 2. 关键决策（已与用户确认）

| 决策点 | 选择 | 说明 |
|---|---|---|
| 审核流程 | **上传即生效** | 解析成功直接进入有课/无课表，不走 admin 审核。打破现有「课表未经确认不得影响排班」红线，由用户决策承担 |
| 上传入口 | **用户自助 + admin 代传** | 新建用户上传 UI；admin 也能代传 |
| 格式适配范围 | **专注本校格式** | 旋转 90° + `(节次)周次/校区:.../场地:.../...` 结构。格式变了再扩展 |
| 课程名等附加信息 | **只存有无课** | 解析会带出课程名/教师/场地，存入 CourseRule 字段（模型已有），但前端预览只显示「时段占用」，不展示业务信息 |
| 节次→时间映射 | **复用现有节次表** | 沿用 `availability.resolve_period_time` + 学期 `CoursePeriodRule` |
| 重复上传 | **上传前确认覆盖** | 弹窗确认「这将覆盖你 X 月上传的课表」后才提交 |

## 3. 架构设计

### 3.1 数据流

```
[用户/admin 拖拽 PDF]
        ↓
[POST /timetables/upload-pdf  multipart]
        ↓
[PdfTimetableExtractor.extract(bytes)]   ← 新建
        │  1. pymupdf 提取 dict（带坐标）
        │  2. 定位 7 个星期列头 → 建立 y→weekday 映射
        │  3. 遍历文本块，归属 weekday
        │  4. 正则抽取 (节次)(周次)(场地)(校区)
        │  5. 课程名 = 文本块首行非符号串
        ↓
[list[RawCourseEntry]]                    ← 已有结构
        ↓
[timetable_service.parse_and_apply_pdf()]  ← 新增一站式函数
        │  内部：create_upload_from_entries + 直接 approve
        │  （绕过 review_status=pending → approved）
        ↓
[生成 AvailabilityBlock（不可值班区间）]   ← 已有
        ↓
[/timetables/active] 自动反映
        ↓
[前端 TimetablesPage「有课/无课表」视图]
```

### 3.2 模块清单

#### 新增：`apps/api/app/timetable/pdf_extractor.py`

职责：把 PDF bytes 转成 `list[RawCourseEntry]`。

**公开接口**：
```python
class PdfTimetableExtractor:
    def extract(self, file_bytes: bytes, file_name: str) -> ExtractResult: ...
```

**算法**：
1. `pymupdf.open(stream=file_bytes, filetype="pdf")`
2. 取第 1 页，无视 `page.rotation`，用 `get_text("dict")` 取原始坐标
3. 第一遍扫描：找所有文本块中 `text in {"星期一".."星期日"}` 的 span，记录其 `(x, y)` → 建立 weekday 映射（按 y 排序，因页面旋转 90°，星期在 y 轴分布）
4. 第二遍遍历文本块（过滤掉列头、节次行号、表头、学号行）：
   - 用正则 `\((\d+)-(\d+)节\)\s*([\d\-]+周(?:\(单\)|\(双\))?)` 识别「课程说明行」
   - 课程名 = 该块中早于此行的最后一行非符号文本（如 `供应链管理基础B★` 去 ★ 后的串）
   - weekday = 该块中心 y 落在哪个星期列头区间
   - `/场地:([^/]+?)/`、`/校区:([^/]+?)/` 抽取附属字段
5. 失败处理：
   - 找不到 7 个星期列头 → `warnings.append("无法识别表头，可能非本校格式")`，返回空 entries
   - 某课程块缺周次 → 跳过并 warning
   - 抽出 0 条且无 warning → 加 warning「未解析到任何课程」
6. `confidence` 按是否所有字段齐全给 1.0 / 0.8 / 0.5

**鲁棒性要点**：
- 不依赖 `page.rotation`，直接用原始坐标，避免不同导出工具旋转方向差异
- 用 weekday 列头实际坐标做区间归属，不硬编码像素值
- 同一单元格多课程（如周三 3-4 节同时有 4 门课分周次上）→ 全部抽出，各自一条 RawCourseEntry

#### 修改：`apps/api/app/services/timetable_service.py`

新增一站式函数：
```python
def parse_and_apply_pdf(
    db: Session,
    *,
    person_id: uuid.UUID,
    semester_id: uuid.UUID,
    uploader_user_id: uuid.UUID | None,
    file_name: str,
    file_bytes: bytes,
) -> tuple[TimetableUpload, ExtractResult]:
    """PDF 解析 + 直接生效（不走 admin 审核）。

    流程：
    1. 计算 file_hash（sha256），若同 person+semester+hash 已存在则直接返回
    2. 调 PdfTimetableExtractor.extract
    3. 若 entries 为空 → 抛 HTTPException 400（解析失败）
    4. create_upload_from_entries（已有）
    5. 直接调 approve(db, upload.id, uploader_user_id)（已有，含 _supersede_previous）
    6. 返回 upload + ExtractResult（供前端展示解析明细）
    """
```

> 注：现有 `approve()` 已包含「旧课表标记 superseded + 旧 AvailabilityBlock 标记 expired」逻辑，天然支持「上传前确认覆盖」语义——前端确认后才调用此端点即可。

#### 修改：`apps/api/app/api/v1/timetables.py`

新增端点：
```python
@router.post("/upload-pdf", response_model=TimetablePreviewOut)
def upload_pdf(
    semester_id: uuid.UUID = Form(...),
    person_id: uuid.UUID | None = Form(None),  # admin 代传时指定
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimetablePreviewOut: ...
```

权限：
- admin 可指定任意 `person_id`
- 普通用户忽略 `person_id`，强制绑定本人 `person_profile`
- 文件大小限制 10MB、扩展名 `.pdf`（mime sniff 而非信任扩展名）
- 内容校验：`pymupdf.open()` 失败 → 400

#### 新增：`apps/api/app/schemas/timetable.py`

```python
class TimetableParseWarning(BaseModel):
    message: str

class TimetableUploadPdfOut(BaseModel):
    upload: TimetablePreviewOut
    warnings: list[str]
    student_no: str | None
    full_name: str | None
```
（或直接复用 `TimetablePreviewOut` + 在 response 加可选字段，二选一，实现时定）

#### 新增：前端 `apps/web/src/pages/user/UploadTimetablePage.tsx`（或在 HomePage 加入口）

交互：
1. 拖拽/选择 PDF
2. 调 `POST /timetables/upload-pdf` 上传
3. 解析成功 → 展示抽出的课程时段列表（**只显示星期/节次/周次**，不显示课程名/教师）
4. 若该人本学期已有生效课表 → 上传前弹窗「这将覆盖你 YYYY-MM-DD 上传的课表，确认？」
5. 用户点「确认生效」→ 已在 step 2 完成（或拆成两步：先 `/parse-pdf` 预览，再 `/apply` 生效，更稳）

> **设计选择**：拆成「解析预览」+「确认生效」两步更符合「上传前确认」语义，且复用现有 `/upload`（创建 draft）+ `/approve` 路径。最终实现采用此方案：
> - `POST /timetables/parse-pdf` → 返回解析出的 entries（不入库）
> - `POST /timetables/upload` → 用 entries 创建 draft（已有）
> - `POST /timetables/{id}/approve` → 直接生效（已有，admin only 需放开为「本人可调」）

#### 修改：`apps/web/src/pages/admin/TimetablesPage.tsx` 或 `PeoplePage.tsx`

admin 代传入口：选人 → 上传 PDF → 同样的预览确认流程。

### 3.3 端点最终清单

| 方法 | 路径 | 说明 | 权限 |
|---|---|---|---|
| POST | `/timetables/parse-pdf` | **新增**：multipart PDF → 返回解析出的 entries（不入库） | 登录用户 |
| POST | `/timetables/upload` | 已有：entries → 创建 draft upload | 登录用户 |
| POST | `/timetables/{id}/approve` | 已有：生效。**修改**：放开为「admin 或 upload 本人」可调 | admin 或本人 |
| 其他 | `/timetables/*` | 已有，不变 | — |

> 拆三步而非一步的好处：复用现有路径、预览阶段用户可手工修正解析错的 entries、`/upload-pdf` 直冲生效会让「上传前确认」形同虚设。

### 3.4 错误处理

| 场景 | 处理 |
|---|---|
| 非 PDF 文件 | 400 `仅支持 PDF` |
| PDF 损坏 | 400 `PDF 文件无法读取` |
| 不是本校格式（找不到 7 个星期列头） | 400 `无法识别课表格式，请确认是学校教务系统导出的 PDF` |
| 解析出 0 条课程 | 400 `未在 PDF 中识别到课程，请检查或改用手工录入` |
| 文件 > 10MB | 413 |
| 学期不存在 / 无当前学期 | 400 |
| 该人本学期已有生效课表 | 前端在上传前拦截弹窗（端点侧靠 `_supersede_previous` 保证覆盖语义正确） |
| pymupdf 依赖未安装 | 500 `服务端未配置 PDF 解析依赖`（运维问题，非用户问题） |

### 3.5 测试

`apps/api/tests/test_pdf_extractor.py`：
- 用真实样例 PDF（放 `tests/fixtures/王文博_课表.pdf`）作为 fixture
- 断言解析出预期条数（约 7-8 条 RawCourseEntry）
- 断言关键字段：周三 3-4 节有课、周四 5-6 节 `2-17周`、周四 7-8 节 `2-5周` 等
- 断言 weekday 归属正确（旋转 90° 场景）
- 异常 PDF / 空 PDF → 返回 warnings 不抛

`apps/api/tests/test_timetable_upload_pdf.py`：
- 端到端：上传样例 PDF → `/parse-pdf` → `/upload` → `/approve` → 查 `/active` 反映
- 同人重复上传 → 旧课表 superseded、旧 block expired
- 权限：普通用户传他人 person_id → 403
- 依赖未安装场景 mock

## 4. 依赖与部署

- 后端新增运行时依赖：`pymupdf>=1.24`（从 `[timetable]` optional 提升为必装）
- pyproject.toml `dependencies` 加入 `pymupdf>=1.24`，移除 `[project.optional-dependencies].timetable`
- Dockerfile 确认 mupdf 系统库（pymupdf 自带 wheel，通常无需系统库）
- 前端无新依赖（用现有 antd `Upload` + `Modal`）

## 5. 不做的事（YAGNI）

- ❌ 不做 OCR（PDF 文本层干净，OCR 增重 200MB+ 依赖）
- ❌ 不做通用多校格式适配（专注本校，格式变了再说）
- ❌ 不做 ICS/Excel 课表导入（用户没提）
- ❌ 不强制存储课程名/教师/学分等业务字段（只存有无课）
- ❌ 不做 admin 批量审核页（用户决策：上传即生效）

## 6. 风险与回退

| 风险 | 缓解 |
|---|---|
| 学校换教务系统导致 PDF 格式变 | 解析器集中在 `pdf_extractor.py` 单文件，替换即可；保留 `ManualEntryExtractor` 手工录入兜底 |
| 旋转方向 / 坐标系差异 | 不依赖 `page.rotation`，用星期列头实际坐标做区间归属 |
| 节次表未配置导致时间映射失败 | 沿用现有 `needs_review` 标记，前端提示「请联系 admin 配置节次表」 |
| 用户传错别人的 PDF | 前端预览显示解析出的学号/姓名，用户可核对（虽然不强制存，但解析时会显示用于校对） |

## 7. 实施顺序

1. 后端 PDF 解析器 `pdf_extractor.py` + 单元测试（用样例 PDF）
2. 后端 `/timetables/parse-pdf` 端点 + `/approve` 权限放开
3. 后端集成测试（端到端）
4. 前端用户上传页面 + 预览确认交互
5. 前端 admin 代传入口
6. 文档更新（README 阶段三、deployment.md 依赖说明）
