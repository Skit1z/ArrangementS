"""认证路由。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.cookies import clear_auth_cookies, set_auth_cookies
from app.core.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, MessageOut, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = auth_service.authenticate(db, payload.username, payload.password)
    db.commit()
    access = create_access_token(user.id, user.role.value)
    refresh = create_refresh_token(user.id, user.role.value)
    set_auth_cookies(response, access, refresh)
    return user


@router.post("/logout", response_model=MessageOut)
def logout(response: Response, _: User = Depends(get_current_user)) -> MessageOut:
    clear_auth_cookies(response)
    return MessageOut(message="已退出登录")


@router.get("/me", response_model=UserOut)
def me(current: User = Depends(get_current_user)) -> User:
    return current


@router.post("/change-password", response_model=MessageOut)
def change_password(
    payload: ChangePasswordRequest,
    current: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MessageOut:
    auth_service.change_password(db, current, payload.old_password, payload.new_password)
    db.commit()
    return MessageOut(message="密码已更新")
