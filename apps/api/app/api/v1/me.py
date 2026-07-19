"""普通用户自助路由（不可值班申请、请假、换班）。"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.people import PeerOut
from app.schemas.timetable import MyTimetableEntryOut, MyTimetableOut
from app.schemas.workflow import (
    AvailabilityRequestIn,
    AvailabilityRequestOut,
    LeaveIn,
    LeaveOut,
    SwapOpenIn,
    SwapOut,
    SwapTargetedIn,
)
from app.services import (
    availability_service,
    leave_service,
    me_service,
    people_service,
    schedule_stats,
    swap_service,
)

router = APIRouter(prefix="/me", tags=["me"])


def _person_id(db: Session, user: User) -> uuid.UUID:
    return people_service.get_person_by_user(db, user.id).id


# --- 我的排班 / 工时 ---
@router.get("/schedule")
def my_schedule(
    start: date | None = None,
    end: date | None = None,
    u: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    return me_service.my_assignments(db, _person_id(db, u), start=start, end=end)


@router.get("/next-duty")
def my_next_duty(u: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    return {"next": me_service.next_duty(db, _person_id(db, u))}


@router.get("/hours")
def my_hours(month: str, u: User = Depends(get_current_user), db: Session = Depends(get_db)) -> dict:
    person_id = _person_id(db, u)
    try:
        s = schedule_stats.get_summary(db, month, person_id)
    except HTTPException:
        return {"month": month, "balance_minutes": 0, "completed_minutes": 0, "venues": [], "calculated": False}
    breakdown = schedule_stats.venue_breakdown(db, month, person_id)
    return {
        "month": month,
        "balance_minutes": s.balance_minutes,
        "completed_minutes": s.completed_minutes,
        "multiplier_extra_minutes": s.multiplier_extra_minutes,
        "leave_count": s.leave_count,
        "swap_out_count": s.swap_out_count,
        "absence_count": s.absence_count,
        "status": s.status.value,
        "calculated": True,
        "venues": [
            {"venue_id": str(v.venue_id), "venue_name": venue.name, "completed_minutes": v.completed_minutes}
            for v, venue in breakdown
        ],
    }


# --- 不可值班申请 ---
@router.post("/availability-requests", response_model=AvailabilityRequestOut, status_code=201)
def create_availability_request(payload: AvailabilityRequestIn, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = availability_service.create_request(
        db, person_id=_person_id(db, u), start_at=payload.start_at, end_at=payload.end_at,
        reason=payload.reason, recurrence_rule=payload.recurrence_rule,
    )
    db.commit()
    return req


@router.get("/availability-requests", response_model=list[AvailabilityRequestOut])
def my_availability_requests(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return availability_service.list_my(db, _person_id(db, u))


@router.post("/availability-requests/{request_id}/withdraw", response_model=AvailabilityRequestOut)
def withdraw_availability_request(request_id: uuid.UUID, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = availability_service.withdraw(db, _person_id(db, u), request_id)
    db.commit()
    return req


# --- 请假 ---
@router.post("/leave-requests", response_model=LeaveOut, status_code=201)
def create_leave(payload: LeaveIn, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    leave = leave_service.create_leave(
        db, applicant_person_id=_person_id(db, u), assignment_id=payload.assignment_id, reason=payload.reason,
    )
    db.commit()
    return leave


@router.get("/leave-requests", response_model=list[LeaveOut])
def my_leaves(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return leave_service.list_my_leaves(db, _person_id(db, u))


@router.post("/leave-requests/{leave_id}/withdraw", response_model=LeaveOut)
def withdraw_leave(leave_id: uuid.UUID, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    leave = leave_service.withdraw(db, _person_id(db, u), leave_id)
    db.commit()
    return leave


# --- 换班 ---
@router.post("/swap-requests/targeted", response_model=SwapOut, status_code=201)
def create_targeted_swap(payload: SwapTargetedIn, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    swap = swap_service.create_targeted(
        db, requester_person_id=_person_id(db, u), assignment_id=payload.assignment_id,
        target_person_id=payload.target_person_id, reason=payload.reason,
    )
    db.commit()
    return swap


@router.post("/swap-requests/open", response_model=SwapOut, status_code=201)
def create_open_swap(payload: SwapOpenIn, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    swap = swap_service.create_open(
        db, requester_person_id=_person_id(db, u), assignment_id=payload.assignment_id, reason=payload.reason,
    )
    db.commit()
    return swap


@router.get("/swap-requests", response_model=list[SwapOut])
def my_swaps(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return swap_service.list_my(db, _person_id(db, u))


@router.get("/swap-invitations", response_model=list[SwapOut])
def my_swap_invitations(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return swap_service.list_invitations(db, _person_id(db, u))


@router.post("/swap-requests/{swap_id}/accept", response_model=SwapOut)
def accept_swap(swap_id: uuid.UUID, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    swap = swap_service.respond_target(db, target_person_id=_person_id(db, u), swap_id=swap_id, accept=True)
    db.commit()
    return swap


@router.post("/swap-requests/{swap_id}/reject", response_model=SwapOut)
def reject_swap_invitation(swap_id: uuid.UUID, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    swap = swap_service.respond_target(db, target_person_id=_person_id(db, u), swap_id=swap_id, accept=False)
    db.commit()
    return swap


@router.post("/swap-requests/{swap_id}/apply", response_model=MessageOut)
def apply_open_swap(swap_id: uuid.UUID, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    swap_service.apply_open(db, candidate_person_id=_person_id(db, u), swap_id=swap_id)
    db.commit()
    return MessageOut(message="报名成功")


@router.post("/swap-requests/{swap_id}/withdraw", response_model=SwapOut)
def withdraw_swap(swap_id: uuid.UUID, u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    swap = swap_service.withdraw(db, requester_person_id=_person_id(db, u), swap_id=swap_id)
    db.commit()
    return swap


open_swaps_router = APIRouter(prefix="/swap-requests", tags=["me"])


@open_swaps_router.get("/open", response_model=list[SwapOut])
def list_open_swaps(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return swap_service.list_open(db)


@router.get("/peers", response_model=list[PeerOut])
def list_peers(u: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.models.person import PersonProfile
    from app.models.enums import PersonStatus
    from sqlalchemy import select
    my_id = _person_id(db, u)
    people = db.scalars(
        select(PersonProfile)
        .where(PersonProfile.id != my_id, PersonProfile.status == PersonStatus.active)
        .order_by(PersonProfile.full_name.asc())
    ).all()
    return [PeerOut(id=p.id, full_name=p.full_name, class_name=p.class_name) for p in people]


@router.get("/timetable", response_model=MyTimetableOut | None)
def get_my_timetable(
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MyTimetableOut | None:
    """返回当前用户本学期已生效的课表（approved 状态），无则返回 null。"""
    from app.models.enums import ReviewStatus
    from app.models.timetable import TimetableUpload
    from app.services import semester_service
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    prof = people_service.get_person_by_user(db, current.id)
    if prof is None:
        return None
    sem = semester_service.get_current_semester(db)
    if sem is None:
        return None

    stmt = (
        select(TimetableUpload)
        .where(
            TimetableUpload.person_id == prof.id,
            TimetableUpload.semester_id == sem.id,
            TimetableUpload.review_status == ReviewStatus.approved,
        )
        .options(selectinload(TimetableUpload.course_rules))
        .order_by(TimetableUpload.confirmed_at.desc().nulls_last())
        .limit(1)
    )
    up = db.scalars(stmt).first()
    if up is None:
        return None
    return MyTimetableOut(
        upload_id=up.id,
        uploaded_at=up.created_at,
        review_status=up.review_status.value,
        entries=[
            MyTimetableEntryOut(
                weekday=r.weekday,
                period_start=r.period_start,
                period_end=r.period_end,
                week_expr=_rule_week_expr(r),
                location_code=r.location_code,
                course_name=r.course_name,
            )
            for r in up.course_rules
        ],
    )


def _rule_week_expr(rule) -> str:
    """从 CourseRule 反推展示用周次表达。"""
    if rule.explicit_weeks:
        ws = list(rule.explicit_weeks)
        if len(ws) <= 1:
            return f"{ws[0]}周"
        # 简单连续区间
        if ws == list(range(ws[0], ws[-1] + 1)):
            base = f"{ws[0]}-{ws[-1]}周"
            if rule.week_parity == "odd":
                base += "(单)"
            elif rule.week_parity == "even":
                base += "(双)"
            return base
        return ",".join(str(w) for w in ws) + "周"
    return ""
