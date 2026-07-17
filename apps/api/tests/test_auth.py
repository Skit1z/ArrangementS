"""认证与 admin 管理 API 测试。"""
from __future__ import annotations

from app.core.cookies import CSRF_COOKIE_NAME
from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import csrf_headers, login


def test_login_success_sets_cookies(client, seed_admin):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "admin1234"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin"
    assert client.cookies.get("access_token")
    assert client.cookies.get(CSRF_COOKIE_NAME)


def test_login_wrong_password(client, seed_admin):
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "bad"})
    assert resp.status_code == 401


def test_me_requires_auth(client):
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_after_login(client, seed_admin):
    login(client, "admin", "admin1234")
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_write_requires_csrf(client, seed_admin):
    login(client, "admin", "admin1234")
    # 不带 CSRF 头 → 403
    resp = client.post(
        "/api/v1/admin/admins", json={"username": "admin2", "password": "secret123"}
    )
    assert resp.status_code == 403


def test_create_admin_with_csrf(client, seed_admin):
    token = login(client, "admin", "admin1234")
    resp = client.post(
        "/api/v1/admin/admins",
        json={"username": "admin2", "password": "secret123"},
        headers=csrf_headers(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["username"] == "admin2"


def test_normal_user_cannot_create_admin(client, db_session):
    user = User(
        username="20230001",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    token = login(client, "20230001", "pw123456")
    resp = client.post(
        "/api/v1/admin/admins",
        json={"username": "hacker", "password": "secret123"},
        headers=csrf_headers(token),
    )
    assert resp.status_code == 403


def test_cannot_disable_self(client, seed_admin):
    token = login(client, "admin", "admin1234")
    resp = client.post(
        f"/api/v1/admin/admins/{seed_admin.id}/disable", headers=csrf_headers(token)
    )
    assert resp.status_code == 400


def test_change_password_then_relogin(client, seed_admin):
    token = login(client, "admin", "admin1234")
    resp = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": "admin1234", "new_password": "newpass123"},
        headers=csrf_headers(token),
    )
    assert resp.status_code == 200
    client.post("/api/v1/auth/logout", headers=csrf_headers(token))
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "admin1234"}
    ).status_code == 401
    assert client.post(
        "/api/v1/auth/login", json={"username": "admin", "password": "newpass123"}
    ).status_code == 200


def test_last_admin_cannot_be_disabled(client, seed_admin, db_session):
    token = login(client, "admin", "admin1234")
    other = client.post(
        "/api/v1/admin/admins",
        json={"username": "admin2", "password": "secret123"},
        headers=csrf_headers(token),
    ).json()
    # 停用 admin2 后仅剩 admin 自己；再尝试停用 admin 自己走的是 “不能停用自己”
    client.post(f"/api/v1/admin/admins/{other['id']}/disable", headers=csrf_headers(token))
    # 仅剩一个启用 admin（自己），停用自己被拒
    resp = client.post(
        f"/api/v1/admin/admins/{seed_admin.id}/disable", headers=csrf_headers(token)
    )
    assert resp.status_code == 400
