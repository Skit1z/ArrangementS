"""认证与 admin 账号管理业务逻辑。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import ratelimit
from app.core.security import hash_password, needs_rehash, verify_password
from app.models.enums import UserRole
from app.models.user import User
from app.services.audit_service import record_audit


def authenticate(db: Session, username: str, password: str) -> User:
    if ratelimit.is_locked(username):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
        )
    user = db.scalar(select(User).where(User.username == username))
    if user is None or not verify_password(password, user.password_hash):
        ratelimit.register_failure(username)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已停用")

    ratelimit.reset(username)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    user.last_login_at = datetime.now(timezone.utc)
    db.flush()
    return user


def change_password(db: Session, user: User, old_password: str, new_password: str) -> None:
    if not verify_password(old_password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码错误")
    user.password_hash = hash_password(new_password)
    db.flush()


def _active_admin_count(db: Session) -> int:
    return db.scalar(
        select(func.count()).select_from(User).where(
            User.role == UserRole.admin, User.is_active.is_(True)
        )
    ) or 0


def create_admin(db: Session, actor: User, username: str, password: str) -> User:
    exists = db.scalar(select(User).where(User.username == username))
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="用户名已存在")
    admin = User(
        username=username,
        password_hash=hash_password(password),
        role=UserRole.admin,
        is_active=True,
    )
    db.add(admin)
    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="admin.create",
        entity_type="user",
        entity_id=admin.id,
        after_data={"username": username, "role": "admin"},
    )
    return admin


def disable_admin(db: Session, actor: User, target_id: uuid.UUID) -> User:
    target = db.get(User, target_id)
    if target is None or target.role != UserRole.admin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="admin 不存在")
    if target.id == actor.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用自己")
    if target.is_active and _active_admin_count(db) <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="系统至少保留一个启用的 admin"
        )
    target.is_active = False
    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="admin.disable",
        entity_type="user",
        entity_id=target.id,
    )
    return target


def reset_password(db: Session, actor: User, target_id: uuid.UUID, new_password: str) -> User:
    target = db.get(User, target_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    target.password_hash = hash_password(new_password)
    db.flush()
    record_audit(
        db,
        actor_user_id=actor.id,
        action="user.reset_password",
        entity_type="user",
        entity_id=target.id,
    )
    return target
