"""场地、班次模板、任务路由。"""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.enums import TaskStatus
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.venue import (
    ShiftTemplateIn,
    ShiftTemplateOut,
    TaskCreate,
    TaskListItem,
    TaskOut,
    TaskTransitionIn,
    TaskUpdate,
    VenueCreate,
    VenueOut,
    VenueUpdate,
)
from app.services import task_service, venue_service

router = APIRouter(tags=["venues"])


@router.get("/venues", response_model=list[VenueOut])
def list_venues(_: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list:
    return venue_service.list_venues(db)


@router.post("/venues", response_model=VenueOut, status_code=201)
def create_venue(
    payload: VenueCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> object:
    v = venue_service.create_venue(db, **payload.model_dump())
    db.commit()
    return v


@router.patch("/venues/{venue_id}", response_model=VenueOut)
def update_venue(
    venue_id: uuid.UUID,
    payload: VenueUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    v = venue_service.update_venue(db, venue_id, payload.model_dump(exclude_unset=True))
    db.commit()
    return v


@router.post("/venues/{venue_id}/disable", response_model=MessageOut)
def disable_venue(
    venue_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    venue_service.disable_venue(db, venue_id)
    db.commit()
    return MessageOut(message="场地已停用")


@router.get("/venues/{venue_id}/shift-templates", response_model=list[ShiftTemplateOut])
def get_shift_templates(
    venue_id: uuid.UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list:
    return venue_service.list_shift_templates(db, venue_id)


@router.put("/venues/{venue_id}/shift-templates", response_model=list[ShiftTemplateOut])
def put_shift_templates(
    venue_id: uuid.UUID,
    templates: list[ShiftTemplateIn],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    result = venue_service.replace_shift_templates(
        db, venue_id, [t.model_dump() for t in templates]
    )
    db.commit()
    return result


# --- 任务 ---
@router.get("/venue-tasks", response_model=list[TaskListItem])
def list_tasks(
    venue_id: uuid.UUID | None = Query(None),
    status: TaskStatus | None = Query(None),
    from_date: datetime | None = Query(None, alias="from"),
    to_date: datetime | None = Query(None, alias="to"),
    include_cancelled: bool = Query(False),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = task_service.list_tasks(
        db,
        venue_id=venue_id,
        status=status,
        from_date=from_date,
        to_date=to_date,
        include_hidden=include_cancelled,
    )
    return [
        {
            "id": str(t.id),
            "venue_id": str(t.venue_id),
            "venue_name": v.name,
            "title": t.title,
            "booking_start_at": t.booking_start_at,
            "booking_end_at": t.booking_end_at,
            "prep_minutes": t.prep_minutes,
            "cleanup_minutes": t.cleanup_minutes,
            "duty_start_at": t.duty_start_at,
            "duty_end_at": t.duty_end_at,
            "required_people": t.required_people,
            "is_temporary": t.is_temporary,
            "status": t.status,
            "version": t.version,
            "organization": t.organization,
            "contact_name": t.contact_name,
            "contact_phone": t.contact_phone,
        }
        for t, v in rows
    ]


@router.get("/venue-tasks/{task_id}", response_model=TaskOut)
def get_task(
    task_id: uuid.UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> object:
    return task_service.get_task(db, task_id)


@router.post("/venue-tasks", response_model=TaskOut, status_code=201)
def create_task(
    payload: TaskCreate, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> object:
    task = task_service.create_task(db, created_by=actor.id, **payload.model_dump())
    db.commit()
    return task


@router.patch("/venue-tasks/{task_id}", response_model=TaskOut)
def update_task(
    task_id: uuid.UUID,
    payload: TaskUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_version", None)
    task = task_service.update_task(db, task_id, data, expected_version=expected)
    db.commit()
    return task


@router.post("/venue-tasks/{task_id}/cancel", response_model=MessageOut)
def cancel_task(
    task_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    task_service.cancel_task(db, task_id)
    db.commit()
    return MessageOut(message="任务已取消")


@router.post("/venue-tasks/{task_id}/transition", response_model=TaskOut)
def transition_task(
    task_id: uuid.UUID,
    payload: TaskTransitionIn,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> object:
    """按状态机转换任务状态（draft→confirmed→scheduled→executing→completed）。"""
    from app.models.enums import TaskStatus

    try:
        target = TaskStatus(payload.target_status)
    except ValueError as exc:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=422, detail=f"未知任务状态：{payload.target_status}"
        ) from exc
    task = task_service.transition_task(db, task_id, target)
    db.commit()
    return task


@router.post("/venue-tasks/{task_id}/add-to-plan", response_model=MessageOut)
def add_task_to_plan(
    task_id: uuid.UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    """把已确认任务增量追加到其所在周的周计划（创建 DutySlot + 空缺岗位）。"""
    from app.services import schedule_service

    schedule_service.add_task_to_plan(db, task_id, actor_id=actor.id)
    db.commit()
    return MessageOut(message="任务已加入周排班（请到排班页拖拽分配人员）")


@router.get("/venue-tasks/{task_id}/hours-preview")
def task_hours_preview(
    task_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> dict:
    task = task_service.get_task(db, task_id)
    return task_service.preview_task_hours(db, task)
