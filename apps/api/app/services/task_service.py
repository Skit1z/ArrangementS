"""蓝厅 / 图书馆报告厅临时任务（方案 2.3 / 7.2）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus, VenueType
from app.models.venue import Venue
from app.models.venue_task import VenueTask
from app.services import multiplier_service
from app.services.hours import compute_event_task_hours
from app.services.intervals import overlaps

# 视为“占用场地”的有效状态（用于同场地重叠判定）
ACTIVE_STATUSES = (
    TaskStatus.draft,
    TaskStatus.confirmed,
    TaskStatus.scheduled,
    TaskStatus.executing,
    TaskStatus.completed,
)


def _duty_window(booking_start: datetime, booking_end: datetime, prep: int, cleanup: int) -> tuple[datetime, datetime]:
    return booking_start - timedelta(minutes=prep), booking_end + timedelta(minutes=cleanup)


def _validate_and_check_overlap(
    db: Session,
    venue_id: uuid.UUID,
    duty_start: datetime,
    duty_end: datetime,
    booking_start: datetime,
    booking_end: datetime,
    prep: int,
    cleanup: int,
    required_people: int,
    exclude_task_id: uuid.UUID | None = None,
) -> None:
    if booking_end <= booking_start:
        raise HTTPException(status_code=422, detail="预约结束必须晚于预约开始")
    if prep < 0 or cleanup < 0:
        raise HTTPException(status_code=422, detail="提前到岗和收尾分钟数不能为负")
    if required_people < 1:
        raise HTTPException(status_code=422, detail="需求人数不少于 1")

    others = db.scalars(
        select(VenueTask).where(
            VenueTask.venue_id == venue_id,
            VenueTask.status.in_(ACTIVE_STATUSES),
        )
    )
    for other in others:
        if exclude_task_id is not None and other.id == exclude_task_id:
            continue
        if overlaps(duty_start, duty_end, other.duty_start_at, other.duty_end_at):
            raise HTTPException(
                status_code=409,
                detail=f"与同场地任务「{other.title}」完整值班时间重叠",
            )


def create_task(
    db: Session,
    *,
    venue_id: uuid.UUID,
    title: str,
    booking_start_at: datetime,
    booking_end_at: datetime,
    prep_minutes: int | None = None,
    cleanup_minutes: int | None = None,
    required_people: int | None = None,
    is_temporary: bool = False,
    created_by: uuid.UUID | None = None,
    **extra,
) -> VenueTask:
    venue = db.get(Venue, venue_id)
    if venue is None or not venue.is_active:
        raise HTTPException(status_code=404, detail="场地不存在或已停用")
    if venue.venue_type != VenueType.event_based:
        raise HTTPException(status_code=422, detail="仅蓝厅/报告厅类场地可创建任务")

    prep = venue.default_prep_minutes if prep_minutes is None else prep_minutes
    cleanup = venue.default_cleanup_minutes if cleanup_minutes is None else cleanup_minutes
    people = venue.default_required_people if required_people is None else required_people
    duty_start, duty_end = _duty_window(booking_start_at, booking_end_at, prep, cleanup)

    _validate_and_check_overlap(
        db, venue_id, duty_start, duty_end, booking_start_at, booking_end_at, prep, cleanup, people
    )

    task = VenueTask(
        venue_id=venue_id,
        title=title,
        booking_start_at=booking_start_at,
        booking_end_at=booking_end_at,
        prep_minutes=prep,
        cleanup_minutes=cleanup,
        duty_start_at=duty_start,
        duty_end_at=duty_end,
        required_people=people,
        is_temporary=is_temporary,
        status=TaskStatus.draft,
        created_by=created_by,
        version=1,
        **{k: v for k, v in extra.items() if v is not None},
    )
    db.add(task)
    db.flush()
    return task


def update_task(db: Session, task_id: uuid.UUID, patch: dict, expected_version: int | None = None) -> VenueTask:
    task = get_task(db, task_id)
    if task.status in (TaskStatus.completed, TaskStatus.cancelled):
        raise HTTPException(status_code=422, detail="已完成或已取消任务不得直接修改")
    if expected_version is not None and task.version != expected_version:
        raise HTTPException(status_code=409, detail="任务已被他人修改，请刷新后重试")

    for k in (
        "title", "organization", "contact_name", "contact_phone", "requirements", "notes",
        "is_temporary", "status",
    ):
        if k in patch and patch[k] is not None:
            setattr(task, k, patch[k])

    booking_start = patch.get("booking_start_at") or task.booking_start_at
    booking_end = patch.get("booking_end_at") or task.booking_end_at
    prep = patch.get("prep_minutes") if patch.get("prep_minutes") is not None else task.prep_minutes
    cleanup = patch.get("cleanup_minutes") if patch.get("cleanup_minutes") is not None else task.cleanup_minutes
    people = patch.get("required_people") if patch.get("required_people") is not None else task.required_people
    duty_start, duty_end = _duty_window(booking_start, booking_end, prep, cleanup)

    _validate_and_check_overlap(
        db, task.venue_id, duty_start, duty_end, booking_start, booking_end, prep, cleanup, people,
        exclude_task_id=task.id,
    )
    task.booking_start_at = booking_start
    task.booking_end_at = booking_end
    task.prep_minutes = prep
    task.cleanup_minutes = cleanup
    task.required_people = people
    task.duty_start_at = duty_start
    task.duty_end_at = duty_end
    task.version += 1
    db.flush()
    return task


def cancel_task(db: Session, task_id: uuid.UUID) -> VenueTask:
    task = get_task(db, task_id)
    task.status = TaskStatus.cancelled
    task.version += 1
    db.flush()
    return task


def get_task(db: Session, task_id: uuid.UUID) -> VenueTask:
    task = db.get(VenueTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


def preview_task_hours(db: Session, task: VenueTask) -> dict:
    """按完整值班时间与倍率规则预览单人工时。"""
    rules = multiplier_service.load_engine_rules(db)
    result = compute_event_task_hours(
        task.duty_start_at, task.duty_end_at, rules, venue_id=str(task.venue_id)
    )
    return {
        "raw_minutes": result.raw_minutes,
        "weighted_minutes_before_round": float(result.weighted_minutes_before_round),
        "credited_minutes": result.credited_minutes,
        "segments": [
            {
                "start_at": s.start_at.isoformat(),
                "end_at": s.end_at.isoformat(),
                "minutes": s.minutes,
                "multiplier": float(s.multiplier),
                "rule_name": s.rule_name,
            }
            for s in result.segments
        ],
    }
