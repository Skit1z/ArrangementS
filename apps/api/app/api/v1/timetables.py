"""课表上传、预览、修正与审核路由（方案 4.3 / 4.6 / 13.3）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.timetable import (
    ActiveTimetableOut,
    CourseRuleOut,
    CourseRulePatch,
    ParsedEntryOut,
    ParsedPdfOut,
    TimetablePreviewOut,
    TimetableUploadIn,
)
from app.services import people_service, timetable_service
from app.timetable.extractor import ManualEntryExtractor, get_pdf_extractor

router = APIRouter(prefix="/timetables", tags=["timetables"])

MAX_PDF_BYTES = 10 * 1024 * 1024  # 10 MB


@router.post("/parse-pdf", response_model=ParsedPdfOut)
def parse_pdf(
    semester_id: uuid.UUID | None = Form(None),
    file: UploadFile = File(...),
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ParsedPdfOut:
    """解析 PDF 课表但不入库，返回 entries 供前端预览。

    前端拿到 entries 后调 ``POST /timetables/upload`` 创建 draft，再调
    ``POST /timetables/{id}/approve`` 生效。``semester_id`` 未传则用当前学期。
    """
    file_bytes = file.file.read()
    if len(file_bytes) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail="文件过大（>10MB）")

    # 按 magic bytes 校验是 PDF（不信任扩展名/mime）
    if not file_bytes.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail="仅支持 PDF 文件")

    # 学期：未传则取当前学期
    from app.models.semester import Semester
    from app.services import semester_service

    if semester_id is not None:
        if db.get(Semester, semester_id) is None:
            raise HTTPException(status_code=404, detail="学期不存在")
    else:
        sem = semester_service.get_current_semester(db)
        if sem is None:
            raise HTTPException(status_code=400, detail="当前无激活学期，请联系管理员")

    try:
        extractor = get_pdf_extractor()
        result = extractor.extract(file_bytes, file.filename or "timetable.pdf")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"PDF 解析失败：{exc}") from exc
    except Exception as exc:  # pymupdf 解析失败等
        raise HTTPException(status_code=400, detail=f"PDF 文件无法读取：{exc}") from exc

    if not result.entries:
        detail = (
            "未识别到课程：" + "；".join(result.warnings)
            if result.warnings
            else "未识别到课程，请确认是学校教务系统导出的 PDF"
        )
        raise HTTPException(status_code=400, detail=detail)

    return ParsedPdfOut(
        student_no=result.student_no,
        full_name=result.full_name,
        entries=[
            ParsedEntryOut(
                weekday=e.weekday,
                period_start=e.period_start,
                period_end=e.period_end,
                week_expr=e.week_expr,
                location_code=e.location_code,
                course_name=e.course_name,
            )
            for e in result.entries
        ],
        warnings=result.warnings,
    )


@router.post("/upload", response_model=TimetablePreviewOut)
def upload(
    payload: TimetableUploadIn,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimetablePreviewOut:
    # 目标人员：admin 可代传 person_id；普通用户仅本人
    if current.role == UserRole.admin and payload.person_id is not None:
        person_id = payload.person_id
    else:
        person_id = people_service.get_person_by_user(db, current.id).id

    # 学期：未传则取当前学期
    semester_id = payload.semester_id
    if semester_id is None:
        from app.services import semester_service

        sem = semester_service.get_current_semester(db)
        if sem is None:
            raise HTTPException(status_code=400, detail="当前无激活学期，请联系管理员")
        semester_id = sem.id

    result = ManualEntryExtractor().extract_from_entries([e.model_dump() for e in payload.entries])
    up = timetable_service.create_upload_from_entries(
        db,
        person_id=person_id,
        semester_id=semester_id,
        uploader_user_id=current.id,
        file_name=payload.file_name,
        entries=result.entries,
    )
    db.commit()
    db.refresh(up)
    return TimetablePreviewOut(
        id=up.id,
        person_id=up.person_id,
        semester_id=up.semester_id,
        file_name=up.file_name,
        parse_status=up.parse_status,
        review_status=up.review_status,
        rules=[CourseRuleOut.model_validate(r) for r in up.course_rules],
    )


@router.get("/active", response_model=list[ActiveTimetableOut])
def get_active(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ActiveTimetableOut]:
    from app.services import semester_service
    from app.models.timetable import TimetableUpload
    from app.models.person import PersonProfile
    from app.models.enums import ReviewStatus
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    current_sem = semester_service.get_current_semester(db)
    if not current_sem:
        return []

    stmt = (
        select(TimetableUpload, PersonProfile)
        .join(PersonProfile, TimetableUpload.person_id == PersonProfile.id)
        .where(
            TimetableUpload.semester_id == current_sem.id,
            TimetableUpload.review_status == ReviewStatus.approved,
        )
        .options(selectinload(TimetableUpload.course_rules))
    )
    results = db.execute(stmt).all()

    out = []
    for up, person in results:
        out.append(
            ActiveTimetableOut(
                person_id=person.id,
                person_name=person.full_name,
                rules=[CourseRuleOut.model_validate(r) for r in up.course_rules],
            )
        )
    return out


@router.get("/export-free")
def export_free_timetable(
    week: int | None = None,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """导出高可读性全员无课表 Excel。"""
    from datetime import date
    from fastapi import Response

    content = timetable_service.build_free_timetable_excel(db, week=week)
    filename = (
        f"free_timetable_{'week_' + str(week) if week else 'all'}_{date.today().isoformat()}.xlsx"
    )
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _load_owned(db: Session, current: User, upload_id: uuid.UUID):
    up = timetable_service._get_upload(db, upload_id)
    if current.role != UserRole.admin:
        prof = people_service.get_person_by_user(db, current.id)
        if up.person_id != prof.id:
            raise HTTPException(status_code=403, detail="无权访问他人课表")
    return up


@router.get("/{upload_id}/preview", response_model=TimetablePreviewOut)
def preview(
    upload_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TimetablePreviewOut:
    up = _load_owned(db, current, upload_id)
    return TimetablePreviewOut(
        id=up.id,
        person_id=up.person_id,
        semester_id=up.semester_id,
        file_name=up.file_name,
        parse_status=up.parse_status,
        review_status=up.review_status,
        rules=[CourseRuleOut.model_validate(r) for r in up.course_rules],
    )


@router.patch("/{upload_id}/parsed-rules/{rule_id}", response_model=CourseRuleOut)
def patch_rule(
    upload_id: uuid.UUID,
    rule_id: uuid.UUID,
    patch: CourseRulePatch,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CourseRuleOut:
    _load_owned(db, current, upload_id)
    rule = timetable_service.update_course_rule(
        db, upload_id, rule_id, patch.model_dump(exclude_unset=True)
    )
    db.commit()
    return CourseRuleOut.model_validate(rule)


@router.post("/{upload_id}/submit", response_model=MessageOut)
def submit(
    upload_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    _load_owned(db, current, upload_id)
    timetable_service.submit_for_review(db, upload_id)
    db.commit()
    return MessageOut(message="已提交，等待 admin 审核")


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
