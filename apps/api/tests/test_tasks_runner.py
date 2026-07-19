"""周期任务接线测试（方案 7.4 / 4.8）。

直接测 app.tasks.runner 的 job_* 函数体（不启真实 scheduler），
验证两个原本未被调用的服务函数在此正确接线。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from app.models.enums import (
    ExecutionStatus,
    PlanAssignmentStatus,
    PlanStatus,
    SlotSourceType,
    SlotStatus,
    UserRole,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.models.user import User
from app.services import semester_service, timetable_service
from app.tasks import runner
from app.timetable.extractor import RawCourseEntry


def _person(db):
    u = User(username="ta1", password_hash="x", role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(user_id=u.id, student_no="ta1", class_name="一班", full_name="甲", phone="13800000000")
    db.add(p)
    db.flush()
    return p


def _venue(db):
    from app.models.enums import VenueType
    from app.models.venue import Venue

    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db.add(v)
    db.flush()
    return v


def test_job_auto_complete_completes_ended(db_session):
    """班次结束时间在现在的「待值班」分配应被自动置为已完成。"""
    v = _venue(db_session)
    p = _person(db_session)
    plan = WeeklyPlan(week_start=date(2026, 3, 2), week_end=date(2026, 3, 8), revision=1, status=PlanStatus.published)
    db_session.add(plan)
    db_session.flush()

    end = datetime.now(timezone.utc) - timedelta(minutes=30)
    start = end - timedelta(hours=2)
    slot = DutySlot(
        weekly_plan_id=plan.id, venue_id=v.id, source_type=SlotSourceType.fixed_shift,
        slot_start_at=start, slot_end_at=end, required_people=1,
        credited_minutes=120, month_key="2026-03", status=SlotStatus.filled,
    )
    db_session.add(slot)
    db_session.flush()
    a = Assignment(
        duty_slot_id=slot.id, person_id=p.id, position_index=0,
        plan_status=PlanAssignmentStatus.assigned, execution_status=ExecutionStatus.pending,
        raw_minutes=120, weighted_minutes_before_round=Decimal(120),
        credited_minutes=120, balance_minutes=120,
    )
    db_session.add(a)
    db_session.commit()

    n = runner.job_auto_complete(db=db_session)
    assert n == 1
    db_session.refresh(a)
    assert a.execution_status == ExecutionStatus.completed


def test_job_auto_complete_skips_future(db_session):
    """尚未结束的班次不应被处理。"""
    v = _venue(db_session)
    p = _person(db_session)
    plan = WeeklyPlan(week_start=date(2026, 3, 2), week_end=date(2026, 3, 8), revision=1, status=PlanStatus.published)
    db_session.add(plan)
    db_session.flush()

    start = datetime.now(timezone.utc) + timedelta(hours=1)  # 未来
    end = start + timedelta(hours=2)
    slot = DutySlot(
        weekly_plan_id=plan.id, venue_id=v.id, source_type=SlotSourceType.fixed_shift,
        slot_start_at=start, slot_end_at=end, required_people=1,
        credited_minutes=120, month_key="2026-03", status=SlotStatus.filled,
    )
    db_session.add(slot)
    db_session.flush()
    a = Assignment(
        duty_slot_id=slot.id, person_id=p.id, position_index=0,
        plan_status=PlanAssignmentStatus.assigned, execution_status=ExecutionStatus.pending,
        raw_minutes=120, weighted_minutes_before_round=Decimal(120),
        credited_minutes=120, balance_minutes=120,
    )
    db_session.add(a)
    db_session.commit()

    assert runner.job_auto_complete(db=db_session) == 0
    db_session.refresh(a)
    assert a.execution_status == ExecutionStatus.pending


def test_job_expire_semesters_expires_past(db_session):
    """is_current 且 first_monday+20w <= today 的学期，应失效其已审核课表并置为非当前。"""
    # 学期 20 周前开始 → 20*7 天前；end = first_monday + 20w <= today
    first_monday = datetime.now(timezone.utc).date() - timedelta(weeks=21)
    sem = semester_service.create_semester(db_session, name="旧学期", first_monday=first_monday, is_current=True)
    p = _person(db_session)
    db_session.commit()

    entries = [RawCourseEntry(weekday=3, period_start=3, period_end=4, week_expr="1-8周", location_code="B608", course_name="高数")]
    upload = timetable_service.create_upload_from_entries(
        db_session, person_id=p.id, semester_id=sem.id, uploader_user_id=None,
        file_name="t.pdf", entries=entries,
    )
    db_session.commit()
    timetable_service.approve(db_session, upload.id, reviewer_id=None)
    db_session.commit()
    assert sem.is_current is True
    assert upload.review_status.value == "approved"

    names = runner.job_expire_semesters(db=db_session)
    assert sem.name in names
    db_session.flush()  # 把 runner 对 sem/upload 的修改写库，便于 refresh 校验
    db_session.refresh(sem)
    db_session.refresh(upload)
    assert sem.is_current is False
    assert upload.review_status.value == "superseded"


def test_job_expire_semesters_skips_active(db_session):
    """尚未结束的当前学期不应被处理。"""
    first_monday = datetime.now(timezone.utc).date() - timedelta(weeks=1)  # 才开始 1 周
    sem = semester_service.create_semester(db_session, name="当前学期", first_monday=first_monday, is_current=True)
    db_session.commit()

    names = runner.job_expire_semesters(db=db_session)
    assert names == []
    db_session.refresh(sem)
    assert sem.is_current is True


def test_job_expire_semesters_deactivates_past_without_uploads(db_session):
    """已结束但无任何已审核课表的当前学期：仍应被置为非当前。"""
    first_monday = datetime.now(timezone.utc).date() - timedelta(weeks=21)
    sem = semester_service.create_semester(db_session, name="空过期学期", first_monday=first_monday, is_current=True)
    db_session.commit()
    assert sem.is_current is True

    names = runner.job_expire_semesters(db=db_session)
    assert sem.name in names
    db_session.flush()  # 把 runner 对 sem 的修改写库，便于 refresh 校验
    db_session.refresh(sem)
    assert sem.is_current is False
