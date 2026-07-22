"""可用性矩阵与求解输入构建（方案 5 / 8.2 / 8.4）。

硬约束来源：审核通过的不可值班区间、暂停排班、禁止场地/星期/日期/时间、假期白名单、
每周最多班次、禁止同班搭档。偏好约束不参与可行性（仅影响目标，后续可扩展）。

P1.4 修复：所有约束都尊重 ``effective_start``/``effective_end`` —— 仅在区间内的约束
生效，区间外的约束对当前排班透明。
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.availability import AvailabilityBlock
from app.models.constraint import PersonConstraint
from app.models.enums import (
    AvailabilityStatus,
    PersonStatus,
    PlanAssignmentStatus,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot
from app.models.vacation import VacationPeriod
from app.scheduling.slots import BEIJING_TZ, _active_vacation
from app.scheduling.solver import Position, SolverInput
from app.services.intervals import overlaps
from app.services.vacation_service import is_person_available


def _is_constraint_in_effect(c: PersonConstraint, on_date: date) -> bool:
    """约束是否在指定日期生效（effective_start/end 闭合区间；None 表示无界）。"""
    if c.effective_start is not None and on_date < c.effective_start:
        return False
    if c.effective_end is not None and on_date > c.effective_end:
        return False
    return True


def _hard_constraints(
    db: Session, person_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[PersonConstraint]]:
    """加载硬约束（不按日期过滤——调用方在判定时按 slot 日期过滤 effective_*）。

    保留无日期过滤是为了保持原 API：``build_solver_input`` 和 ``check_person_available_for_slot``
    会通过 ``_is_constraint_in_effect`` 在评估时按 slot 日期过滤。这样既支持同一人配置多条
    不同有效期的约束，又不必在 SQL 层做复杂 join。
    """
    rows = db.scalars(
        select(PersonConstraint).where(
            PersonConstraint.person_id.in_(person_ids),
            PersonConstraint.is_active.is_(True),
            PersonConstraint.is_hard.is_(True),
        )
    )
    out: dict[uuid.UUID, list[PersonConstraint]] = {}
    for c in rows:
        out.setdefault(c.person_id, []).append(c)
    return out


def _blocks(db: Session, person_ids: list[uuid.UUID]) -> dict[uuid.UUID, list[tuple]]:
    rows = db.scalars(
        select(AvailabilityBlock).where(
            AvailabilityBlock.person_id.in_(person_ids),
            AvailabilityBlock.status == AvailabilityStatus.active,
        )
    )
    out: dict[uuid.UUID, list[tuple]] = {}
    for b in rows:
        out.setdefault(b.person_id, []).append((b.start_at, b.end_at))
    return out


def _violates_constraint(c: PersonConstraint, slot: DutySlot) -> bool:
    val = c.constraint_value or {}
    t = c.constraint_type
    if t == "suspend":
        return True
    if t == "forbid_venue":
        return str(slot.venue_id) in {str(v) for v in val.get("venue_ids", [])}
    if t == "only_venue":
        allowed = {str(v) for v in val.get("venue_ids", [])}
        return bool(allowed) and str(slot.venue_id) not in allowed
    if t == "forbid_weekday":
        return slot.slot_start_at.isoweekday() in val.get("weekdays", [])
    if t == "forbid_date":
        return slot.slot_start_at.date().isoformat() in val.get("dates", [])
    if t == "forbid_time":
        for r in val.get("ranges", []):
            rs = time.fromisoformat(r["start"])
            re = time.fromisoformat(r["end"])
            if slot.slot_start_at.time() < re and rs < slot.slot_end_at.time():
                return True
    return False


def _weekly_limit(
    constraints: list[PersonConstraint], on_dates: set[date] | None = None
) -> int | None:
    """Return the strictest applicable weekly limit.

    Multiple effective-dated rules may overlap.  Taking the minimum avoids making
    the result depend on database row order.
    """
    limits: list[int] = []
    for c in constraints:
        if c.constraint_type != "weekly_limit":
            continue
        if on_dates is not None and not any(_is_constraint_in_effect(c, day) for day in on_dates):
            continue
        value = (c.constraint_value or {}).get("limit")
        if isinstance(value, int) and value >= 0:
            limits.append(value)
    return min(limits) if limits else None


def _forbidden_pairs(
    constraints_by_person: dict[uuid.UUID, list[PersonConstraint]],
) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for pid, cs in constraints_by_person.items():
        for c in cs:
            if c.constraint_type == "no_pair_with":
                for other in (c.constraint_value or {}).get("person_ids", []):
                    pairs.append((str(pid), str(other)))
    return pairs


def build_solver_input(
    db: Session, plan, seed: int = 42, max_time_seconds: float | None = None
) -> SolverInput:
    slots = list(db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id)))

    people = list(
        db.scalars(
            select(PersonProfile).where(
                PersonProfile.status == PersonStatus.active,
                PersonProfile.is_in_scheduling_pool.is_(True),
            )
        )
    )
    person_ids = [p.id for p in people]
    blocks = _blocks(db, person_ids)
    constraints = _hard_constraints(db, person_ids)

    # 预取场地（用于 is_event_venue 判定）
    from app.models.venue import Venue

    venue_by_id = {str(v.id): v for v in db.scalars(select(Venue))}

    # 展开岗位并计算可用性
    positions: list[Position] = []
    available: dict[tuple[str, str], bool] = {}
    locked: dict[str, str] = {}

    # 预取锁定分配
    locked_rows = db.scalars(
        select(Assignment)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(
            DutySlot.weekly_plan_id == plan.id,
            DutySlot.is_locked.is_(True),
            Assignment.person_id.is_not(None),
        )
    )
    locked_by_slot_pos = {
        (str(a.duty_slot_id), a.position_index): str(a.person_id)
        for a in locked_rows
        if a.person_id is not None
    }

    for slot in slots:
        vacation = _active_vacation(db, slot.slot_start_at.date())
        # 预取场地类型（用于 is_event_venue 判定）
        slot_venue = venue_by_id.get(str(slot.venue_id))
        is_event = slot_venue is not None and slot_venue.venue_type.value == "event_based"
        # 是否周末（北京时间）：周六/周日
        if slot.slot_start_at.tzinfo is None:
            _local = slot.slot_start_at
        else:
            _local = slot.slot_start_at.astimezone(BEIJING_TZ)
        is_weekend = _local.weekday() >= 5  # 5=周六, 6=周日
        # 早班：12 点前开始；晚班：18 点后开始（二者皆 False 为中午）
        is_morning = _local.hour < 12
        for pidx in range(slot.required_people):
            pos_id = f"{slot.id}:{pidx}"
            positions.append(
                Position(
                    id=pos_id,
                    slot_id=str(slot.id),
                    month_key=slot.month_key,
                    credited_minutes=slot.credited_minutes,
                    venue_id=str(slot.venue_id),
                    start_at=slot.slot_start_at,
                    end_at=slot.slot_end_at,
                    is_weekend=is_weekend,
                    is_morning=is_morning,
                    is_event_venue=is_event,
                )
            )
            lk = locked_by_slot_pos.get((str(slot.id), pidx))
            if lk is not None:
                locked[pos_id] = lk
            for person in people:
                available[(str(person.id), pos_id)] = _is_available(
                    db,
                    person,
                    slot,
                    blocks.get(person.id, []),
                    constraints.get(person.id, []),
                    vacation,
                )

    slot_dates = {
        s.slot_start_at.date()
        if s.slot_start_at.tzinfo is None
        else s.slot_start_at.astimezone(BEIJING_TZ).date()
        for s in slots
    }
    weekly_limit = {str(p.id): _weekly_limit(constraints.get(p.id, []), slot_dates) for p in people}
    weekly_limit = {k: v for k, v in weekly_limit.items() if v is not None}

    history = _month_history(db, plan)

    return SolverInput(
        positions=positions,
        persons=[str(p.id) for p in people],
        available=available,
        weekly_limit=weekly_limit,
        forbidden_pairs=_forbidden_pairs(constraints),
        locked=locked,
        history_minutes=history,
        seed=seed,
        max_time_seconds=15.0 if max_time_seconds is None else max_time_seconds,
    )


def _is_available(
    db: Session,
    person: PersonProfile,
    slot: DutySlot,
    person_blocks: list[tuple],
    person_constraints: list[PersonConstraint],
    vacation: VacationPeriod | None,
) -> bool:
    # 不可值班区间
    for bs, be in person_blocks:
        if overlaps(slot.slot_start_at, slot.slot_end_at, bs, be):
            return False
    # 硬约束（按 slot 日期过滤有效期）
    if slot.slot_start_at.tzinfo is None:
        slot_date = slot.slot_start_at.date()
    else:
        slot_date = slot.slot_start_at.astimezone(BEIJING_TZ).date()
    for c in person_constraints:
        if not _is_constraint_in_effect(c, slot_date):
            continue
        if _violates_constraint(c, slot):
            return False
    # 假期白名单：假期内仅登记时间段可用。
    # 如果没有任何人登记该假期的可值班时段，则不做白名单过滤（避免误伤所有人）。
    if vacation is not None:
        from app.models.vacation import VacationAvailability

        any_registered = db.scalar(
            select(VacationAvailability)
            .where(
                VacationAvailability.vacation_period_id == vacation.id,
            )
            .limit(1)
        )
        if any_registered is not None:
            return is_person_available(
                db, vacation.id, person.id, slot.slot_start_at, slot.slot_end_at
            )
    return True


def check_person_available_for_slot(db: Session, person: PersonProfile, slot: DutySlot) -> bool:
    """换班/补位审核复用：单人对单岗位的硬可用性校验。"""
    person_blocks = _blocks(db, [person.id]).get(person.id, [])
    person_constraints = _hard_constraints(db, [person.id]).get(person.id, [])
    vacation = _active_vacation(db, slot.slot_start_at.date())
    return _is_available(db, person, slot, person_blocks, person_constraints, vacation)


def has_time_overlap_with_person(
    db: Session,
    person_id: uuid.UUID,
    slot: DutySlot,
    exclude_assignment_id: uuid.UUID | None = None,
) -> bool:
    """该人是否已有与目标岗位时间重叠的有效分配。"""
    from app.models.enums import PlanAssignmentStatus

    rows = db.execute(
        select(Assignment, DutySlot)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(
            Assignment.person_id == person_id,
            Assignment.plan_status.notin_(
                [
                    PlanAssignmentStatus.vacant,
                    PlanAssignmentStatus.cancelled,
                    PlanAssignmentStatus.replaced,
                ]
            ),
        )
    ).all()
    for a, other_slot in rows:
        if exclude_assignment_id is not None and a.id == exclude_assignment_id:
            continue
        if overlaps(
            slot.slot_start_at, slot.slot_end_at, other_slot.slot_start_at, other_slot.slot_end_at
        ):
            return True
    return False


def would_exceed_weekly_limit(
    db: Session,
    person_id: uuid.UUID,
    slot: DutySlot,
    exclude_assignment_id: uuid.UUID | None = None,
) -> bool:
    """Whether adding ``slot`` would exceed the person's effective weekly cap.

    The count is based on the slot's local Monday-Sunday week and includes all
    active assignments, not merely assignments in one WeeklyPlan.  This matters
    for manual/overtime slots and for data imported into a neighbouring plan.
    """
    local_start = (
        slot.slot_start_at
        if slot.slot_start_at.tzinfo is None
        else slot.slot_start_at.astimezone(BEIJING_TZ)
    )
    on_date = local_start.date()
    constraints = _hard_constraints(db, [person_id]).get(person_id, [])
    limit = _weekly_limit(constraints, {on_date})
    if limit is None:
        return False

    week_start = on_date - timedelta(days=on_date.weekday())
    week_end = week_start + timedelta(days=7)
    rows = db.execute(
        select(Assignment, DutySlot)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(
            Assignment.person_id == person_id,
            Assignment.plan_status.notin_(
                [
                    PlanAssignmentStatus.vacant,
                    PlanAssignmentStatus.cancelled,
                    PlanAssignmentStatus.replaced,
                ]
            ),
        )
    ).all()
    count = 0
    for assignment, other_slot in rows:
        if exclude_assignment_id is not None and assignment.id == exclude_assignment_id:
            continue
        other_start: datetime = other_slot.slot_start_at
        other_date = (
            other_start.date()
            if other_start.tzinfo is None
            else other_start.astimezone(BEIJING_TZ).date()
        )
        if week_start <= other_date < week_end:
            count += 1
    return count + 1 > limit


def violates_no_pair_with_existing(
    db: Session,
    person_id: uuid.UUID,
    slot: DutySlot,
    exclude_assignment_id: uuid.UUID | None = None,
) -> bool:
    """接替人若与同 slot 的其它已分配人员存在「禁止同班」关系，返回 True。

    双向检查：A 禁 B 或 B 禁 A 都视为违反。用于换班终审的补查。
    """
    from app.models.enums import PlanAssignmentStatus

    # 同 slot 其它人员
    other_person_ids = [
        pid
        for assignment_id, pid in db.execute(
            select(Assignment.id, Assignment.person_id).where(
                Assignment.duty_slot_id == slot.id,
                Assignment.person_id.is_not(None),
                Assignment.plan_status.notin_(
                    [
                        PlanAssignmentStatus.vacant,
                        PlanAssignmentStatus.cancelled,
                        PlanAssignmentStatus.replaced,
                    ]
                ),
            )
        )
        if pid is not None and assignment_id != exclude_assignment_id
    ]
    if not other_person_ids:
        return False
    other_set = {str(pid) for pid in other_person_ids}

    # 双方的 no_pair_with 约束（按 slot 日期过滤有效期）
    slot_date = (
        slot.slot_start_at.date()
        if slot.slot_start_at.tzinfo is None
        else slot.slot_start_at.astimezone(BEIJING_TZ).date()
    )
    all_ids = [person_id] + other_person_ids
    rows = db.scalars(
        select(PersonConstraint).where(
            PersonConstraint.person_id.in_(all_ids),
            PersonConstraint.is_active.is_(True),
            PersonConstraint.is_hard.is_(True),
            PersonConstraint.constraint_type == "no_pair_with",
        )
    )
    for c in rows:
        if not _is_constraint_in_effect(c, slot_date):
            continue
        forbidden = {str(pid) for pid in (c.constraint_value or {}).get("person_ids", [])}
        if not forbidden:
            continue
        # c.person_id 禁止与 forbidden 中的人搭档
        # 若 c.person_id 是接替人：检查 forbidden ∩ other_set
        # 若 c.person_id 是某个现有同班：检查 forbidden 是否含接替人
        if str(c.person_id) == str(person_id):
            if forbidden & other_set:
                return True
        else:
            if str(person_id) in forbidden:
                return True
    return False


def _month_history(db: Session, plan) -> dict[str, int]:
    """当月已存在分配的平衡工时（排除本周计划），用于公平性历史 H_p。"""
    month_keys = {
        s.month_key for s in db.scalars(select(DutySlot).where(DutySlot.weekly_plan_id == plan.id))
    }
    if not month_keys:
        return {}
    rows = db.scalars(
        select(Assignment)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(DutySlot.month_key.in_(month_keys), DutySlot.weekly_plan_id != plan.id)
    )
    out: dict[str, int] = {}
    for a in rows:
        if a.person_id is not None:
            out[str(a.person_id)] = out.get(str(a.person_id), 0) + a.balance_minutes
    return out
