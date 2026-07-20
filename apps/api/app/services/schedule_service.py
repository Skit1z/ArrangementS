"""周排班编排：生成岗位 -> 求解 -> 落库分配与工时 -> 发布（方案 8 / 7.3）。"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    AssignmentSource,
    ExecutionStatus,
    PlanAssignmentStatus,
    PlanStatus,
    SlotSourceType,
    SlotStatus,
)
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.scheduling import eligibility, slots
from app.scheduling.solver import ALGORITHM_VERSION, solve
from app.services import multiplier_service
from app.services.audit_service import record_audit
from app.services.hours import compute_event_task_hours


def _get_or_create_plan(db: Session, week_start: date) -> tuple[WeeklyPlan, bool]:
    plan = db.scalar(select(WeeklyPlan).where(WeeklyPlan.week_start == week_start))
    if plan is not None:
        return plan, False
    plan = WeeklyPlan(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        revision=1,
        status=PlanStatus.draft,
    )
    db.add(plan)
    db.flush()
    return plan, True


def mark_plan_changed(db: Session, plan: WeeklyPlan) -> None:
    """Record an in-place content change to a weekly plan."""
    plan.version += 1
    if plan.status == PlanStatus.published:
        plan.revision += 1
    db.flush()


def generate(
    db: Session, week_start: date, actor_id: uuid.UUID | None, seed: int = 42
) -> dict:
    if week_start.isoweekday() != 1:
        raise HTTPException(status_code=422, detail="周起始日必须为周一")

    plan, _created = _get_or_create_plan(db, week_start)
    if plan.status == PlanStatus.published:
        raise HTTPException(status_code=409, detail="已发布计划请使用重新优化或增量排班")

    # 草稿重建只清除自动生成且未锁定的岗位；手工岗位和锁定岗位必须保留。
    for s in list(db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id))):
        if not s.is_locked and s.source_type != SlotSourceType.manual:
            db.delete(s)
    db.flush()

    slots.generate_slots(db, plan)
    solver_input = eligibility.build_solver_input(db, plan, seed=seed)
    try:
        result = solve(solver_input)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result.status not in {"OPTIMAL", "FEASIBLE"}:
        raise HTTPException(
            status_code=409,
            detail="锁定分配与当前排班约束冲突，请先解锁冲突岗位后再生成",
        )

    _persist_assignments(db, plan, result, actor_id)

    plan.generated_at = datetime.now(timezone.utc)
    plan.generated_by = actor_id
    plan.algorithm_version = ALGORITHM_VERSION
    plan.random_seed = seed
    db.flush()

    record_audit(
        db, actor_user_id=actor_id, action="schedule.generate",
        entity_type="weekly_plan", entity_id=plan.id,
        after_data={"vacancies": len(result.vacancies), "status": result.status},
    )
    return {
        "plan_id": str(plan.id),
        "status": result.status,
        "vacancies": len(result.vacancies),
        "spread_minutes": result.spread_minutes,
        "solve_time_seconds": result.solve_time_seconds,
        "algorithm_version": result.algorithm_version,
        "seed": seed,
    }


def _persist_assignments(db: Session, plan: WeeklyPlan, result, actor_id: uuid.UUID | None) -> None:
    engine_rules = multiplier_service.load_engine_rules(db)
    slot_map = {str(s.id): s for s in db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id))}

    filled_counts: dict[str, int] = {}

    # 按岗位聚合 position -> person
    for pos_id, person in result.assignments.items():
        slot_id, pidx = pos_id.rsplit(":", 1)
        slot = slot_map[slot_id]
        position_index = int(pidx)
        raw, weighted, credited = _assignment_hours(slot, engine_rules)
        if person is not None:
            filled_counts[slot_id] = filled_counts.get(slot_id, 0) + 1

        assignment = db.scalar(
            select(Assignment).where(
                Assignment.duty_slot_id == slot.id,
                Assignment.position_index == position_index,
            )
        )
        # 锁定岗位复用原 assignment，未锁定岗位通常走创建分支。
        if assignment is None:
            assignment = Assignment(duty_slot_id=slot.id, position_index=position_index)
            db.add(assignment)

        if person is None:
            assignment.person_id = None
            assignment.assignment_source = AssignmentSource.auto
            assignment.plan_status = PlanAssignmentStatus.vacant
            assignment.execution_status = ExecutionStatus.pending
            assignment.raw_minutes = 0
            assignment.weighted_minutes_before_round = Decimal(0)
            assignment.credited_minutes = 0
            assignment.balance_minutes = 0
            assignment.created_by = assignment.created_by or actor_id
        else:
            assignment.person_id = uuid.UUID(person)
            if not slot.is_locked and slot.source_type != SlotSourceType.manual:
                assignment.assignment_source = AssignmentSource.auto
            assignment.plan_status = PlanAssignmentStatus.pending
            assignment.execution_status = ExecutionStatus.pending
            assignment.raw_minutes = raw
            assignment.weighted_minutes_before_round = weighted
            assignment.credited_minutes = credited
            assignment.balance_minutes = credited
            assignment.created_by = assignment.created_by or actor_id

    # 更新 slot 状态。注意：assignment 通过 duty_slot_id 创建，不会回填 slot.assignments 关系，
    # 因此这里用求解结果直接计数，不读关系集合。
    for slot_id, slot in slot_map.items():
        filled = filled_counts.get(slot_id, 0)
        slot.status = SlotStatus.filled if filled >= slot.required_people else SlotStatus.open
    db.flush()


def _assignment_hours(slot: DutySlot, engine_rules) -> tuple[int, Decimal, int]:
    if slot.source_type == SlotSourceType.fixed_shift:
        # 黄楼固定工时，不倍率、不取整
        return slot.credited_minutes, Decimal(slot.credited_minutes), slot.credited_minutes
    r = compute_event_task_hours(slot.slot_start_at, slot.slot_end_at, engine_rules, venue_id=str(slot.venue_id))
    return r.raw_minutes, r.weighted_minutes_before_round, r.credited_minutes


def publish(db: Session, week_start: date, actor_id: uuid.UUID | None) -> WeeklyPlan:
    plan = db.scalar(select(WeeklyPlan).where(WeeklyPlan.week_start == week_start))
    if plan is None:
        raise HTTPException(status_code=404, detail="周计划不存在")
    for slot in db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id)):
        for a in slot.assignments:
            if a.plan_status == PlanAssignmentStatus.pending and a.person_id is not None:
                a.plan_status = PlanAssignmentStatus.assigned
    was_published = plan.status == PlanStatus.published
    was_published_before = plan.published_at is not None
    plan.status = PlanStatus.published
    plan.published_at = datetime.now(timezone.utc)
    plan.published_by = actor_id
    if was_published or (not was_published and was_published_before):
        plan.revision += 1
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="schedule.publish",
        entity_type="weekly_plan", entity_id=plan.id,
        after_data={"revision": plan.revision},
    )
    return plan


def unpublish(db: Session, week_start: date, actor_id: uuid.UUID | None) -> WeeklyPlan:
    plan = db.scalar(select(WeeklyPlan).where(WeeklyPlan.week_start == week_start))
    if plan is None:
        raise HTTPException(status_code=404, detail="周计划不存在")
    if plan.status != PlanStatus.published:
        raise HTTPException(status_code=400, detail="周计划尚未发布或已是草稿状态")

    plan.status = PlanStatus.draft
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="schedule.unpublish",
        entity_type="weekly_plan", entity_id=plan.id,
        after_data={"revision": plan.revision},
    )
    return plan


def add_task_to_plan(db: Session, task_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> DutySlot:
    """把一个已确认的 VenueTask 增量追加到其所在周的周计划（不论已发布或草稿）。

    场景：周计划已发布后，admin 又创建/确认了一个当天任务，调用本函数会在不破坏
    现有排班的前提下新增 DutySlot，并为其每个 required_people 岗位创建空缺 assignment。
    admin 随后可手动把人拖上去（draft_service.apply_operations）。

    若计划已发布，会提升修订号以触发前端刷新。若该任务在此周已有 slot（重复调用），抛 409。
    """
    from app.models.enums import (
        AssignmentSource,
        ExecutionStatus,
        PlanAssignmentStatus,
        SlotSourceType,
        SlotStatus,
        TaskStatus,
    )
    from app.models.venue_task import VenueTask
    from app.scheduling.slots import BEIJING_TZ, month_key

    task = db.get(VenueTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task.status not in (
        TaskStatus.confirmed,
    ):
        raise HTTPException(status_code=422, detail=f"任务状态「{task.status.value}」不可加入排班")

    # 定位所在周（基于 duty_start_at 的北京时间日期）
    duty_local = task.duty_start_at.astimezone(BEIJING_TZ) if task.duty_start_at.tzinfo else task.duty_start_at
    week_start = duty_local.date() - timedelta(days=duty_local.weekday())
    plan, _created = _get_or_create_plan(db, week_start)

    # 防重复
    exists = db.scalar(
        select(DutySlot.id).where(
            DutySlot.weekly_plan_id == plan.id,
            DutySlot.source_type == SlotSourceType.venue_task,
            DutySlot.source_id == task.id,
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="该任务已在此周计划中")

    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=task.venue_id,
        source_type=SlotSourceType.venue_task,
        source_id=task.id,
        slot_start_at=task.duty_start_at,
        slot_end_at=task.duty_end_at,
        required_people=task.required_people,
        credited_minutes=0,  # 任务工时按倍率逐人计算，落到 assignment
        month_key=month_key(duty_local.date()),
        status=SlotStatus.open,
    )
    db.add(slot)
    db.flush()

    for pidx in range(task.required_people):
        db.add(Assignment(
            duty_slot_id=slot.id, person_id=None, position_index=pidx,
            assignment_source=AssignmentSource.auto,
            plan_status=PlanAssignmentStatus.vacant,
            execution_status=ExecutionStatus.pending,
            raw_minutes=0, weighted_minutes_before_round=Decimal(0),
            credited_minutes=0, balance_minutes=0, created_by=actor_id,
        ))

    was_published = plan.status == PlanStatus.published
    task.status = TaskStatus.scheduled
    task.version += 1
    mark_plan_changed(db, plan)

    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="schedule.add_task",
        entity_type="weekly_plan", entity_id=plan.id,
        after_data={"task_id": str(task.id), "slot_id": str(slot.id), "published": was_published},
    )
    return slot


def get_plan(db: Session, week_start: date) -> WeeklyPlan:
    plan = db.scalar(select(WeeklyPlan).where(WeeklyPlan.week_start == week_start))
    if plan is None:
        plan, _created = _get_or_create_plan(db, week_start)
        slots.generate_slots(db, plan)
        db.flush()
    return plan


def get_week_label(db: Session, week_start: date) -> str:
    from app.models.semester import Semester
    from datetime import timedelta

    semesters = list(db.scalars(select(Semester).order_by(Semester.first_monday.asc())))
    if not semesters:
        return f"{week_start.year}年 第{week_start.isocalendar()[1]}周"

    # 1. Check if falls within any semester
    for sem in semesters:
        sem_end = sem.first_monday + timedelta(weeks=sem.week_count)
        if sem.first_monday <= week_start < sem_end:
            diff_days = (week_start - sem.first_monday).days
            week_num = (diff_days // 7) + 1
            return f"{sem.name} 第{week_num}周"

    # 2. Check if falls in a vacation after a semester
    prev_sems = [s for s in semesters if s.first_monday <= week_start]
    if prev_sems:
        latest_sem = prev_sems[-1]
        sem_end = latest_sem.first_monday + timedelta(weeks=latest_sem.week_count)
        if week_start >= sem_end:
            diff_days = (week_start - sem_end).days
            vacation_week = (diff_days // 7) + 1
            is_winter = sem_end.month in [1, 2, 3, 11, 12]
            vacation_name = "寒假" if is_winter else "暑假"
            return f"{latest_sem.name}后 {vacation_name}第{vacation_week}周"

    # 3. If before the first semester in DB
    first_sem = semesters[0]
    if week_start < first_sem.first_monday:
        diff_days = (first_sem.first_monday - week_start).days
        weeks_before = (diff_days + 6) // 7
        is_winter = first_sem.first_monday.month in [2, 3]
        vacation_name = "寒假" if is_winter else "暑假"
        return f"{first_sem.name}前 {vacation_name}第{weeks_before}周"

    return f"{week_start.year}年 第{week_start.isocalendar()[1]}周"


def serialize_week(db: Session, plan: WeeklyPlan) -> dict:
    from app.models.person import PersonProfile

    slot_rows = list(
        db.scalars(
            select(DutySlot).where(DutySlot.weekly_plan_id == plan.id).order_by(DutySlot.slot_start_at)
        )
    )
    visible_statuses = (PlanAssignmentStatus.assigned, PlanAssignmentStatus.pending)
    person_ids = {
        a.person_id
        for s in slot_rows
        for a in s.assignments
        if a.person_id and a.plan_status in visible_statuses
    }
    names = {
        p.id: p.full_name
        for p in db.scalars(select(PersonProfile).where(PersonProfile.id.in_(person_ids)))
    } if person_ids else {}

    return {
        "plan_id": plan.id,
        "week_start": plan.week_start,
        "week_end": plan.week_end,
        "status": plan.status.value,
        "revision": plan.revision,
        "version": plan.version,
        "week_label": get_week_label(db, plan.week_start),
        "slots": [
            {
                "id": s.id,
                "venue_id": s.venue_id,
                "source_type": s.source_type.value,
                "slot_start_at": s.slot_start_at,
                "slot_end_at": s.slot_end_at,
                "required_people": s.required_people,
                "month_key": s.month_key,
                "status": s.status.value,
                "is_locked": s.is_locked,
                "assignments": [
                    {
                        "id": a.id,
                        "person_id": a.person_id if a.plan_status in visible_statuses else None,
                        "person_name": names.get(a.person_id) if a.plan_status in visible_statuses else None,
                        "position_index": a.position_index,
                        "plan_status": a.plan_status.value,
                        "execution_status": a.execution_status.value,
                        "credited_minutes": a.credited_minutes,
                    }
                    for a in sorted(s.assignments, key=lambda x: x.position_index)
                ],
            }
            for s in slot_rows
        ],
    }


def set_lock(db: Session, assignment_id: uuid.UUID, locked: bool) -> DutySlot:
    a = db.get(Assignment, assignment_id)
    if a is None:
        raise HTTPException(status_code=404, detail="分配不存在")
    slot = db.get(DutySlot, a.duty_slot_id)
    if locked and a.person_id is None:
        raise HTTPException(status_code=422, detail="空缺岗位不能锁定")
    slot.is_locked = locked
    db.flush()
    return slot
