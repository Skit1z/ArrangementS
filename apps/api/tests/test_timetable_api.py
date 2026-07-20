"""课表 API 集成测试：普通用户自助上传 + 提交 + admin 审核生效。"""

from __future__ import annotations

from datetime import date

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.person import PersonProfile
from app.models.user import User
from app.services import semester_service
from tests.conftest import csrf_headers, login


def _seed_user_with_profile(db):
    u = User(
        username="20250001",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no="20250001",
        class_name="一班",
        full_name="学生甲",
        phone="13800000000",
    )
    db.add(p)
    db.commit()
    return u, p


def test_user_upload_and_admin_approve(client, seed_admin, db_session):
    sem = semester_service.create_semester(db_session, name="秋", first_monday=date(2026, 9, 7))
    db_session.commit()
    _seed_user_with_profile(db_session)

    token = login(client, "20250001", "pw123456")
    resp = client.post(
        "/api/v1/timetables/upload",
        json={
            "semester_id": str(sem.id),
            "file_name": "my.pdf",
            "entries": [
                {
                    "weekday": 3,
                    "period_start": 3,
                    "period_end": 4,
                    "week_expr": "1-8周",
                    "location_code": "B608",
                    "course_name": "高数",
                }
            ],
        },
        headers=csrf_headers(token),
    )
    assert resp.status_code == 200, resp.text
    up = resp.json()
    assert up["review_status"] == "draft"
    assert up["rules"][0]["building_type"] == "main"
    upload_id = up["id"]

    client.post(f"/api/v1/timetables/{upload_id}/submit", headers=csrf_headers(token))

    # 另一个普通用户不能审核别人的（owner 本人现在可以 approve 自己的）
    other = User(
        username="20250099",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(
        PersonProfile(
            user_id=other.id,
            student_no="20250099",
            class_name="一班",
            full_name="丙",
            phone="13800000002",
        )
    )
    db_session.commit()
    other_token = login(client, "20250099", "pw123456")
    assert (
        client.post(
            f"/api/v1/timetables/{upload_id}/approve", headers=csrf_headers(other_token)
        ).status_code
        == 403
    )

    # admin 审核通过
    client.post("/api/v1/auth/logout", headers=csrf_headers(token))
    atoken = login(client, "admin", "admin1234")
    resp2 = client.post(f"/api/v1/timetables/{upload_id}/approve", headers=csrf_headers(atoken))
    assert resp2.status_code == 200, resp2.text

    from app.models.availability import AvailabilityBlock
    from sqlalchemy import select

    blocks = list(db_session.scalars(select(AvailabilityBlock)))
    assert len(blocks) == 8


def test_user_cannot_access_others_timetable(client, seed_admin, db_session):
    sem = semester_service.create_semester(db_session, name="秋", first_monday=date(2026, 9, 7))
    db_session.commit()
    _, p = _seed_user_with_profile(db_session)

    # admin 代该用户上传
    atoken = login(client, "admin", "admin1234")
    resp = client.post(
        "/api/v1/timetables/upload",
        json={
            "semester_id": str(sem.id),
            "person_id": str(p.id),
            "entries": [
                {
                    "weekday": 1,
                    "period_start": 1,
                    "period_end": 2,
                    "week_expr": "1-4周",
                    "location_code": "B101",
                }
            ],
        },
        headers=csrf_headers(atoken),
    )
    upload_id = resp.json()["id"]
    client.post("/api/v1/auth/logout", headers=csrf_headers(atoken))

    # 另一个普通用户无权查看
    other = User(
        username="20250002",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(
        PersonProfile(
            user_id=other.id,
            student_no="20250002",
            class_name="一班",
            full_name="乙",
            phone="13800000001",
        )
    )
    db_session.commit()
    login(client, "20250002", "pw123456")
    assert client.get(f"/api/v1/timetables/{upload_id}/preview").status_code == 403
