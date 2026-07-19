"""临时/加班单条岗位的规范化创建（方案 P1.1 修复）。

为 ``overtime.py`` 的 approve 与 ``/admin/duty-slots/manual`` 提供统一的「走核心排班规则」
入口，避免直接 ``db.add(DutySlot/Assignment)`` 绕过：

- 课程冲突（AvailabilityBlock）经 ``eligibility.check_person_available_for_slot``
- 时间重叠（同人在重叠时段已排班）经 ``eligibility.has_time_overlap_with_person``
- 工时按 ``multiplier_service`` 倍率逐段计算 + 半小时向上取整
- 审计：``record_audit``

注意：本模块只覆盖「单岗位 + 单人员」的最小可复用单元，复杂的多岗位批量优化仍走
``schedule_service.generate`` + solver。
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    AssignmentSource,
    ExecutionStatus,
    PlanAssignmentStatus,
    SlotSourceType,
    SlotStatus,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.models.venue import Venue
from app.scheduling import eligibility
from app.scheduling.slots import BEIJING_TZ
from app.services import multiplier_service, schedule_service
from app.services.audit_service import record_audit


def _to_utc_aware(dt: datetime) -> datetime:
    """naive 视为北京时间（与 task_service/slots 一致），aware 原样返回。"""
    return dt.replace(tzinfo=BEIJING_TZ) if dt.tzinfo is None else dt


def assign_person_to_new_slot(
    db: Session,
    *,
    person_id: uuid.UUID,
    venue_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    source_type: SlotSourceType = SlotSourceType.manual,
    created_by: uuid.UUID | None = None,
    action: str = "manual.assign",
) -> tuple[DutySlot, Assignment]:
    """为单人在指定场地/时段创建一个已分配的岗位（加班 approve 路径）。

    全程走核心排班规则：
    1. 校验场地存在且启用
    2. 校验 person 在此时段无课程/不可值班/场地硬约束
    3. 校验 person 在此时段无时间重叠
    4. 倍率 + 半小时取整算工时
    5. 写 DutySlot + Assignment + 审计
    """
    start_at = _to_utc_aware(start_at)
    end_at = _to_utc_aware(end_at)
    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="结束时间必须晚于开始时间")

    venue = db.get(Venue, venue_id)
    if venue is None or not venue.is_active:
        raise HTTPException(status_code=404, detail="场地不存在或已停用")

    person = db.get(PersonProfile, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="人员不存在")
    from app.models.enums import PersonStatus
    if person.status != PersonStatus.active:
        raise HTTPException(status_code=422, detail="该人员当前非启用状态，不可排班")

    plan = _get_or_create_plan_for_date(db, start_at)

    # 占位 slot 供 eligibility 复用：先建一个临时 DutySlot 对象（不入库）
    probe = DutySlot(
        venue_id=venue_id,
        source_type=source_type,
        slot_start_at=start_at,
        slot_end_at=end_at,
        required_people=1,
    )

    # 1. 不可值班区间 / 课程冲突 / 场地硬约束 / 假期白名单
    if not eligibility.check_person_available_for_slot(db, person, probe):
        raise HTTPException(status_code=422, detail="该人员在此时段存在课程/不可值班/场地硬约束")
    # 2. 时间重叠
    if eligibility.has_time_overlap_with_person(db, person.id, probe):
        raise HTTPException(status_code=422, detail="该人员在此时段已有排班，时间重叠")

    # 3. 工时：倍率 + 半小时取整
    engine_rules = multiplier_service.load_engine_rules(db)
    raw, weighted, credited = schedule_service._assignment_hours(probe, engine_rules)

    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=venue_id,
        source_type=source_type,
        slot_start_at=start_at,
        slot_end_at=end_at,
        required_people=1,
        credited_minutes=credited,
        month_key=start_at.strftime("%Y-%m"),
        status=SlotStatus.filled,
    )
    db.add(slot)
    db.flush()

    assignment = Assignment(
        duty_slot_id=slot.id,
        person_id=person.id,
        position_index=0,
        assignment_source=AssignmentSource.manual,
        plan_status=PlanAssignmentStatus.assigned,
        execution_status=ExecutionStatus.pending,
        raw_minutes=raw,
        weighted_minutes_before_round=weighted,
        credited_minutes=credited,
        balance_minutes=credited,
        created_by=created_by,
    )
    db.add(assignment)
    db.flush()

    record_audit(
        db, actor_user_id=created_by, action=action,
        entity_type="assignment", entity_id=assignment.id,
        after_data={"slot_id": str(slot.id), "person_id": str(person.id),
                    "credited_minutes": credited, "raw_minutes": raw},
    )
    return slot, assignment


def create_vacant_slot(
    db: Session,
    *,
    venue_id: uuid.UUID,
    start_at: datetime,
    end_at: datetime,
    required_people: int,
    created_by: uuid.UUID | None = None,
) -> DutySlot:
    """创建一个空缺岗位（manual slot 路径）：所有 position 都是 vacant，不写工时。

    与旧 ``/admin/duty-slots/manual`` 行为一致的「空岗位」语义，但不再为空位
    填 ``balance_minutes``（避免污染月度统计的平衡分布）。
    """
    start_at = _to_utc_aware(start_at)
    end_at = _to_utc_aware(end_at)
    if end_at <= start_at:
        raise HTTPException(status_code=422, detail="结束时间必须晚于开始时间")
    if required_people < 1:
        raise HTTPException(status_code=422, detail="需求人数不少于 1")

    venue = db.get(Venue, venue_id)
    if venue is None or not venue.is_active:
        raise HTTPException(status_code=404, detail="场地不存在或已停用")

    plan = _get_or_create_plan_for_date(db, start_at)

    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=venue_id,
        source_type=SlotSourceType.manual,
        slot_start_at=start_at,
        slot_end_at=end_at,
        required_people=required_people,
        credited_minutes=0,  # 空岗无 credited；填岗后由 assign 时算
        month_key=start_at.strftime("%Y-%m"),
        status=SlotStatus.open,
    )
    db.add(slot)
    db.flush()

    for pidx in range(required_people):
        db.add(Assignment(
            duty_slot_id=slot.id, person_id=None, position_index=pidx,
            assignment_source=AssignmentSource.auto,
            plan_status=PlanAssignmentStatus.vacant,
            execution_status=ExecutionStatus.pending,
            raw_minutes=0, weighted_minutes_before_round=Decimal(0),
            credited_minutes=0, balance_minutes=0,  # 空岗 0，不污染统计
            created_by=created_by,
        ))

    db.flush()
    record_audit(
        db, actor_user_id=created_by, action="manual.vacant_slot",
        entity_type="duty_slot", entity_id=slot.id,
        after_data={"required_people": required_people},
    )
    return slot


def _get_or_create_plan_for_date(db: Session, target: datetime):
    """按 target 所在周找/建 WeeklyPlan（不主动发布）。"""
    local = target.astimezone(BEIJING_TZ) if target.tzinfo else target
    week_start = local.date() - timedelta(days=local.weekday())
    plan = db.scalar(select(WeeklyPlan).where(WeeklyPlan.week_start == week_start))
    if plan is not None:
        return plan
    plan = WeeklyPlan(
        week_start=week_start,
        week_end=week_start + timedelta(days=6),
        revision=1,
    )
    db.add(plan)
    db.flush()
    return plan
