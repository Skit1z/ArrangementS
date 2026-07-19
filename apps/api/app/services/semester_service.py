"""学期与课程时间 / 教学楼映射（方案 4.1 / 4.2）。"""
from __future__ import annotations

import uuid
from datetime import date, time

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.enums import BuildingType
from app.models.semester import BuildingCodeRule, CoursePeriodRule, Semester

# 方案 4.2 默认课程节次时间
DEFAULT_PERIODS: list[tuple[str, BuildingType, time, time]] = [
    ("1-2", BuildingType.all, time(8, 0), time(9, 50)),
    ("3-4", BuildingType.main, time(10, 5), time(11, 55)),
    ("3-4", BuildingType.second, time(10, 20), time(12, 10)),
    ("5-6", BuildingType.all, time(14, 0), time(15, 50)),
    ("7-8", BuildingType.all, time(16, 5), time(17, 55)),
    ("9-10", BuildingType.all, time(19, 0), time(20, 50)),
]
# 方案 4.2 默认教学楼代码前缀
DEFAULT_BUILDING_PREFIXES: list[tuple[str, BuildingType, int]] = [
    ("B", BuildingType.main, 10),
    ("02-", BuildingType.second, 10),
]


def create_semester(
    db: Session,
    *,
    name: str,
    first_monday: date,
    week_count: int = 20,
    is_current: bool = False,
    course_buffer_enabled: bool = False,
    course_buffer_minutes: int = 10,
) -> Semester:
    if not (1 <= week_count <= 30):
        raise HTTPException(status_code=422, detail="周数须在 1-30 之间")
    sem = Semester(
        name=name,
        first_monday=first_monday,
        week_count=week_count,
        is_current=is_current,
        course_buffer_enabled=course_buffer_enabled,
        course_buffer_minutes=course_buffer_minutes,
    )
    for group, building, start, end in DEFAULT_PERIODS:
        sem.period_rules.append(
            CoursePeriodRule(
                period_group=group,
                building_type=building,
                start_time=start,
                end_time=end,
                is_active=True,
            )
        )
    for prefix, building, priority in DEFAULT_BUILDING_PREFIXES:
        sem.building_rules.append(
            BuildingCodeRule(
                prefix=prefix, building_type=building, priority=priority, is_active=True
            )
        )
    db.add(sem)
    db.flush()
    if is_current:
        _make_current(db, sem.id)
    return sem


def _make_current(db: Session, semester_id: uuid.UUID) -> None:
    db.execute(update(Semester).values(is_current=False))
    db.execute(update(Semester).where(Semester.id == semester_id).values(is_current=True))
    db.flush()


def activate_semester(db: Session, semester_id: uuid.UUID) -> Semester:
    sem = db.get(Semester, semester_id)
    if sem is None:
        raise HTTPException(status_code=404, detail="学期不存在")
    _make_current(db, semester_id)
    db.refresh(sem)
    return sem


def update_semester(db: Session, semester_id: uuid.UUID, patch: dict) -> Semester:
    """更新学期配置（name/first_monday/week_count/course_buffer_*）。is_current 走 activate。"""
    sem = db.get(Semester, semester_id)
    if sem is None:
        raise HTTPException(status_code=404, detail="学期不存在")
    if "week_count" in patch and patch["week_count"] is not None:
        wc = patch["week_count"]
        if not (1 <= wc <= 30):
            raise HTTPException(status_code=422, detail="周数须在 1-30 之间")
    for k in ("name", "first_monday", "week_count", "course_buffer_enabled", "course_buffer_minutes"):
        if k in patch and patch[k] is not None:
            setattr(sem, k, patch[k])
    db.flush()
    return sem


def get_current_semester(db: Session) -> Semester | None:
    from datetime import date, timedelta
    today = date.today()
    all_semesters = db.scalars(select(Semester).order_by(Semester.first_monday.asc())).all()
    if not all_semesters:
        return None
    
    active_sem = None
    for sem in all_semesters:
        start_date = sem.first_monday
        end_date = start_date + timedelta(weeks=sem.week_count)
        if start_date <= today < end_date:
            active_sem = sem
            break
            
    if not active_sem:
        active_sem = min(
            all_semesters,
            key=lambda s: abs((s.first_monday - today).days)
        )
        
    if not active_sem.is_current:
        for sem in all_semesters:
            sem.is_current = (sem.id == active_sem.id)
        db.flush()
        
    return active_sem


def resolve_building_type(db: Session, semester_id: uuid.UUID, location_code: str) -> BuildingType | None:
    """按前缀优先级匹配教学楼类型；未识别返回 None（交人工确认）。"""
    code = (location_code or "").strip().upper()
    rules = db.scalars(
        select(BuildingCodeRule)
        .where(BuildingCodeRule.semester_id == semester_id, BuildingCodeRule.is_active.is_(True))
        .order_by(BuildingCodeRule.priority.desc())
    )
    for rule in rules:
        if code.startswith(rule.prefix.upper()):
            return rule.building_type
    return None
