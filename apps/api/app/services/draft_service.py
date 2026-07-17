"""拖拽草稿编辑：批量原子保存、冲突校验、候选人查询（方案 9.5 / 13.6）。

红线：
- 时间重叠永远禁止，即使 admin 选择强制安排也不得保存。
- 其他强制约束（课程/不可值班/场地/暂停/假期白名单）可强制越过，但必须填写原因并写审计。
- 前端预校验不能替代服务端校验；本模块为最终判定方。
- 保存采用乐观锁，防止覆盖其他 admin 的修改。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import (
    AssignmentSource,
    ExecutionStatus,
    PersonStatus,
    PlanAssignmentStatus,
    PlanStatus,
    SlotStatus,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.scheduling import eligibility
from app.services import multiplier_service
from app.services.audit_service import record_audit
from app.services.schedule_service import _assignment_hours, get_plan

OP_ASSIGN = "assign"
OP_UNASSIGN = "unassign"


@dataclass
class Conflict:
    slot_id: str
    position_index: int
    person_id: str | None
    kind: str  # time_overlap / hard_constraint / vacancy
    message: str


def _slot_of(db: Session, plan: WeeklyPlan, slot_id: uuid.UUID) -> DutySlot:
    slot = db.get(DutySlot, slot_id)
    if slot is None or slot.weekly_plan_id != plan.id:
        raise HTTPException(status_code=404, detail="岗位不存在于该周计划")
    return slot


def _assignment_at(db: Session, slot: DutySlot, position_index: int) -> Assignment | None:
    return db.scalar(
        select(Assignment).where(
            Assignment.duty_slot_id == slot.id, Assignment.position_index == position_index
        )
    )


def apply_operations(
    db: Session,
    *,
    week_start: date,
    expected_version: int,
    operations: list[dict],
    actor_id: uuid.UUID | None,
) -> WeeklyPlan:
    """原子应用一批拖拽操作。任一操作非法则整体拒绝。"""
    plan = get_plan(db, week_start)
    if plan.version != expected_version:
        raise HTTPException(status_code=409, detail="本周计划已被他人修改，请刷新后重试")

    engine_rules = multiplier_service.load_engine_rules(db)

    for op in operations:
        kind = op.get("op")
        if kind == OP_UNASSIGN:
            _do_unassign(db, plan, op)
        elif kind == OP_ASSIGN:
            _do_assign(db, plan, op, actor_id, engine_rules)
        else:
            raise HTTPException(status_code=422, detail=f"未知操作：{kind}")

    _refresh_slot_statuses(db, plan)
    plan.version += 1
    if plan.status == PlanStatus.published:
        plan.revision += 1  # 已发布计划的修改需要提升修订号
    db.flush()
    return plan


def _do_unassign(db: Session, plan: WeeklyPlan, op: dict) -> None:
    slot = _slot_of(db, plan, uuid.UUID(op["slot_id"]))
    a = _assignment_at(db, slot, int(op["position_index"]))
    if a is None:
        return
    a.person_id = None
    a.plan_status = PlanAssignmentStatus.vacant
    a.execution_status = ExecutionStatus.pending
    a.raw_minutes = 0
    a.weighted_minutes_before_round = Decimal(0)
    a.credited_minutes = 0
    a.balance_minutes = 0
    a.version += 1
    db.flush()


def _do_assign(db: Session, plan: WeeklyPlan, op: dict, actor_id: uuid.UUID | None, engine_rules) -> None:
    slot = _slot_of(db, plan, uuid.UUID(op["slot_id"]))
    position_index = int(op["position_index"])
    person_id = uuid.UUID(op["person_id"])
    forced = bool(op.get("forced", False))
    forced_reason = (op.get("forced_reason") or "").strip()

    person = db.get(PersonProfile, person_id)
    if person is None or person.status != PersonStatus.active:
        raise HTTPException(status_code=422, detail="人员不存在或已停用")

    existing = _assignment_at(db, slot, position_index)
    exclude_id = existing.id if existing else None

    # 同一人不得占据同一岗位的两个位置
    dup = db.scalar(
        select(Assignment).where(
            Assignment.duty_slot_id == slot.id,
            Assignment.person_id == person_id,
            Assignment.position_index != position_index,
        )
    )
    if dup is not None:
        raise HTTPException(status_code=422, detail=f"{person.full_name} 已在该班次的其他位置")

    # 红线：时间重叠绝对禁止，强制安排也不例外
    if eligibility.has_time_overlap_with_person(db, person_id, slot, exclude_assignment_id=exclude_id):
        raise HTTPException(
            status_code=422,
            detail=f"{person.full_name} 在该时间已有排班，时间重叠禁止安排（强制安排亦不可）",
        )

    # 其他强制约束：可强制越过，但必须填原因
    if not eligibility.check_person_available_for_slot(db, person, slot):
        if not forced:
            raise HTTPException(
                status_code=422,
                detail=f"{person.full_name} 存在课程/不可值班/场地等强制约束冲突，如需安排请选择强制安排并填写原因",
            )
        if not forced_reason:
            raise HTTPException(status_code=422, detail="强制安排必须填写原因")

    raw, weighted, credited = _assignment_hours(slot, engine_rules)
    source = AssignmentSource.forced if forced else AssignmentSource.manual

    if existing is None:
        existing = Assignment(
            duty_slot_id=slot.id, position_index=position_index, created_by=actor_id
        )
        db.add(existing)
    existing.person_id = person_id
    existing.assignment_source = source
    existing.plan_status = PlanAssignmentStatus.assigned
    existing.execution_status = ExecutionStatus.pending
    existing.raw_minutes = raw
    existing.weighted_minutes_before_round = weighted
    existing.credited_minutes = credited
    existing.balance_minutes = credited
    existing.forced_reason = forced_reason or None
    existing.version += 1
    db.flush()

    if forced:
        record_audit(
            db, actor_user_id=actor_id, action="assignment.force",
            entity_type="assignment", entity_id=existing.id, reason=forced_reason,
            after_data={"person_id": str(person_id), "slot_id": str(slot.id)},
        )


def _refresh_slot_statuses(db: Session, plan: WeeklyPlan) -> None:
    for slot in db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id)):
        count = db.scalar(
            select(func.count())
            .select_from(Assignment)
            .where(Assignment.duty_slot_id == slot.id, Assignment.person_id.isnot(None))
        ) or 0
        slot.status = SlotStatus.filled if count >= slot.required_people else SlotStatus.open
    db.flush()


def validate_week(db: Session, week_start: date) -> list[Conflict]:
    """对当前草稿做整体冲突检查，供“冲突检查”按钮使用。"""
    plan = get_plan(db, week_start)
    conflicts: list[Conflict] = []
    for slot in db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id)):
        assigned = 0
        for a in db.scalars(select(Assignment).where(Assignment.duty_slot_id == slot.id)):
            if a.person_id is None:
                continue
            assigned += 1
            person = db.get(PersonProfile, a.person_id)
            if person is None:
                continue
            if eligibility.has_time_overlap_with_person(db, a.person_id, slot, exclude_assignment_id=a.id):
                conflicts.append(Conflict(str(slot.id), a.position_index, str(a.person_id), "time_overlap", f"{person.full_name} 时间重叠"))
            elif not eligibility.check_person_available_for_slot(db, person, slot) and a.assignment_source != AssignmentSource.forced:
                conflicts.append(Conflict(str(slot.id), a.position_index, str(a.person_id), "hard_constraint", f"{person.full_name} 违反强制约束"))
        if assigned < slot.required_people:
            conflicts.append(Conflict(str(slot.id), -1, None, "vacancy", f"缺 {slot.required_people - assigned} 人"))
    return conflicts


def list_candidates(db: Session, slot_id: uuid.UUID) -> list[dict]:
    """人员抽屉：返回每人对该岗位的可用性与当月工时，供拖拽前置提示。"""
    slot = db.get(DutySlot, slot_id)
    if slot is None:
        raise HTTPException(status_code=404, detail="岗位不存在")

    people = list(
        db.scalars(select(PersonProfile).where(PersonProfile.status == PersonStatus.active))
    )
    month_balance = _month_balance_map(db, slot.month_key)
    week_counts = _week_shift_counts(db, slot.weekly_plan_id)

    out: list[dict] = []
    for p in people:
        overlap = eligibility.has_time_overlap_with_person(db, p.id, slot)
        available = eligibility.check_person_available_for_slot(db, p, slot)
        reasons: list[str] = []
        if overlap:
            reasons.append("时间重叠")
        if not available:
            reasons.append("课程/不可值班/场地限制")
        if not p.is_in_scheduling_pool:
            reasons.append("未参与自动排班")
        out.append({
            "person_id": str(p.id),
            "full_name": p.full_name,
            "class_name": p.class_name,
            "student_no": p.student_no,
            "month_balance_minutes": month_balance.get(p.id, 0),
            "week_shift_count": week_counts.get(p.id, 0),
            "in_scheduling_pool": p.is_in_scheduling_pool,
            "time_overlap": overlap,
            "available": available and not overlap,
            "reasons": reasons,
        })
    out.sort(key=lambda x: (not x["available"], x["month_balance_minutes"]))
    return out


def week_people(db: Session, week_start: date) -> list[dict]:
    """人员抽屉数据：一次性返回全周每人的当月工时、本周班次数与不可用岗位集合。

    预加载区间/约束，逐格在内存中判定，避免 N×M 次数据库查询。
    时间重叠由前端依据棋盘状态实时推导（其数据前端已完整持有）。
    """
    plan = get_plan(db, week_start)
    slot_rows = list(db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id)))
    people = list(
        db.scalars(select(PersonProfile).where(PersonProfile.status == PersonStatus.active))
    )
    person_ids = [p.id for p in people]
    blocks = eligibility._blocks(db, person_ids)
    constraints = eligibility._hard_constraints(db, person_ids)
    vac_by_date = {
        d: eligibility._active_vacation(db, d)
        for d in {s.slot_start_at.date() for s in slot_rows}
    }

    month_keys = {s.month_key for s in slot_rows}
    balance: dict[uuid.UUID, int] = {}
    for mk in month_keys:
        for pid, minutes in _month_balance_map(db, mk).items():
            balance[pid] = balance.get(pid, 0) + minutes
    week_counts = _week_shift_counts(db, plan.id)

    out: list[dict] = []
    for p in people:
        pb = blocks.get(p.id, [])
        pc = constraints.get(p.id, [])
        unavailable = [
            str(s.id)
            for s in slot_rows
            if not eligibility._is_available(
                db, p, s, pb, pc, vac_by_date.get(s.slot_start_at.date())
            )
        ]
        out.append({
            "person_id": str(p.id),
            "full_name": p.full_name,
            "class_name": p.class_name,
            "student_no": p.student_no,
            "month_balance_minutes": balance.get(p.id, 0),
            "week_shift_count": week_counts.get(p.id, 0),
            "in_scheduling_pool": p.is_in_scheduling_pool,
            "unavailable_slot_ids": unavailable,
        })
    out.sort(key=lambda x: (x["month_balance_minutes"], x["full_name"]))
    return out


def _month_balance_map(db: Session, month_key: str) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(Assignment, DutySlot)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(DutySlot.month_key == month_key, Assignment.person_id.isnot(None))
    ).all()
    out: dict[uuid.UUID, int] = {}
    for a, _slot in rows:
        out[a.person_id] = out.get(a.person_id, 0) + a.balance_minutes
    return out


def _week_shift_counts(db: Session, plan_id: uuid.UUID) -> dict[uuid.UUID, int]:
    rows = db.execute(
        select(Assignment, DutySlot)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(DutySlot.weekly_plan_id == plan_id, Assignment.person_id.isnot(None))
    ).all()
    out: dict[uuid.UUID, int] = {}
    for a, _slot in rows:
        out[a.person_id] = out.get(a.person_id, 0) + 1
    return out
