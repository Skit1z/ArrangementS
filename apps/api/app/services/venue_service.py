"""场地与班次模板管理（方案 7.1）。删除采用逻辑停用，历史引用不物理删除。"""

from __future__ import annotations

import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import VenueType
from app.models.venue import ShiftTemplate, Venue


def list_venues(db: Session, include_inactive: bool = True) -> list[Venue]:
    stmt = select(Venue).order_by(Venue.sort_order, Venue.name)
    if not include_inactive:
        stmt = stmt.where(Venue.is_active.is_(True))
    return list(db.scalars(stmt))


def get_venue(db: Session, venue_id: uuid.UUID) -> Venue:
    v = db.get(Venue, venue_id)
    if v is None:
        raise HTTPException(status_code=404, detail="场地不存在")
    return v


def create_venue(db: Session, **fields) -> Venue:
    code = fields.get("code")
    if db.scalar(select(Venue).where(Venue.code == code)):
        raise HTTPException(status_code=409, detail="场地代码已存在")
    v = Venue(**fields)
    db.add(v)
    db.flush()
    return v


def update_venue(db: Session, venue_id: uuid.UUID, patch: dict) -> Venue:
    v = get_venue(db, venue_id)
    for k, val in patch.items():
        setattr(v, k, val)
    db.flush()
    return v


def disable_venue(db: Session, venue_id: uuid.UUID) -> Venue:
    v = get_venue(db, venue_id)
    v.is_active = False
    db.flush()
    return v


def replace_shift_templates(
    db: Session, venue_id: uuid.UUID, templates: list[dict]
) -> list[ShiftTemplate]:
    v = get_venue(db, venue_id)
    if v.venue_type != VenueType.fixed_shift:
        raise HTTPException(status_code=422, detail="仅固定班次场地可配置班次模板")
    existing = list(v.shift_templates)
    for t in existing:
        db.delete(t)
    db.flush()
    created: list[ShiftTemplate] = []
    for idx, t in enumerate(templates):
        st = ShiftTemplate(
            venue_id=venue_id,
            sort_order=t.get("sort_order", idx),
            **{
                k: t[k]
                for k in (
                    "name",
                    "start_time",
                    "end_time",
                    "credited_minutes",
                    "weekday_required_people",
                    "weekend_required_people",
                )
                if k in t
            },
        )
        st.is_active = t.get("is_active", True)
        db.add(st)
        created.append(st)
    db.flush()
    return created


def list_shift_templates(db: Session, venue_id: uuid.UUID) -> list[ShiftTemplate]:
    return list(
        db.scalars(
            select(ShiftTemplate)
            .where(ShiftTemplate.venue_id == venue_id)
            .order_by(ShiftTemplate.sort_order)
        )
    )
