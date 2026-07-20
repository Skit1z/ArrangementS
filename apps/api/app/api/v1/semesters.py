"""学期与课程时间 / 教学楼映射路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.semester import BuildingCodeRule, CoursePeriodRule, Semester
from app.models.user import User
from app.schemas.semester import (
    BuildingRuleOut,
    PeriodRuleOut,
    SemesterCreate,
    SemesterOut,
    SemesterUpdate,
)
from app.services import semester_service

router = APIRouter(prefix="/semesters", tags=["semesters"])


@router.get("", response_model=list[SemesterOut])
def list_semesters(
    _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Semester]:
    semester_service.get_current_semester(db)
    db.commit()
    return list(db.scalars(select(Semester).order_by(Semester.first_monday.desc())))


@router.post("", response_model=SemesterOut, status_code=201)
def create_semester(
    payload: SemesterCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> Semester:
    sem = semester_service.create_semester(
        db,
        name=payload.name,
        first_monday=payload.first_monday,
        week_count=payload.week_count,
        is_current=payload.is_current,
        course_buffer_enabled=payload.course_buffer_enabled,
        course_buffer_minutes=payload.course_buffer_minutes,
    )
    db.commit()
    db.refresh(sem)
    return sem


@router.post("/{semester_id}/activate", response_model=SemesterOut)
def activate_semester(
    semester_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> Semester:
    sem = semester_service.activate_semester(db, semester_id)
    db.commit()
    return sem


@router.patch("/{semester_id}", response_model=SemesterOut)
def update_semester(
    semester_id: uuid.UUID,
    payload: SemesterUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> Semester:
    sem = semester_service.update_semester(db, semester_id, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(sem)
    return sem


@router.get("/{semester_id}/period-rules", response_model=list[PeriodRuleOut])
def period_rules(
    semester_id: uuid.UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[CoursePeriodRule]:
    return list(
        db.scalars(select(CoursePeriodRule).where(CoursePeriodRule.semester_id == semester_id))
    )


@router.get("/{semester_id}/building-rules", response_model=list[BuildingRuleOut])
def building_rules(
    semester_id: uuid.UUID, _: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[BuildingCodeRule]:
    return list(
        db.scalars(select(BuildingCodeRule).where(BuildingCodeRule.semester_id == semester_id))
    )
