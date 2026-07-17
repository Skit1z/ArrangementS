"""人员管理路由（均为 admin 权限）。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import require_admin
from app.db.session import get_db
from app.models.enums import PersonStatus
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.people import (
    ConstraintCreate,
    ConstraintOut,
    CreatedAccountOut,
    ImportConfirmOut,
    ImportPreviewOut,
    ImportPreviewRow,
    PersonOut,
    SchedulingPoolRequest,
    SensitiveOut,
)
from app.services import people_import, people_service

router = APIRouter(prefix="/people", tags=["people"])


@router.get("", response_model=list[PersonOut])
def list_people(
    class_name: str | None = Query(None),
    keyword: str | None = Query(None),
    status: PersonStatus | None = Query(None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[PersonOut]:
    people = people_service.list_people(
        db, class_name=class_name, keyword=keyword, status_filter=status
    )
    return [PersonOut.from_profile(p) for p in people]


@router.get("/{person_id}", response_model=PersonOut)
def get_person(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> PersonOut:
    return PersonOut.from_profile(people_service.get_person(db, person_id))


@router.post("/import/preview", response_model=ImportPreviewOut)
async def import_preview(
    file: UploadFile = File(...),
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ImportPreviewOut:
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        from fastapi import HTTPException

        raise HTTPException(status_code=413, detail="文件过大")
    batch = people_import.create_preview(db, file.filename or "import.xlsx", content, actor.id)
    db.commit()
    payload = batch.preview_payload or {}
    return ImportPreviewOut(
        batch_id=batch.id,
        total_rows=batch.total_rows,
        new_rows=batch.new_rows,
        updated_rows=batch.updated_rows,
        error_rows=batch.error_rows,
        rows=[ImportPreviewRow(**{k: r[k] for k in ImportPreviewRow.model_fields}) for r in payload.get("rows", [])],
    )


@router.post("/import/{batch_id}/confirm", response_model=ImportConfirmOut)
def import_confirm(
    batch_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> ImportConfirmOut:
    created = people_import.confirm_import(db, batch_id)
    db.commit()
    return ImportConfirmOut(
        created_count=len(created),
        accounts=[CreatedAccountOut(**c.__dict__) for c in created],
    )


@router.put("/scheduling-pool", response_model=MessageOut)
def update_scheduling_pool(
    payload: SchedulingPoolRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    n = people_service.set_scheduling_pool(db, actor.id, payload.person_ids, payload.enabled)
    db.commit()
    return MessageOut(message=f"已更新 {n} 人的自动排班参与状态")


@router.post("/{person_id}/suspend", response_model=PersonOut)
def suspend_person(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> PersonOut:
    prof = people_service.set_status(db, person_id, PersonStatus.suspended)
    db.commit()
    return PersonOut.from_profile(prof)


@router.post("/{person_id}/activate", response_model=PersonOut)
def activate_person(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> PersonOut:
    prof = people_service.set_status(db, person_id, PersonStatus.active)
    db.commit()
    return PersonOut.from_profile(prof)


@router.get("/{person_id}/sensitive", response_model=SensitiveOut)
def reveal_sensitive(
    person_id: uuid.UUID,
    request: Request,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> SensitiveOut:
    data = people_service.reveal_sensitive(
        db,
        actor.id,
        person_id,
        request.client.host if request.client else None,
        request.headers.get("user-agent"),
    )
    db.commit()
    return SensitiveOut(**data)


@router.get("/{person_id}/constraints", response_model=list[ConstraintOut])
def list_constraints(
    person_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[ConstraintOut]:
    return [ConstraintOut.model_validate(c) for c in people_service.list_constraints(db, person_id)]


@router.post("/{person_id}/constraints", response_model=ConstraintOut, status_code=201)
def add_constraint(
    person_id: uuid.UUID,
    payload: ConstraintCreate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ConstraintOut:
    c = people_service.add_constraint(
        db, actor.id, person_id, payload.constraint_type, payload.constraint_value, payload.is_hard
    )
    db.commit()
    return ConstraintOut.model_validate(c)


@router.delete("/{person_id}/constraints/{constraint_id}", response_model=MessageOut)
def delete_constraint(
    person_id: uuid.UUID,
    constraint_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    people_service.delete_constraint(db, person_id, constraint_id)
    db.commit()
    return MessageOut(message="约束已删除")
