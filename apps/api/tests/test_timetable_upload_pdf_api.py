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
