"""排班 API 冒烟测试：生成/发布/查询/权限。"""
from __future__ import annotations

from datetime import time

from app.core.security import hash_password
from app.models.enums import PersonStatus, UserRole, VenueType
from app.models.person import PersonProfile
from app.models.user import User
from app.models.venue import ShiftTemplate, Venue
from tests.conftest import csrf_headers, login

MONDAY = "2026-03-02"


def _seed_yellow_and_people(db):
    v = Venue(name="黄楼", code="HL", venue_type=VenueType.fixed_shift, default_required_people=2)
    db.add(v)
    db.flush()
    db.add(ShiftTemplate(venue_id=v.id, name="第1班", start_time=time(8, 0), end_time=time(10, 0),
                         credited_minutes=120, weekday_required_people=2, weekend_required_people=1, sort_order=0))
    for i in range(3):
        u = User(username=f"u{i}", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True)
        db.add(u)
        db.flush()
        db.add(PersonProfile(user_id=u.id, student_no=f"u{i}", class_name="一班", full_name=f"人{i}",
                             phone="13800000000", status=PersonStatus.active, is_in_scheduling_pool=True))
    db.commit()


def test_generate_publish_get_flow(client, seed_admin, db_session):
    _seed_yellow_and_people(db_session)
    token = login(client, "admin", "admin1234")
    h = csrf_headers(token)

    gen = client.post(f"/api/v1/schedule/weeks/{MONDAY}/generate", json={"seed": 1}, headers=h)
    assert gen.status_code == 200, gen.text
    assert gen.json()["vacancies"] == 0

    # 普通用户在未发布时看不到
    client.post("/api/v1/auth/logout", headers=h)
    login(client, "u0", "pw123456")
    assert client.get(f"/api/v1/schedule/weeks/{MONDAY}").status_code == 403

    # admin 发布
    client.post("/api/v1/auth/logout")
    atoken = login(client, "admin", "admin1234")
    ah = csrf_headers(atoken)
    pub = client.post(f"/api/v1/schedule/weeks/{MONDAY}/publish", headers=ah)
    assert pub.status_code == 200

    # 普通用户现在可见
    client.post("/api/v1/auth/logout", headers=ah)
    login(client, "u0", "pw123456")
    view = client.get(f"/api/v1/schedule/weeks/{MONDAY}")
    assert view.status_code == 200
    assert view.json()["status"] == "published"
    assert len(view.json()["slots"]) >= 1


def test_generate_requires_admin(client, seed_admin, db_session):
    _seed_yellow_and_people(db_session)
    login(client, "u0", "pw123456")
    # 需带 CSRF 才能过中间件，再判角色
    from app.core.cookies import CSRF_COOKIE_NAME
    tok = client.cookies.get(CSRF_COOKIE_NAME)
    assert client.post(f"/api/v1/schedule/weeks/{MONDAY}/generate", json={"seed": 1}, headers=csrf_headers(tok)).status_code == 403
