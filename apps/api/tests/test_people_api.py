"""人员管理 API 集成测试（路由 + 权限 + 多部分上传）。"""

from __future__ import annotations

import io

from openpyxl import Workbook

from app.core.security import hash_password
from app.models.enums import UserRole
from app.models.user import User
from tests.conftest import csrf_headers, login


def _xlsx() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(["学号", "班级", "姓名", "手机号", "困难等级", "身份证号", "银行卡号"])
    ws.append(["20240001", "软件1班", "陈晨", "13711112222", "一般", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_admin_import_preview_and_confirm(client, seed_admin):
    token = login(client, "admin", "admin1234")
    files = {
        "file": (
            "p.xlsx",
            _xlsx(),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    }
    resp = client.post("/api/v1/people/import/preview", files=files, headers=csrf_headers(token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["new_rows"] == 1
    batch_id = body["batch_id"]

    resp2 = client.post(f"/api/v1/people/import/{batch_id}/confirm", headers=csrf_headers(token))
    assert resp2.status_code == 200, resp2.text
    accounts = resp2.json()["accounts"]
    assert accounts[0]["student_no"] == "20240001"
    assert accounts[0]["initial_password"] == "20240001cc"

    # 列表可见，敏感字段掩码
    lst = client.get("/api/v1/people").json()
    assert any(p["student_no"] == "20240001" for p in lst)


def test_normal_user_cannot_list_people(client, db_session):
    user = User(
        username="u1", password_hash=hash_password("pw123456"), role=UserRole.user, is_active=True
    )
    db_session.add(user)
    db_session.commit()
    login(client, "u1", "pw123456")
    assert client.get("/api/v1/people").status_code == 403


def test_create_and_activate_semester_via_api(client, seed_admin):
    token = login(client, "admin", "admin1234")
    resp = client.post(
        "/api/v1/semesters",
        json={"name": "2026 秋", "first_monday": "2026-09-07", "is_current": True},
        headers=csrf_headers(token),
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["is_current"] is True
    sem_id = resp.json()["id"]
    rules = client.get(f"/api/v1/semesters/{sem_id}/period-rules").json()
    assert len(rules) == 6
