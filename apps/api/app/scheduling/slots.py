"""周岗位生成：黄楼固定班次（含特殊日期/假期规则）+ 场地任务（方案 8.2 / 4.8）。"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import SlotSourceType, TaskStatus, VenueType
from app.models.schedule import DutySlot, WeeklyPlan
from app.models.special_date import SpecialDate
from app.models.vacation import VacationPeriod
from app.models.venue import ShiftTemplate, Venue
from app.models.venue_task import VenueTask
from app.services.day_rule_service import resolve_required_people

# 业务时间为北京时间；存入 timestamptz 列时必须带时区，否则 naive datetime 被
# Postgres 当 UTC，导致 API 返回 Z 后缀、前端按本地时区渲染时错 8 小时。
BEIJING_TZ = timezone(timedelta(hours=8))


def month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _active_vacation(db: Session, day: date) -> VacationPeriod | None:
    return db.scalar(
        select(VacationPeriod).where(
            VacationPeriod.is_active.is_(True),
            VacationPeriod.start_date <= day,
            VacationPeriod.end_date >= day,
        )
    )


def generate_slots(db: Session, plan: WeeklyPlan) -> list[DutySlot]:
    """为周计划生成岗位；与已保留的锁定岗位同源同时间的岗位不重复创建。"""
    generated: list[DutySlot] = []
    generated.extend(_generate_fixed_slots(db, plan))
    generated.extend(_generate_task_slots(db, plan))

    def identity(s: DutySlot) -> tuple:
        # SQLite 测试库会丢失 tzinfo；以墙上时间比较，避免同一锁定岗位被重复生成。
        return (
            s.venue_id,
            s.source_type,
            s.source_id,
            s.slot_start_at.replace(tzinfo=None),
            s.slot_end_at.replace(tzinfo=None),
        )

    existing_keys = {
        identity(s)
        for s in db.scalars(
            select(DutySlot).where(
                DutySlot.weekly_plan_id == plan.id,
                DutySlot.is_locked.is_(True),
            )
        )
    }
    slots = [s for s in generated if identity(s) not in existing_keys]
    for s in slots:
        db.add(s)
    db.flush()
    return slots


def _generate_fixed_slots(db: Session, plan: WeeklyPlan) -> list[DutySlot]:
    venues = list(
        db.scalars(
            select(Venue).where(
                Venue.venue_type == VenueType.fixed_shift, Venue.is_active.is_(True)
            )
        )
    )
    if not venues:
        return []

    result: list[DutySlot] = []
    for venue in venues:
        templates = list(
            db.scalars(
                select(ShiftTemplate)
                .where(ShiftTemplate.venue_id == venue.id, ShiftTemplate.is_active.is_(True))
                .order_by(ShiftTemplate.sort_order)
            )
        )
        for offset in range(7):
            day = plan.week_start + timedelta(days=offset)
            special = db.scalar(select(SpecialDate).where(SpecialDate.date == day))
            vacation = _active_vacation(db, day)
            day_templates, required_override = _templates_for_day(templates, vacation)
            for tpl in day_templates:
                required = (
                    required_override
                    if required_override is not None
                    else resolve_required_people(day, tpl, special)
                )
                if required <= 0:
                    continue
                result.append(
                    DutySlot(
                        weekly_plan_id=plan.id,
                        venue_id=venue.id,
                        source_type=SlotSourceType.fixed_shift,
                        source_id=tpl.id,
                        slot_start_at=datetime.combine(day, tpl.start_time, tzinfo=BEIJING_TZ),
                        slot_end_at=datetime.combine(day, tpl.end_time, tzinfo=BEIJING_TZ),
                        required_people=required,
                        credited_minutes=tpl.credited_minutes,
                        month_key=month_key(day),
                    )
                )
    return result


def _templates_for_day(
    templates: list[ShiftTemplate], vacation: VacationPeriod | None
) -> tuple[list[ShiftTemplate], int | None]:
    """假期：只保留配置的班次（默认第一个），每班人数取假期配置。"""
    if vacation is None:
        return templates, None
    keep_ids = set(vacation.yellow_shift_template_ids or [])
    if keep_ids:
        kept = [t for t in templates if str(t.id) in {str(i) for i in keep_ids}]
    else:
        kept = templates[:1]  # 默认保留第一个班次
    return kept, vacation.required_people


def _generate_task_slots(db: Session, plan: WeeklyPlan) -> list[DutySlot]:
    week_start_dt = datetime.combine(plan.week_start, time.min, tzinfo=BEIJING_TZ)
    week_end_dt = datetime.combine(plan.week_end + timedelta(days=1), time.min, tzinfo=BEIJING_TZ)
    # 仅已确认及之后状态的任务进入排班；草稿任务待 admin 确认后才占用岗位
    schedulable = (
        TaskStatus.confirmed,
        TaskStatus.scheduled,
        TaskStatus.executing,
        TaskStatus.completed,
    )
    tasks = db.scalars(
        select(VenueTask).where(
            VenueTask.duty_start_at >= week_start_dt,
            VenueTask.duty_start_at < week_end_dt,
            VenueTask.status.in_(schedulable),
        )
    )
    result: list[DutySlot] = []
    for task in tasks:
        result.append(
            DutySlot(
                weekly_plan_id=plan.id,
                venue_id=task.venue_id,
                source_type=SlotSourceType.venue_task,
                source_id=task.id,
                slot_start_at=task.duty_start_at,
                slot_end_at=task.duty_end_at,
                required_people=task.required_people,
                credited_minutes=0,  # 任务工时按倍率逐人计算，落到 assignment
                month_key=month_key(task.duty_start_at.date()),
            )
        )
    return result
