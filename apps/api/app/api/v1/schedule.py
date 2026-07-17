"""排班路由：生成、发布、查询、锁定（方案 13.6）。"""
from __future__ import annotations

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_admin
from app.db.session import get_db
from app.models.enums import PlanStatus, UserRole
from app.models.user import User
from app.schemas.auth import MessageOut
from app.schemas.schedule import GenerateRequest, WeekView
from app.services import schedule_service

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/weeks/{week_start}", response_model=WeekView)
def get_week(
    week_start: date,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    plan = schedule_service.get_plan(db, week_start)
    # 普通用户仅查看已发布计划
    if current.role != UserRole.admin and plan.status != PlanStatus.published:
        raise HTTPException(status_code=403, detail="该周排班尚未发布")
    return schedule_service.serialize_week(db, plan)


@router.post("/weeks/{week_start}/generate")
def generate_week(
    week_start: date,
    payload: GenerateRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    summary = schedule_service.generate(db, week_start, actor.id, seed=payload.seed)
    db.commit()
    return summary


@router.post("/weeks/{week_start}/publish", response_model=MessageOut)
def publish_week(
    week_start: date, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    plan = schedule_service.publish(db, week_start, actor.id)
    db.commit()
    return MessageOut(message=f"已发布（修订号 {plan.revision}）")


assignments_router = APIRouter(prefix="/assignments", tags=["schedule"])


@assignments_router.post("/{assignment_id}/lock", response_model=MessageOut)
def lock_assignment(
    assignment_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    schedule_service.set_lock(db, assignment_id, True)
    db.commit()
    return MessageOut(message="已锁定")


@assignments_router.post("/{assignment_id}/unlock", response_model=MessageOut)
def unlock_assignment(
    assignment_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    schedule_service.set_lock(db, assignment_id, False)
    db.commit()
    return MessageOut(message="已解锁")
