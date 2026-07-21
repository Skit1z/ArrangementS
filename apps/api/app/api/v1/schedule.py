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
from app.schemas.schedule import (
    CandidateOut,
    ConflictOut,
    DraftSaveRequest,
    GenerateRequest,
    WeekPersonOut,
    WeekView,
)
from app.services import draft_service, schedule_service

router = APIRouter(prefix="/schedule", tags=["schedule"])


@router.get("/current-duty")
def current_duty(
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    """获取当前时刻正处于在岗值班状态的人员及联系电话（普通用户与管理员均可访问）。"""
    from app.services import me_service

    return me_service.get_current_on_duty_staff(db)


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
    summary = schedule_service.generate(
        db, week_start, actor.id, seed=payload.seed, clear_locks=payload.clear_locks
    )
    db.commit()
    return summary


@router.patch("/weeks/{week_start}/draft", response_model=WeekView)
def save_draft(
    week_start: date,
    payload: DraftSaveRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> dict:
    """拖拽保存：批量原子提交 + 乐观锁。时间重叠绝对拒绝；其他强制约束需 forced+原因。"""
    plan = draft_service.apply_operations(
        db,
        week_start=week_start,
        expected_version=payload.version,
        operations=[op.model_dump(mode="json") for op in payload.operations],
        actor_id=actor.id,
    )
    db.commit()
    db.expire_all()
    return schedule_service.serialize_week(db, plan)


@router.post("/weeks/{week_start}/validate", response_model=list[ConflictOut])
def validate_week(
    week_start: date, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list:
    return draft_service.validate_week(db, week_start)


@router.get("/candidates", response_model=list[CandidateOut])
def candidates(
    slot_id: uuid.UUID, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    return draft_service.list_candidates(db, slot_id)


@router.get("/weeks/{week_start}/people", response_model=list[WeekPersonOut])
def week_people(
    week_start: date, _: User = Depends(require_admin), db: Session = Depends(get_db)
) -> list[dict]:
    """人员抽屉：全周人员 + 当月工时 + 各自不可用岗位集合。"""
    return draft_service.week_people(db, week_start)


@router.post("/weeks/{week_start}/publish", response_model=MessageOut)
def publish_week(
    week_start: date, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    plan = schedule_service.publish(db, week_start, actor.id)
    db.commit()
    return MessageOut(message=f"已发布（修订号 {plan.revision}）")


@router.post("/weeks/{week_start}/unpublish", response_model=MessageOut)
def unpublish_week(
    week_start: date, actor: User = Depends(require_admin), db: Session = Depends(get_db)
) -> MessageOut:
    schedule_service.unpublish(db, week_start, actor.id)
    db.commit()
    return MessageOut(message="已撤销发布，恢复为草稿状态")


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
