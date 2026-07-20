"""假期与假期可值班白名单（方案 4.8）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.vacation import VacationAvailability, VacationPeriod
from app.services.intervals import merge_intervals

BEIJING_TZ = timezone(timedelta(hours=8))


def sync_vacation_periods(db: Session) -> list[VacationPeriod]:
    """根据已有学期的首周周一和周数，自动计算并同步学期之间的寒暑假区间。"""
    from app.models.semester import Semester

    semesters = list(db.scalars(select(Semester).order_by(Semester.first_monday.asc())))
    if not semesters:
        return list(db.scalars(select(VacationPeriod).order_by(VacationPeriod.start_date.desc())))

    for i in range(len(semesters)):
        sem_i = semesters[i]
        sem_i_end = sem_i.first_monday + timedelta(weeks=sem_i.week_count)
        if i + 1 < len(semesters):
            next_sem = semesters[i + 1]
            vac_start = sem_i_end
            vac_end = next_sem.first_monday - timedelta(days=1)
        else:
            vac_start = sem_i_end
            vac_end = sem_i_end + timedelta(weeks=8) - timedelta(days=1)

        if vac_start > vac_end:
            continue

        if vac_start.month in (5, 6, 7, 8, 9):
            default_name = f"{vac_start.year}年暑假"
        else:
            default_name = f"{vac_start.year}年寒假"

        existing = db.scalar(select(VacationPeriod).where(VacationPeriod.semester_id == sem_i.id))
        if existing:
            existing.start_date = vac_start
            existing.end_date = vac_end
            if (
                not existing.name
                or "寒假" in existing.name
                or "暑假" in existing.name
                or "假期" in existing.name
            ):
                existing.name = default_name
        else:
            vac = VacationPeriod(
                name=default_name,
                start_date=vac_start,
                end_date=vac_end,
                semester_id=sem_i.id,
                required_people=1,
                is_active=True,
            )
            db.add(vac)

    db.flush()
    return list(db.scalars(select(VacationPeriod).order_by(VacationPeriod.start_date.desc())))


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


def update_vacation(
    db: Session,
    vacation_id: uuid.UUID,
    patch: dict,
) -> VacationPeriod:
    """更新假期的排班规则（名称、保留班次、需求人数、启用状态）。"""
    vac = get_vacation(db, vacation_id)
    for k in ("name", "yellow_shift_template_ids", "required_people", "is_active"):
        if k in patch and patch[k] is not None:
            setattr(vac, k, patch[k])
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
    vacation = get_vacation(db, vacation_id)
    for start, end in intervals:
        if end <= start:
            raise HTTPException(status_code=422, detail="可值班时段的结束时间必须晚于开始时间")
        start_date = start.astimezone(BEIJING_TZ).date() if start.tzinfo else start.date()
        end_date = end.astimezone(BEIJING_TZ).date() if end.tzinfo else end.date()
        if start_date < vacation.start_date or end_date > vacation.end_date:
            raise HTTPException(status_code=422, detail="可值班时段必须完全位于该假期日期范围内")
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
