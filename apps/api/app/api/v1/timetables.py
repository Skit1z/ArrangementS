"""课表上传、预览、修正与审核路由（方案 4.3 / 4.6 / 13.3）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.timetable import (
    CourseRuleOut,
    CourseRulePatch,
    TimetablePreviewOut,
    TimetableUploadIn,
    ActiveTimetableOut,
)
from app.services import people_service, timetable_service
from app.timetable.extractor import ManualEntryExtractor

router = APIRouter(prefix="/timetables", tags=["timetables"])


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

    result = ManualEntryExtractor().extract_from_entries(
        [e.model_dump() for e in payload.entries]
    )
    up = timetable_service.create_upload_from_entries(
        db,
        person_id=person_id,
        semester_id=payload.semester_id,
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

    current_sem = semester_service.get_current(db)
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
        out.append(ActiveTimetableOut(
            person_id=person.id,
            person_name=person.full_name,
            rules=[CourseRuleOut.model_validate(r) for r in up.course_rules],
        ))
    return out


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
    upload_id: uuid.UUID, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    timetable_service.approve(db, upload_id, actor.id)
    db.commit()
    return MessageOut(message="课表已生效")


@router.post("/{upload_id}/reject", response_model=MessageOut)
def reject(
    upload_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    timetable_service.reject(db, upload_id)
    db.commit()
    return MessageOut(message="课表已驳回")
