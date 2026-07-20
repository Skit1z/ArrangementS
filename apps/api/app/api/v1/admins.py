"""admin 账号管理路由。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import require_admin
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.admin import CreateAdminRequest, ResetPasswordResult
from app.schemas.auth import MessageOut, UserOut
from app.services import auth_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/admins", response_model=list[UserOut])
def list_admins(_: User = Depends(require_admin), db: Session = Depends(get_db)) -> list[User]:
    return list(db.scalars(select(User).where(User.role == UserRole.admin)).all())


@router.post("/admins", response_model=UserOut, status_code=201)
def create_admin(
    payload: CreateAdminRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> User:
    admin = auth_service.create_admin(db, actor, payload.username, payload.password)
    db.commit()
    return admin


@router.post("/admins/{admin_id}/disable", response_model=MessageOut)
def disable_admin(
    admin_id: uuid.UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> MessageOut:
    auth_service.disable_admin(db, actor, admin_id)
    db.commit()
    return MessageOut(message="admin 已停用")


@router.post("/admins/{admin_id}/reset-password", response_model=ResetPasswordResult)
def reset_admin_password(
    admin_id: uuid.UUID,
    payload: CreateAdminRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ResetPasswordResult:
    auth_service.reset_password(db, actor, admin_id, payload.password)
    db.commit()
    return ResetPasswordResult(message="密码已重置")


@router.post("/users/{user_id}/reset-password", response_model=ResetPasswordResult)
def reset_user_password(
    user_id: uuid.UUID,
    payload: CreateAdminRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ResetPasswordResult:
    auth_service.reset_password(db, actor, user_id, payload.password)
    db.commit()
    return ResetPasswordResult(message="密码已重置")
