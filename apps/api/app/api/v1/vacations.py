"""假期与假期可值班名单路由（admin）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.models.vacation import VacationPeriod
from app.schemas.auth import MessageOut
from app.schemas.vacation import (
    AvailabilityOut,
    SetAvailabilityRequest,
    VacationCreate,
    VacationOut,
    VacationUpdate,
)
from app.services import vacation_service

router = APIRouter(prefix="/admin/vacations", tags=["vacations"])


@router.get("", response_model=list[VacationOut])
def list_vacations(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[VacationPeriod]:
    res = vacation_service.sync_vacation_periods(db)
    db.commit()
    return res


@router.post("", response_model=VacationOut, status_code=201)
def create_vacation(
    payload: VacationCreate, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> VacationPeriod:
    vac = vacation_service.create_vacation(
        db,
        actor_id=actor.id,
        name=payload.name,
        start_date=payload.start_date,
        end_date=payload.end_date,
        semester_id=payload.semester_id,
        yellow_shift_template_ids=[str(i) for i in payload.yellow_shift_template_ids]
        if payload.yellow_shift_template_ids
        else None,
        required_people=payload.required_people,
    )
    db.commit()
    db.refresh(vac)
    return vac


@router.patch("/{vacation_id}", response_model=VacationOut)
def update_vacation(
    vacation_id: uuid.UUID,
    payload: VacationUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> VacationPeriod:
    patch_data = payload.model_dump(exclude_unset=True)
    if "yellow_shift_template_ids" in patch_data and patch_data["yellow_shift_template_ids"] is not None:
        patch_data["yellow_shift_template_ids"] = [str(i) for i in patch_data["yellow_shift_template_ids"]]
    vac = vacation_service.update_vacation(db, vacation_id, patch_data)
    db.commit()
    db.refresh(vac)
    return vac


@router.post("/{vacation_id}/disable", response_model=MessageOut)
def disable_vacation(
    vacation_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    vac = vacation_service.get_vacation(db, vacation_id)
    vac.is_active = False
    db.commit()
    return MessageOut(message="假期已停用")


@router.get("/{vacation_id}/availabilities", response_model=list[AvailabilityOut])
def list_availabilities(
    vacation_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list:
    return vacation_service.list_availabilities(db, vacation_id)


@router.put("/{vacation_id}/availabilities", response_model=list[AvailabilityOut])
def set_availabilities(
    vacation_id: uuid.UUID,
    payload: SetAvailabilityRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list:
    result = vacation_service.set_availabilities(
        db,
        actor_id=actor.id,
        vacation_id=vacation_id,
        person_id=payload.person_id,
        intervals=[(iv.start_at, iv.end_at) for iv in payload.intervals],
    )
    db.commit()
    return result
