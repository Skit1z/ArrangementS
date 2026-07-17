"""假期与假期可值班白名单（方案 4.8）。"""
from __future__ import annotations

import uuid
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacation import VacationAvailability, VacationPeriod
from app.services.intervals import merge_intervals


def create_vacation(
    db: Session,
    *,
    actor_id: uuid.UUID,
    name: str,
    start_date: date,
    end_date: date,
    semester_id: uuid.UUID | None = None,
    yellow_shift_template_ids: list | None = None,
    required_people: int = 1,
) -> VacationPeriod:
    if end_date < start_date:
        raise HTTPException(status_code=422, detail="结束日期不得早于开始日期")
    vac = VacationPeriod(
        name=name,
        start_date=start_date,
        end_date=end_date,
        semester_id=semester_id,
        yellow_shift_template_ids=yellow_shift_template_ids,
        required_people=required_people,
        is_active=True,
        created_by=actor_id,
    )
    db.add(vac)
    db.flush()
    return vac


def get_vacation(db: Session, vacation_id: uuid.UUID) -> VacationPeriod:
    vac = db.get(VacationPeriod, vacation_id)
    if vac is None:
        raise HTTPException(status_code=404, detail="假期不存在")
    return vac


def set_availabilities(
    db: Session,
    *,
    actor_id: uuid.UUID,
    vacation_id: uuid.UUID,
    person_id: uuid.UUID,
    intervals: list[tuple[datetime, datetime]],
) -> list[VacationAvailability]:
    """整体覆盖某人在该假期的可值班时间段，保存时自动合并重叠区间。"""
    get_vacation(db, vacation_id)
    existing = db.scalars(
        select(VacationAvailability).where(
            VacationAvailability.vacation_period_id == vacation_id,
            VacationAvailability.person_id == person_id,
        )
    )
    for row in existing:
        db.delete(row)
    db.flush()

    merged = merge_intervals(intervals)
    created: list[VacationAvailability] = []
    for start, end in merged:
        av = VacationAvailability(
            vacation_period_id=vacation_id,
            person_id=person_id,
            start_at=start,
            end_at=end,
            created_by=actor_id,
        )
        db.add(av)
        created.append(av)
    db.flush()
    return created


def list_availabilities(db: Session, vacation_id: uuid.UUID) -> list[VacationAvailability]:
    return list(
        db.scalars(
            select(VacationAvailability)
            .where(VacationAvailability.vacation_period_id == vacation_id)
            .order_by(VacationAvailability.person_id, VacationAvailability.start_at)
        )
    )


def is_person_available(
    db: Session, vacation_id: uuid.UUID, person_id: uuid.UUID, start: datetime, end: datetime
) -> bool:
    """假期白名单语义：仅当 [start,end) 完整落在某登记区间内才可用。"""
    rows = db.scalars(
        select(VacationAvailability).where(
            VacationAvailability.vacation_period_id == vacation_id,
            VacationAvailability.person_id == person_id,
        )
    )
    for row in rows:
        if row.start_at <= start and end <= row.end_at:
            return True
    return False
