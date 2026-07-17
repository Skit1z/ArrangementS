"""admin 审核路由：不可值班申请、请假、换班；未到岗/完成标记。"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.workflow import (
    AdminBlockIn,
    AvailabilityRequestOut,
    LeaveOut,
    ReviewIn,
    SwapApproveIn,
    SwapOut,
)
from app.services import (
    availability_service,
    execution_service,
    leave_service,
    swap_service,
)

router = APIRouter(prefix="/admin", tags=["admin-workflow"])


# --- 不可值班申请 ---
@router.get("/availability-requests", response_model=list[AvailabilityRequestOut])
def pending_availability(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return availability_service.list_pending(db)


@router.post("/availability-requests/{request_id}/approve", response_model=AvailabilityRequestOut)
def approve_availability(request_id: uuid.UUID, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    req = availability_service.approve(db, actor.id, request_id)
    db.commit()
    return req


@router.post("/availability-requests/{request_id}/reject", response_model=AvailabilityRequestOut)
def reject_availability(request_id: uuid.UUID, payload: ReviewIn, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    req = availability_service.reject(db, actor.id, request_id, payload.comment)
    db.commit()
    return req


@router.post("/people/{person_id}/availability-blocks", response_model=MessageOut)
def admin_create_block(person_id: uuid.UUID, payload: AdminBlockIn, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    availability_service.admin_create_block(
        db, actor_id=actor.id, person_id=person_id, start_at=payload.start_at,
        end_at=payload.end_at, reason=payload.reason,
    )
    db.commit()
    return MessageOut(message="已设置不可值班区间")


# --- 请假 ---
@router.get("/leave-requests", response_model=list[LeaveOut])
def pending_leaves(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return leave_service.list_pending(db)


@router.post("/leave-requests/{leave_id}/approve", response_model=LeaveOut)
def approve_leave(leave_id: uuid.UUID, payload: ReviewIn, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    leave = leave_service.approve(db, actor.id, leave_id, payload.comment)
    db.commit()
    return leave


@router.post("/leave-requests/{leave_id}/reject", response_model=LeaveOut)
def reject_leave(leave_id: uuid.UUID, payload: ReviewIn, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    leave = leave_service.reject(db, actor.id, leave_id, payload.comment)
    db.commit()
    return leave


# --- 换班 ---
@router.get("/swap-requests", response_model=list[SwapOut])
def open_swaps(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return swap_service.list_open(db)


@router.post("/swap-requests/{swap_id}/approve", response_model=SwapOut)
def approve_swap(swap_id: uuid.UUID, payload: SwapApproveIn, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    swap = swap_service.admin_approve(db, actor_id=actor.id, swap_id=swap_id, selected_person_id=payload.selected_person_id)
    db.commit()
    return swap


@router.post("/swap-requests/{swap_id}/reject", response_model=SwapOut)
def reject_swap(swap_id: uuid.UUID, payload: ReviewIn, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    swap = swap_service.admin_reject(db, actor_id=actor.id, swap_id=swap_id, comment=payload.comment)
    db.commit()
    return swap


# --- 未到岗 / 完成标记 ---
assignments_router = APIRouter(prefix="/assignments", tags=["admin-workflow"])


@assignments_router.post("/{assignment_id}/mark-absent", response_model=MessageOut)
def mark_absent(assignment_id: uuid.UUID, payload: ReviewIn, request: Request, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    execution_service.mark_absent(
        db, actor_id=actor.id, assignment_id=assignment_id, reason=payload.comment,
        ip=request.client.host if request.client else None, ua=request.headers.get("user-agent"),
    )
    db.commit()
    return MessageOut(message="已标记未到岗")


@assignments_router.post("/{assignment_id}/mark-completed", response_model=MessageOut)
def mark_completed(assignment_id: uuid.UUID, actor: User = Depends(require_admin), db: Session = Depends(get_db)):
    execution_service.mark_completed(db, actor_id=actor.id, assignment_id=assignment_id)
    db.commit()
    return MessageOut(message="已标记完成")
