"""场地、班次模板、任务路由。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.venue import (
    ShiftTemplateIn,
    ShiftTemplateOut,
    TaskCreate,
    TaskOut,
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
def create_venue(payload: VenueCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> object:
    v = venue_service.create_venue(db, **payload.model_dump())
    db.commit()
    return v


@router.patch("/venues/{venue_id}", response_model=VenueOut)
def update_venue(venue_id: uuid.UUID, payload: VenueUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> object:
    v = venue_service.update_venue(db, venue_id, payload.model_dump(exclude_unset=True))
    db.commit()
    return v


@router.post("/venues/{venue_id}/disable", response_model=MessageOut)
def disable_venue(venue_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> MessageOut:
    venue_service.disable_venue(db, venue_id)
    db.commit()
    return MessageOut(message="场地已停用")


@router.get("/venues/{venue_id}/shift-templates", response_model=list[ShiftTemplateOut])
def get_shift_templates(venue_id: uuid.UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list:
    return venue_service.list_shift_templates(db, venue_id)


@router.put("/venues/{venue_id}/shift-templates", response_model=list[ShiftTemplateOut])
def put_shift_templates(
    venue_id: uuid.UUID,
    templates: list[ShiftTemplateIn],
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    result = venue_service.replace_shift_templates(db, venue_id, [t.model_dump() for t in templates])
    db.commit()
    return result


# --- 任务 ---
@router.get("/venue-tasks/{task_id}", response_model=TaskOut)
def get_task(task_id: uuid.UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)) -> object:
    return task_service.get_task(db, task_id)


@router.post("/venue-tasks", response_model=TaskOut, status_code=201)
def create_task(payload: TaskCreate, actor: User = Depends(require_admin), db: Session = Depends(get_db)) -> object:
    task = task_service.create_task(db, created_by=actor.id, **payload.model_dump())
    db.commit()
    return task


@router.patch("/venue-tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: uuid.UUID, payload: TaskUpdate, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> object:
    data = payload.model_dump(exclude_unset=True)
    expected = data.pop("expected_version", None)
    task = task_service.update_task(db, task_id, data, expected_version=expected)
    db.commit()
    return task


@router.post("/venue-tasks/{task_id}/cancel", response_model=MessageOut)
def cancel_task(task_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> MessageOut:
    task_service.cancel_task(db, task_id)
    db.commit()
    return MessageOut(message="任务已取消")


@router.get("/venue-tasks/{task_id}/hours-preview")
def task_hours_preview(task_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    task = task_service.get_task(db, task_id)
    return task_service.preview_task_hours(db, task)
