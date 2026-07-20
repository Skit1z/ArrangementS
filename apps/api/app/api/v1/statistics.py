"""月度统计路由（方案 13.9）。admin 看全员，普通用户仅本人。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.person import PersonProfile
from app.models.user import User
from app.schemas.auth import MessageOut
from app.services import people_service, schedule_stats, stats_export

router = APIRouter(prefix="/statistics", tags=["statistics"])


class AdjustmentIn(BaseModel):
    person_id: uuid.UUID
    minutes_delta: int
    affect_balance: bool = False
    reason: str


def _summary_dict(s, p) -> dict:
    return {
        "person_id": str(s.person_id),
        "person_name": p.full_name,
        "student_no": p.student_no,
        "class_name": p.class_name,
        "balance_minutes": s.balance_minutes,
        "completed_minutes": s.completed_minutes,
        "multiplier_extra_minutes": s.multiplier_extra_minutes,
        "leave_count": s.leave_count,
        "swap_out_count": s.swap_out_count,
        "replacement_count": s.replacement_count,
        "absence_count": s.absence_count,
        "status": s.status.value,
    }


@router.get("/monthly/{month}")
def monthly(
    month: str, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    return [_summary_dict(s, p) for s, p in schedule_stats.list_monthly(db, month)]


@router.get("/monthly/{month}/people/{person_id}")
def person_monthly(
    month: str,
    person_id: uuid.UUID,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    if current.role != UserRole.admin:
        own = people_service.get_person_by_user(db, current.id)
        if own.id != person_id:
            raise HTTPException(status_code=403, detail="只能查看本人统计")
    s = schedule_stats.get_summary(db, month, person_id)
    breakdown = schedule_stats.venue_breakdown(db, month, person_id)
    # 取人员档案用于姓名（admin 视图需要）
    p = db.get(PersonProfile, person_id)
    base = (
        _summary_dict(s, p)
        if p is not None
        else {
            "person_id": str(s.person_id),
            "person_name": None,
            "student_no": None,
            "class_name": None,
            "balance_minutes": s.balance_minutes,
            "completed_minutes": s.completed_minutes,
            "multiplier_extra_minutes": s.multiplier_extra_minutes,
            "leave_count": s.leave_count,
            "swap_out_count": s.swap_out_count,
            "replacement_count": s.replacement_count,
            "absence_count": s.absence_count,
            "status": s.status.value,
        }
    )
    return {
        **base,
        "venues": [
            {
                "venue_id": str(v.venue_id),
                "venue_name": venue.name,
                "completed_minutes": v.completed_minutes,
                "balance_minutes": v.balance_minutes,
            }
            for v, venue in breakdown
        ],
    }


@router.post("/monthly/{month}/recalculate", response_model=MessageOut)
def recalculate(
    month: str, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    n = schedule_stats.recalculate(db, month)
    db.commit()
    return MessageOut(message=f"已重算 {n} 人")


@router.post("/monthly/{month}/lock", response_model=MessageOut)
def lock(
    month: str, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    n = schedule_stats.lock_month(db, actor.id, month)
    db.commit()
    return MessageOut(message=f"已锁定 {n} 条月度汇总")


@router.post("/monthly/{month}/adjustments", response_model=MessageOut)
def add_adjustment(
    month: str,
    payload: AdjustmentIn,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    schedule_stats.add_adjustment(
        db,
        actor_id=actor.id,
        month_key=month,
        person_id=payload.person_id,
        minutes_delta=payload.minutes_delta,
        affect_balance=payload.affect_balance,
        reason=payload.reason,
    )
    db.commit()
    return MessageOut(message="已记录工时调整")


@router.get("/monthly/{month}/export")
def export(month: str, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> Response:
    content = stats_export.build_export(db, month)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="hours-{month}.xlsx"'},
    )
