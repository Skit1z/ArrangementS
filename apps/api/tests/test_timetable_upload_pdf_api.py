"""PDF 课表解析端点测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from app.services import semester_service
from tests.conftest import csrf_headers, login

FIXTURE = Path(__file__).parent / "fixtures" / "sample_timetable.pdf"


def _seed_user(db):
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User

    u = User(
        username="202301070410",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no="202301070410",
        class_name="信管231",
        full_name="王文博",
        phone="13800000000",
    )
    db.add(p)
    db.commit()
    return u, p


def test_parse_pdf_returns_entries(client, seed_admin, db_session):
    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        data={"semester_id": str(sem.id)},
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["student_no"] == "202301070410"
    assert len(body["entries"]) == 10
    # 每条 entry 有前端入库所需字段
    e0 = body["entries"][0]
    assert {"weekday", "period_start", "period_end", "week_expr", "location_code"} <= set(e0.keys())


def test_parse_pdf_without_semester_uses_current(client, seed_admin, db_session):
    """不传 semester_id 时，自动用当前学期。"""
    semester_service.create_semester(
        db_session, name="春", first_monday=date(2026, 2, 23), is_current=True
    )
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["entries"]) == 10


def test_parse_pdf_rejects_non_pdf(client, seed_admin, db_session):
    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        data={"semester_id": str(sem.id)},
        files={"file": ("not.pdf", b"hello world", "text/plain")},
    )
    assert resp.status_code == 400
    detail = resp.json()["detail"]
    assert "PDF" in detail or "pdf" in detail.lower()


def test_parse_pdf_requires_login(client, db_session):
    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    resp = client.post(
        "/api/v1/timetables/parse-pdf",
        data={"semester_id": str(sem.id)},
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    )
    assert resp.status_code in (401, 403)  # 未登录或 CSRF 拦截


def test_user_can_approve_own_upload(client, seed_admin, db_session):
    """用户上传后可直接 approve 自己的课表（上传即生效）。"""
    from sqlalchemy import select
    from app.models.availability import AvailabilityBlock

    sem = semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")

    # 1) 解析 PDF
    parsed = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        data={"semester_id": str(sem.id)},
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    ).json()

    # 2) 用解析结果创建 upload
    upload = client.post(
        "/api/v1/timetables/upload",
        headers=csrf_headers(token),
        json={
            "semester_id": str(sem.id),
            "file_name": "sample.pdf",
            "entries": parsed["entries"],
        },
    ).json()
    upload_id = upload["id"]

    # 3) 普通用户 approve 自己的（之前会 403，现在应 200）
    resp = client.post(f"/api/v1/timetables/{upload_id}/approve", headers=csrf_headers(token))
    assert resp.status_code == 200, resp.text

    # 4) 验证已生成不可值班区间（10 条课程规则，按各自周次展开）
    blocks = list(db_session.scalars(select(AvailabilityBlock)))
    assert len(blocks) > 0


def test_user_cannot_approve_others_upload(client, seed_admin, db_session):
    """普通用户不能 approve 别人的 upload。"""
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User

    semester_service.create_semester(db_session, name="春", first_monday=date(2026, 2, 23))
    db_session.commit()
    _seed_user(db_session)

    # 另一个用户
    u2 = User(
        username="20250002",
        password_hash=hash_password("pw123456"),
        role=UserRole.user,
        is_active=True,
    )
    db_session.add(u2)
    db_session.flush()
    db_session.add(
        PersonProfile(
            user_id=u2.id,
            student_no="20250002",
            class_name="一班",
            full_name="乙",
            phone="13800000001",
        )
    )
    db_session.commit()

    # owner 上传
    token_owner = login(client, "202301070410", "pw123456")
    upload = client.post(
        "/api/v1/timetables/upload",
        headers=csrf_headers(token_owner),
        json={
            "file_name": "t.pdf",
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
    ).json()

    # 乙尝试 approve 甲的
    token_other = login(client, "20250002", "pw123456")
    resp = client.post(
        f"/api/v1/timetables/{upload['id']}/approve", headers=csrf_headers(token_other)
    )
    assert resp.status_code == 403


def test_upload_without_semester_uses_current(client, seed_admin, db_session):
    """不传 semester_id 时，/upload 自动用当前学期。"""
    semester_service.create_semester(
        db_session, name="春", first_monday=date(2026, 2, 23), is_current=True
    )
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")
    resp = client.post(
        "/api/v1/timetables/upload",
        headers=csrf_headers(token),
        json={
            "file_name": "t.pdf",
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
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["review_status"] == "draft"


def test_end_to_end_pdf_upload_and_apply(client, seed_admin, db_session):
    """端到端：解析 PDF → upload → approve（上传者本人）→ /me/timetable 反映。"""
    from sqlalchemy import select
    from app.models.availability import AvailabilityBlock

    semester_service.create_semester(
        db_session, name="春", first_monday=date(2026, 2, 23), is_current=True
    )
    db_session.commit()
    _seed_user(db_session)

    token = login(client, "202301070410", "pw123456")

    parsed = client.post(
        "/api/v1/timetables/parse-pdf",
        headers=csrf_headers(token),
        files={"file": ("sample.pdf", FIXTURE.read_bytes(), "application/pdf")},
    ).json()

    upload = client.post(
        "/api/v1/timetables/upload",
        headers=csrf_headers(token),
        json={"file_name": "sample.pdf", "entries": parsed["entries"]},
    ).json()

    resp = client.post(f"/api/v1/timetables/{upload['id']}/approve", headers=csrf_headers(token))
    assert resp.status_code == 200, resp.text

    # 已生成不可值班区间
    blocks = list(db_session.scalars(select(AvailabilityBlock)))
    assert len(blocks) > 0

    mine = client.get("/api/v1/me/timetable").json()
    assert mine["review_status"] == "approved"
    assert len(mine["entries"]) == 10
