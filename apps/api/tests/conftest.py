"""测试夹具：使用内存 SQLite 建表，覆盖 get_db 依赖。

模型使用可移植类型（Uuid / JSONBType / 通用 Enum），因此可在 SQLite 上建表；
生产仍走 Postgres（JSONB、原生 enum）。
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.cookies import CSRF_COOKIE_NAME, CSRF_HEADER_NAME
from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import User  # noqa: F401 - 触发全部模型注册
from app.models.enums import UserRole
from app.models.user import User as UserModel


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def seed_admin(db_session):
    admin = UserModel(
        username="admin",
        password_hash=hash_password("admin1234"),
        role=UserRole.admin,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    return admin


def login(client: TestClient, username: str, password: str) -> str:
    """登录并返回 CSRF 令牌，供后续写操作请求头使用。"""
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return client.cookies.get(CSRF_COOKIE_NAME)


def csrf_headers(token: str) -> dict:
    return {CSRF_HEADER_NAME: token}
