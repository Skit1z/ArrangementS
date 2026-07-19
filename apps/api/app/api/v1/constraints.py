"""admin 管理个人排班约束（PersonConstraint CRUD）。

支持类型：suspend（暂停排班+起止）、forbid_venue、only_venue、forbid_weekday、
forbid_date、forbid_time、no_pair_with、weekly_limit。
所有类型都支持可选的 effective_start/end（按日期生效）。
"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.constraint import PersonConstraint
from app.models.user import User

router = APIRouter(prefix="/admin/people", tags=["admin-constraints"])

ALLOWED_TYPES = {
    "suspend", "forbid_venue", "only_venue", "forbid_weekday", "forbid_date",
    "forbid_time", "no_pair_with", "weekly_limit",
}


class ConstraintIn(BaseModel):
    constraint_type: str
    constraint_value: dict | None = None
    is_hard: bool = True
    effective_start: date | None = None
    effective_end: date | None = None
    is_active: bool = True


class ConstraintOut(BaseModel):
    id: uuid.UUID
    person_id: uuid.UUID
    constraint_type: str
    constraint_value: dict | None
    is_hard: bool
    effective_start: date | None
    effective_end: date | None
    is_active: bool

    model_config = {"from_attributes": True}


@router.get("/{person_id}/constraints", response_model=list[ConstraintOut])
def list_constraints(
    person_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ConstraintOut]:
    rows = db.scalars(
        select(PersonConstraint).where(PersonConstraint.person_id == person_id)
        .order_by(PersonConstraint.created_at.desc())
    )
    return [ConstraintOut.model_validate(r) for r in rows]


@router.post("/{person_id}/constraints", response_model=ConstraintOut)
def create_constraint(
    person_id: uuid.UUID,
    payload: ConstraintIn,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ConstraintOut:
    if payload.constraint_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"不支持的约束类型：{payload.constraint_type}，可选：{sorted(ALLOWED_TYPES)}",
        )
    if payload.effective_start and payload.effective_end and payload.effective_end < payload.effective_start:
        raise HTTPException(status_code=422, detail="effective_end 不得早于 effective_start")
    c = PersonConstraint(
        person_id=person_id,
        constraint_type=payload.constraint_type,
        constraint_value=payload.constraint_value,
        is_hard=payload.is_hard,
        effective_start=payload.effective_start,
        effective_end=payload.effective_end,
        is_active=payload.is_active,
        created_by=actor.id,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return ConstraintOut.model_validate(c)


@router.patch("/constraints/{constraint_id}", response_model=ConstraintOut)
def update_constraint(
    constraint_id: uuid.UUID,
    payload: dict,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ConstraintOut:
    c = db.get(PersonConstraint, constraint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="约束不存在")
    # 把日期字符串转 date（Pydantic 不参与 dict payload 的转换）
    for k in ("effective_start", "effective_end"):
        if k in payload and isinstance(payload[k], str):
            try:
                payload[k] = date.fromisoformat(payload[k])
            except ValueError as exc:
                raise HTTPException(status_code=422, detail=f"{k} 不是有效日期") from exc
    if (
        payload.get("effective_start")
        and payload.get("effective_end")
        and payload["effective_end"] < payload["effective_start"]
    ):
        raise HTTPException(status_code=422, detail="effective_end 不得早于 effective_start")
    for k in ("constraint_value", "is_hard", "effective_start", "effective_end", "is_active"):
        if k in payload:
            setattr(c, k, payload[k])
    db.commit()
    db.refresh(c)
    return ConstraintOut.model_validate(c)


@router.delete("/constraints/{constraint_id}", response_model=dict)
def delete_constraint(
    constraint_id: uuid.UUID,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    c = db.get(PersonConstraint, constraint_id)
    if c is None:
        raise HTTPException(status_code=404, detail="约束不存在")
    db.delete(c)
    db.commit()
    return {"ok": True}
