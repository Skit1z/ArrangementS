"""排班全链路集成测试：岗位生成 -> 求解 -> 落库 -> 发布。"""

from __future__ import annotations

from datetime import date, datetime, time

from sqlalchemy import select

from app.core.security import hash_password
from app.models.availability import AvailabilityBlock
from app.models.enums import (
    AvailabilitySource,
    AvailabilityStatus,
    PersonStatus,
    PlanStatus,
    UserRole,
    VenueType,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot
from app.models.user import User
from app.models.venue import ShiftTemplate, Venue
from app.services import schedule_service

MONDAY = date(2026, 3, 2)


def _yellow(db, templates=2):
    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db.add(v)
    db.flush()
    specs = [("第1班", time(8, 0), time(10, 0)), ("第2班", time(10, 0), time(12, 0))]
    for i, (n, s, e) in enumerate(specs[:templates]):
        db.add(
            ShiftTemplate(
                venue_id=v.id,
                name=n,
                start_time=s,
                end_time=e,
                credited_minutes=120,
                weekday_required_people=2,
                weekend_required_people=1,
                sort_order=i,
            )
        )
    db.flush()
    return v


def _person(db, i):
    u = User(username=f"u{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no=f"u{i}",
        class_name="一班",
        full_name=f"人{i}",
        phone="13800000000",
        status=PersonStatus.active,
        is_in_scheduling_pool=True,
    )
    db.add(p)
    db.flush()
    return p


def test_generate_fills_weekday_slots(db_session):
    _yellow(db_session, templates=2)
    for i in range(4):
        _person(db_session, i)
    db_session.commit()

    summary = schedule_service.generate(
        db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1
    )
    db_session.commit()
    assert summary["vacancies"] == 0

    # 周一（工作日）第1班应有 2 个已分配、互不相同的人
    slots = list(db_session.scalars(select(DutySlot)))
    monday_shift1 = next(s for s in slots if s.slot_start_at == datetime(2026, 3, 2, 8, 0))
    assert monday_shift1.required_people == 2
    people = [a.person_id for a in monday_shift1.assignments if a.person_id]
    assert len(people) == 2 and len(set(people)) == 2

    # 周六（2026-03-07）第1班仅需 1 人
    sat_shift1 = next(s for s in slots if s.slot_start_at == datetime(2026, 3, 7, 8, 0))
    assert sat_shift1.required_people == 1


def test_filled_slot_status_is_filled(db_session):
    # 回归：assignment 经 duty_slot_id 创建不会回填 slot.assignments，
    # 曾导致排满的岗位状态仍为 open。
    _yellow(db_session, templates=1)
    for i in range(3):
        _person(db_session, i)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    db_session.commit()

    from app.models.enums import SlotStatus

    slots = list(db_session.scalars(select(DutySlot)))
    monday1 = next(s for s in slots if s.slot_start_at == datetime(2026, 3, 2, 8, 0))
    assert monday1.required_people == 2
    assert monday1.status == SlotStatus.filled


def test_yellow_credited_fixed_120(db_session):
    _yellow(db_session, templates=1)
    _person(db_session, 0)
    _person(db_session, 1)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    db_session.commit()
    a = db_session.scalar(select(Assignment).where(Assignment.person_id.isnot(None)))
    assert a.credited_minutes == 120
    assert a.balance_minutes == 120


def test_course_conflict_excludes_person(db_session):
    _yellow(db_session, templates=1)
    p0 = _person(db_session, 0)
    _person(db_session, 1)
    _person(db_session, 2)
    # p0 在周一第1班时间有课
    db_session.add(
        AvailabilityBlock(
            person_id=p0.id,
            source=AvailabilitySource.course,
            start_at=datetime(2026, 3, 2, 8, 0),
            end_at=datetime(2026, 3, 2, 10, 0),
            status=AvailabilityStatus.active,
        )
    )
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    db_session.commit()
    slots = list(db_session.scalars(select(DutySlot)))
    monday1 = next(s for s in slots if s.slot_start_at == datetime(2026, 3, 2, 8, 0))
    assigned = {a.person_id for a in monday1.assignments if a.person_id}
    assert p0.id not in assigned  # 有课冲突不被排入


def test_publish_sets_status_and_assigned(db_session):
    _yellow(db_session, templates=1)
    _person(db_session, 0)
    _person(db_session, 1)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    db_session.commit()
    plan = schedule_service.publish(db_session, MONDAY, actor_id=None)
    db_session.commit()
    assert plan.status == PlanStatus.published
    assert plan.published_at is not None


def test_reproducible_generate(db_session):
    _yellow(db_session, templates=2)
    for i in range(5):
        _person(db_session, i)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=7)
    db_session.commit()
    first = {
        (str(a.duty_slot_id), a.position_index): str(a.person_id)
        for a in db_session.scalars(select(Assignment))
        if a.person_id
    }
    # 同 seed 直接复跑求解器应得到相同分配；省去第二次完整 generate 管线，验证确定性
    from app.models.schedule import WeeklyPlan
    from app.scheduling.eligibility import build_solver_input
    from app.scheduling.solver import solve

    plan = db_session.scalars(select(WeeklyPlan)).first()
    second = solve(build_solver_input(db_session, plan, seed=7, max_time_seconds=2.0))
    second_set = {str(p) for p in second.assignments.values() if p is not None}
    assert set(first.values()) == second_set


def test_generate_preserves_locked_slot_and_assignment(db_session):
    _yellow(db_session, templates=1)
    for i in range(3):
        _person(db_session, i)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    db_session.commit()

    locked_slot = db_session.scalar(select(DutySlot).order_by(DutySlot.slot_start_at))
    locked_assignment = next(a for a in locked_slot.assignments if a.person_id is not None)
    original_slot_id = locked_slot.id
    original_assignment_id = locked_assignment.id
    original_person_id = locked_assignment.person_id
    schedule_service.set_lock(db_session, locked_assignment.id, True)
    db_session.commit()

    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=9)
    db_session.commit()
    assert db_session.get(DutySlot, original_slot_id).is_locked is True
    preserved = db_session.get(Assignment, original_assignment_id)
    assert preserved.person_id == original_person_id
    matching = list(
        db_session.scalars(
            select(DutySlot).where(
                DutySlot.source_id == locked_slot.source_id,
                DutySlot.slot_start_at == locked_slot.slot_start_at,
            )
        )
    )
    assert len(matching) == 1


def test_republish_after_unpublish_bumps_revision(db_session):
    _yellow(db_session, templates=1)
    _person(db_session, 0)
    _person(db_session, 1)
    db_session.commit()
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    plan = schedule_service.publish(db_session, MONDAY, actor_id=None)
    initial_revision = plan.revision
    schedule_service.unpublish(db_session, MONDAY, actor_id=None)
    plan = schedule_service.publish(db_session, MONDAY, actor_id=None)
    assert plan.revision == initial_revision + 1


# --- 增量排班：把新任务追加到已发布的当前周计划 ---
def test_add_task_to_published_plan_creates_slot_and_vacant_assignments(db_session):
    """已发布周计划创建后，再创建一个当天任务，调用增量服务应：
    1) 在已发布计划上新增 DutySlot
    2) 创建 required_people 个空缺 assignment（不破坏现有排班）
    3) 提升已发布计划修订号
    """
    from datetime import timedelta, timezone
    from app.models.enums import (
        PlanAssignmentStatus,
        SlotSourceType,
        TaskStatus,
    )
    from app.services import schedule_service, task_service

    # 场地：1 个固定班次 + 1 个事件场地
    _yellow(db_session)
    event_v = Venue(
        name="蓝厅", code="LT", venue_type=VenueType.event_based, default_required_people=2
    )
    db_session.add(event_v)
    db_session.flush()
    _person(db_session, 0)
    _person(db_session, 1)
    db_session.commit()

    # 生成并发布本周计划
    schedule_service.generate(db_session, MONDAY, actor_id=None, max_time_seconds=2.0, seed=1)
    plan = db_session.scalars(
        select(__import__("app.models.schedule", fromlist=["WeeklyPlan"]).WeeklyPlan)
    ).first()
    initial_revision = plan.revision
    schedule_service.publish(db_session, MONDAY, actor_id=None)
    db_session.commit()
    len(list(db_session.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id))))

    # 创建一个属于本周三的任务
    wed = datetime.combine(MONDAY + timedelta(days=2), time(14, 0), tzinfo=timezone.utc)
    task = task_service.create_task(
        db_session,
        venue_id=event_v.id,
        title="讲座",
        booking_start_at=wed,
        booking_end_at=wed + timedelta(hours=2),
    )
    task_service.transition_task(db_session, task.id, TaskStatus.confirmed)  # 进排班池
    db_session.commit()

    # 增量追加
    schedule_service.add_task_to_plan(db_session, task.id)
    db_session.commit()

    # 验证：新增了 1 个 venue_task slot
    new_slots = list(
        db_session.scalars(
            select(DutySlot).where(
                DutySlot.weekly_plan_id == plan.id,
                DutySlot.source_type == SlotSourceType.venue_task,
            )
        )
    )
    assert len(new_slots) == 1
    assert new_slots[0].source_id == task.id

    # 验证：创建了 required_people(=2) 个空缺 assignment
    vacant_assignments = list(
        db_session.scalars(
            select(Assignment).where(
                Assignment.duty_slot_id == new_slots[0].id,
            )
        )
    )
    assert len(vacant_assignments) == 2
    assert all(a.plan_status == PlanAssignmentStatus.vacant for a in vacant_assignments)
    assert all(a.person_id is None for a in vacant_assignments)

    # 验证：修订号提升（已发布计划的修改）
    db_session.refresh(plan)
    assert plan.revision == initial_revision + 1


def test_add_task_to_draft_plan_no_revision_bump(db_session):
    """草稿计划追加任务时不提升修订号（还没发布）。"""
    from datetime import timedelta, timezone
    from app.models.enums import TaskStatus
    from app.models.schedule import WeeklyPlan
    from app.services import schedule_service, task_service

    event_v = Venue(
        name="蓝厅", code="LT", venue_type=VenueType.event_based, default_required_people=2
    )
    db_session.add(event_v)
    db_session.flush()
    db_session.commit()

    # 直接造一个草稿计划
    plan = WeeklyPlan(
        week_start=MONDAY,
        week_end=MONDAY + timedelta(days=6),
        revision=1,
        status=__import__("app.models.enums", fromlist=["PlanStatus"]).PlanStatus.draft,
    )
    db_session.add(plan)
    db_session.flush()

    wed = datetime.combine(MONDAY + timedelta(days=2), time(14, 0), tzinfo=timezone.utc)
    task = task_service.create_task(
        db_session,
        venue_id=event_v.id,
        title="讲座",
        booking_start_at=wed,
        booking_end_at=wed + timedelta(hours=2),
    )
    task_service.transition_task(db_session, task.id, TaskStatus.confirmed)
    db_session.commit()

    initial_revision = plan.revision
    schedule_service.add_task_to_plan(db_session, task.id)
    db_session.commit()
    db_session.refresh(plan)
    assert plan.revision == initial_revision  # 草稿不提升
