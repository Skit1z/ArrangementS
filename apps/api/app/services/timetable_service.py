"""课表编排：抽取结果 -> 课程规则(预览) -> 审核生效 -> 不可值班区间生成（方案 4.6 / 5.1）。

关键红线：
- 课表未经确认不得直接影响排班（写 CourseRule 但不生成 AvailabilityBlock，直至 approve）。
- 学期结束后旧课表与其生成的不可值班区间自动逻辑失效。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import AvailabilityBlock
from app.models.enums import (
    AvailabilitySource,
    AvailabilityStatus,
    ParseStatus,
    ReviewStatus,
)
from app.models.semester import CoursePeriodRule, Semester
from app.models.timetable import CourseRule, TimetableUpload
from app.services.intervals import merge_intervals
from app.services.semester_service import resolve_building_type
from app.timetable.availability import (
    generate_intervals,
    period_time_from_rule,
    resolve_period_time,
)
from app.timetable.extractor import RawCourseEntry
from app.timetable.week_parser import WeekParseError, parse_weeks

PARSER_VERSION = "v1"


def create_upload_from_entries(
    db: Session,
    *,
    person_id: uuid.UUID,
    semester_id: uuid.UUID,
    uploader_user_id: uuid.UUID | None,
    file_name: str,
    entries: list[RawCourseEntry],
    file_hash: str | None = None,
    storage_key: str | None = None,
) -> TimetableUpload:
    semester = db.get(Semester, semester_id)
    if semester is None:
        raise HTTPException(status_code=404, detail="学期不存在")

    upload = TimetableUpload(
        person_id=person_id,
        semester_id=semester_id,
        uploader_user_id=uploader_user_id,
        file_name=file_name,
        file_hash=file_hash,
        storage_key=storage_key,
        parse_status=ParseStatus.parsed,
        review_status=ReviewStatus.draft,
        parser_version=PARSER_VERSION,
    )
    db.add(upload)
    db.flush()

    orm_rules = db.scalars(
        select(CoursePeriodRule).where(
            CoursePeriodRule.semester_id == semester_id,
            CoursePeriodRule.is_active.is_(True),
        )
    )
    period_rules = [period_time_from_rule(r) for r in orm_rules]

    for entry in entries:
        upload.course_rules.append(
            _build_course_rule(db, semester_id, period_rules, entry, max_week=semester.week_count)
        )
    db.flush()
    return upload


def _build_course_rule(
    db: Session, semester_id: uuid.UUID, period_rules, entry: RawCourseEntry, *, max_week: int = 20
) -> CourseRule:
    needs_review = False
    warnings: list[str] = []

    building_type = None
    if entry.location_code:
        building_type = resolve_building_type(db, semester_id, entry.location_code)
    if building_type is None:
        needs_review = True
        warnings.append("教学楼代码未识别")

    week_start = week_end = None
    parity = "all"
    explicit_weeks: list[int] = []
    try:
        spec = parse_weeks(entry.week_expr, max_week=max_week)
        week_start, week_end, parity = spec.week_start, spec.week_end, spec.parity
        explicit_weeks = spec.explicit_weeks
        if spec.warnings:
            needs_review = True
    except WeekParseError:
        needs_review = True

    start_time = end_time = None
    if building_type is not None:
        resolved = resolve_period_time(
            period_rules, building_type, entry.period_start, entry.period_end
        )
        if resolved is None:
            needs_review = True
        else:
            start_time, end_time = resolved

    if entry.confidence is not None and entry.confidence < 0.8:
        needs_review = True

    return CourseRule(
        course_name=entry.course_name,
        weekday=entry.weekday,
        period_start=entry.period_start,
        period_end=entry.period_end,
        week_start=week_start,
        week_end=week_end,
        week_parity=parity,
        explicit_weeks=explicit_weeks or None,
        location_code=entry.location_code,
        building_type=building_type,
        start_time=start_time,
        end_time=end_time,
        confidence=entry.confidence,
        needs_review=needs_review,
    )


def _period_rules_for(db: Session, semester_id: uuid.UUID):
    orm_rules = db.scalars(
        select(CoursePeriodRule).where(
            CoursePeriodRule.semester_id == semester_id,
            CoursePeriodRule.is_active.is_(True),
        )
    )
    return [period_time_from_rule(r) for r in orm_rules]


def update_course_rule(
    db: Session, upload_id: uuid.UUID, rule_id: uuid.UUID, patch: dict
) -> CourseRule:
    """人工修正单条课程规则并重新解析（周次/建筑/时间/needs_review）。"""
    upload = _get_upload(db, upload_id)
    rule = db.get(CourseRule, rule_id)
    if rule is None or rule.timetable_upload_id != upload.id:
        raise HTTPException(status_code=404, detail="课程规则不存在")

    if "course_name" in patch and patch["course_name"] is not None:
        rule.course_name = patch["course_name"]
    if patch.get("weekday") is not None:
        rule.weekday = patch["weekday"]
    if patch.get("period_start") is not None:
        rule.period_start = patch["period_start"]
    if patch.get("period_end") is not None:
        rule.period_end = patch["period_end"]
    if patch.get("location_code") is not None:
        rule.location_code = patch["location_code"]

    needs_review = False
    rule.building_type = (
        resolve_building_type(db, upload.semester_id, rule.location_code)
        if rule.location_code
        else None
    )
    if rule.building_type is None:
        needs_review = True

    if patch.get("week_expr"):
        semester = db.get(Semester, upload.semester_id)
        max_week = semester.week_count if semester else 20
        try:
            spec = parse_weeks(patch["week_expr"], max_week=max_week)
            rule.week_start, rule.week_end = spec.week_start, spec.week_end
            rule.week_parity = spec.parity
            rule.explicit_weeks = spec.explicit_weeks
            if spec.warnings:
                needs_review = True
        except WeekParseError:
            needs_review = True

    if rule.building_type is not None:
        resolved = resolve_period_time(
            _period_rules_for(db, upload.semester_id),
            rule.building_type,
            rule.period_start,
            rule.period_end,
        )
        if resolved is None:
            needs_review = True
        else:
            rule.start_time, rule.end_time = resolved

    rule.needs_review = patch.get("needs_review", needs_review)
    db.flush()
    return rule


def submit_for_review(db: Session, upload_id: uuid.UUID) -> TimetableUpload:
    upload = _get_upload(db, upload_id)
    upload.review_status = ReviewStatus.pending
    db.flush()
    return upload


def approve(db: Session, upload_id: uuid.UUID, reviewer_id: uuid.UUID | None) -> TimetableUpload:
    """审核通过：使旧生效版本失效，生成本次不可值班区间。"""
    upload = _get_upload(db, upload_id)
    semester = db.get(Semester, upload.semester_id)

    _supersede_previous(db, upload)

    intervals: list[tuple[datetime, datetime]] = []
    for rule in upload.course_rules:
        if rule.start_time is None or rule.end_time is None or not rule.explicit_weeks:
            continue  # 未解析完整的规则不生成区间，留待人工修正后再审
        buffer = semester.course_buffer_minutes if semester.course_buffer_enabled else 0
        intervals.extend(
            generate_intervals(
                semester.first_monday,
                rule.weekday,
                rule.start_time,
                rule.end_time,
                rule.explicit_weeks,
                buffer,
            )
        )

    now = datetime.now(timezone.utc)
    for start, end in merge_intervals(intervals):
        db.add(
            AvailabilityBlock(
                person_id=upload.person_id,
                source=AvailabilitySource.course,
                start_at=start,
                end_at=end,
                status=AvailabilityStatus.active,
                reason="课程",
                source_ref_id=upload.id,
                approved_by=reviewer_id,
                approved_at=now,
            )
        )

    upload.review_status = ReviewStatus.approved
    upload.confirmed_at = now
    db.flush()
    return upload


def reject(db: Session, upload_id: uuid.UUID) -> TimetableUpload:
    upload = _get_upload(db, upload_id)
    upload.review_status = ReviewStatus.rejected
    db.flush()
    return upload


def _supersede_previous(db: Session, current: TimetableUpload) -> None:
    """把同一人同一学期的旧生效课表标记 superseded，并使其课程区间失效。"""
    previous = db.scalars(
        select(TimetableUpload).where(
            TimetableUpload.person_id == current.person_id,
            TimetableUpload.semester_id == current.semester_id,
            TimetableUpload.review_status == ReviewStatus.approved,
            TimetableUpload.id != current.id,
        )
    )
    for up in previous:
        up.review_status = ReviewStatus.superseded
        _expire_blocks_of_upload(db, up.id)


def _expire_blocks_of_upload(db: Session, upload_id: uuid.UUID) -> None:
    blocks = db.scalars(
        select(AvailabilityBlock).where(
            AvailabilityBlock.source == AvailabilitySource.course,
            AvailabilityBlock.source_ref_id == upload_id,
            AvailabilityBlock.status == AvailabilityStatus.active,
        )
    )
    for b in blocks:
        b.status = AvailabilityStatus.expired


def expire_semester_courses(db: Session, semester_id: uuid.UUID) -> int:
    """学期结束：该学期课表逻辑失效，其课程不可值班区间一并失效（方案 4.8）。"""
    uploads = list(
        db.scalars(
            select(TimetableUpload).where(
                TimetableUpload.semester_id == semester_id,
                TimetableUpload.review_status == ReviewStatus.approved,
            )
        )
    )
    for up in uploads:
        up.review_status = ReviewStatus.superseded
        _expire_blocks_of_upload(db, up.id)
    db.flush()
    return len(uploads)


def _get_upload(db: Session, upload_id: uuid.UUID) -> TimetableUpload:
    upload = db.get(TimetableUpload, upload_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="课表上传不存在")
    return upload
