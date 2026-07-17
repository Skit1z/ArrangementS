"""课表时间解析、区间生成与审核生效流程测试。"""
from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import select

from app.models.availability import AvailabilityBlock
from app.models.enums import AvailabilityStatus, BuildingType, ReviewStatus
from app.models.person import PersonProfile
from app.models.user import User
from app.services import semester_service, timetable_service
from app.timetable.availability import (
    PeriodTime,
    generate_intervals,
    resolve_period_time,
)
from app.timetable.extractor import RawCourseEntry


def _rules():
    return [
        PeriodTime(1, 2, BuildingType.all, time(8, 0), time(9, 50)),
        PeriodTime(3, 4, BuildingType.main, time(10, 5), time(11, 55)),
        PeriodTime(3, 4, BuildingType.second, time(10, 20), time(12, 10)),
        PeriodTime(5, 6, BuildingType.all, time(14, 0), time(15, 50)),
    ]


def test_resolve_period_main_vs_second():
    assert resolve_period_time(_rules(), BuildingType.main, 3, 4) == (time(10, 5), time(11, 55))
    assert resolve_period_time(_rules(), BuildingType.second, 3, 4) == (time(10, 20), time(12, 10))


def test_resolve_falls_back_to_all():
    assert resolve_period_time(_rules(), BuildingType.main, 1, 2) == (time(8, 0), time(9, 50))


def test_generate_intervals_dates():
    # 第一周星期一 2026-03-02（周一）；weekday=3(周三)，第 1、2 周
    first_monday = date(2026, 3, 2)
    ivs = generate_intervals(first_monday, 3, time(8, 0), time(9, 50), [1, 2])
    assert ivs[0][0] == datetime(2026, 3, 4, 8, 0)  # 第1周周三
    assert ivs[1][0] == datetime(2026, 3, 11, 8, 0)  # 第2周周三


def test_generate_intervals_buffer():
    ivs = generate_intervals(date(2026, 3, 2), 1, time(8, 0), time(9, 50), [1], buffer_minutes=10)
    assert ivs[0][0] == datetime(2026, 3, 2, 7, 50)
    assert ivs[0][1] == datetime(2026, 3, 2, 10, 0)


def _make_person(db):
    from app.core.security import hash_password
    from app.models.enums import UserRole

    u = User(username="s9", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(user_id=u.id, student_no="s9", class_name="一班", full_name="甲", phone="13800000000")
    db.add(p)
    db.flush()
    return p


def test_upload_does_not_generate_blocks_until_approved(db_session):
    sem = semester_service.create_semester(db_session, name="秋", first_monday=date(2026, 9, 7))
    p = _make_person(db_session)
    db_session.commit()

    entries = [RawCourseEntry(weekday=3, period_start=3, period_end=4, week_expr="1-8周", location_code="B608", course_name="高数")]
    upload = timetable_service.create_upload_from_entries(
        db_session, person_id=p.id, semester_id=sem.id, uploader_user_id=None,
        file_name="t.pdf", entries=entries,
    )
    db_session.commit()

    # 上传后仅有课程规则，未生成任何不可值班区间（红线：未确认不得生效）
    rule = upload.course_rules[0]
    assert rule.building_type == BuildingType.main
    assert rule.explicit_weeks == list(range(1, 9))
    blocks = list(db_session.scalars(select(AvailabilityBlock)))
    assert blocks == []

    # 审核通过后生成区间
    timetable_service.approve(db_session, upload.id, reviewer_id=None)
    db_session.commit()
    blocks = list(db_session.scalars(select(AvailabilityBlock).where(AvailabilityBlock.status == AvailabilityStatus.active)))
    assert len(blocks) == 8  # 8 周各一条


def test_unknown_location_flags_review(db_session):
    sem = semester_service.create_semester(db_session, name="秋", first_monday=date(2026, 9, 7))
    p = _make_person(db_session)
    db_session.commit()
    entries = [RawCourseEntry(weekday=1, period_start=1, period_end=2, week_expr="1-4周", location_code="ZZ9")]
    upload = timetable_service.create_upload_from_entries(
        db_session, person_id=p.id, semester_id=sem.id, uploader_user_id=None, file_name="t.pdf", entries=entries,
    )
    db_session.commit()
    assert upload.course_rules[0].needs_review is True


def test_semester_end_expires_blocks(db_session):
    sem = semester_service.create_semester(db_session, name="秋", first_monday=date(2026, 9, 7))
    p = _make_person(db_session)
    db_session.commit()
    entries = [RawCourseEntry(weekday=3, period_start=1, period_end=2, week_expr="1-4周", location_code="B101")]
    upload = timetable_service.create_upload_from_entries(
        db_session, person_id=p.id, semester_id=sem.id, uploader_user_id=None, file_name="t.pdf", entries=entries,
    )
    timetable_service.approve(db_session, upload.id, reviewer_id=None)
    db_session.commit()
    assert len(list(db_session.scalars(select(AvailabilityBlock).where(AvailabilityBlock.status == AvailabilityStatus.active)))) == 4

    timetable_service.expire_semester_courses(db_session, sem.id)
    db_session.commit()
    active = list(db_session.scalars(select(AvailabilityBlock).where(AvailabilityBlock.status == AvailabilityStatus.active)))
    assert active == []
    db_session.refresh(upload)
    assert upload.review_status == ReviewStatus.superseded


def test_new_upload_supersedes_previous(db_session):
    sem = semester_service.create_semester(db_session, name="秋", first_monday=date(2026, 9, 7))
    p = _make_person(db_session)
    db_session.commit()
    e1 = [RawCourseEntry(weekday=1, period_start=1, period_end=2, week_expr="1-2周", location_code="B101")]
    up1 = timetable_service.create_upload_from_entries(db_session, person_id=p.id, semester_id=sem.id, uploader_user_id=None, file_name="a.pdf", entries=e1)
    timetable_service.approve(db_session, up1.id, reviewer_id=None)
    db_session.commit()

    e2 = [RawCourseEntry(weekday=2, period_start=1, period_end=2, week_expr="1-3周", location_code="B101")]
    up2 = timetable_service.create_upload_from_entries(db_session, person_id=p.id, semester_id=sem.id, uploader_user_id=None, file_name="b.pdf", entries=e2)
    timetable_service.approve(db_session, up2.id, reviewer_id=None)
    db_session.commit()

    db_session.refresh(up1)
    assert up1.review_status == ReviewStatus.superseded
    active = list(db_session.scalars(select(AvailabilityBlock).where(AvailabilityBlock.status == AvailabilityStatus.active)))
    assert len(active) == 3  # 仅新版本 3 周
