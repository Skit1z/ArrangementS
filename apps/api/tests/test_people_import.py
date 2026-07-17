"""人员 Excel 导入服务测试（方案 3.1 / 3.2）。"""
from __future__ import annotations

import io

from openpyxl import Workbook
from sqlalchemy import select

from app.core.pinyin import build_initial_password
from app.core.security import verify_password
from app.models.person import PersonProfile
from app.models.user import User
from app.services import people_import


def build_xlsx(rows: list[dict]) -> bytes:
    wb = Workbook()
    ws = wb.active
    headers = ["学号", "班级", "姓名", "手机号", "困难等级", "身份证号", "银行卡号"]
    ws.append(headers)
    for r in rows:
        ws.append([r.get(h, "") for h in headers])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


ADMIN_ID = None


def _preview_and_confirm(db, rows):
    batch = people_import.create_preview(db, "t.xlsx", build_xlsx(rows), actor_id=None)
    db.commit()
    created = people_import.confirm_import(db, batch.id)
    db.commit()
    return batch, created


def test_import_creates_account_and_password(db_session):
    rows = [{"学号": "20230001", "班级": "计算机1班", "姓名": "王文博", "手机号": "13800001111", "困难等级": "一般"}]
    _, created = _preview_and_confirm(db_session, rows)
    assert len(created) == 1

    user = db_session.scalar(select(User).where(User.username == "20230001"))
    assert user is not None
    expected_pw = build_initial_password("20230001", "王文博")
    assert expected_pw == "20230001wwb"
    assert verify_password(expected_pw, user.password_hash)
    assert created[0].initial_password == expected_pw


def test_sensitive_fields_encrypted_not_plaintext(db_session):
    rows = [{
        "学号": "20230002", "班级": "计算机1班", "姓名": "李雷", "手机号": "13900002222",
        "困难等级": "", "身份证号": "110101199003072316", "银行卡号": "6222021234567890",
    }]
    _preview_and_confirm(db_session, rows)
    prof = db_session.scalar(select(PersonProfile).where(PersonProfile.student_no == "20230002"))
    assert prof.id_card_ciphertext is not None
    assert b"110101" not in prof.id_card_ciphertext  # 非明文
    assert prof.id_card_last4 == "2316"
    assert prof.bank_card_last4 == "7890"


def test_preview_classifies_errors(db_session):
    rows = [
        {"学号": "20230003", "班级": "一班", "姓名": "张三", "手机号": "139", "困难等级": ""},  # 手机号非法
        {"学号": "", "班级": "一班", "姓名": "李四", "手机号": "13900003333", "困难等级": ""},  # 学号为空
        {"学号": "20230005", "班级": "一班", "姓名": "王五", "手机号": "13900005555", "困难等级": ""},  # 正常
    ]
    batch = people_import.create_preview(db_session, "t.xlsx", build_xlsx(rows), actor_id=None)
    db_session.commit()
    assert batch.error_rows == 2
    assert batch.new_rows == 1


def test_same_batch_duplicate_marked_error(db_session):
    rows = [
        {"学号": "20230006", "班级": "一班", "姓名": "赵六", "手机号": "13900006666", "困难等级": ""},
        {"学号": "20230006", "班级": "一班", "姓名": "赵六二", "手机号": "13900006667", "困难等级": ""},
    ]
    batch = people_import.create_preview(db_session, "t.xlsx", build_xlsx(rows), actor_id=None)
    db_session.commit()
    assert batch.error_rows == 1  # 第二行重复


def test_reimport_updates_not_duplicates(db_session):
    rows = [{"学号": "20230007", "班级": "一班", "姓名": "钱七", "手机号": "13900007777", "困难等级": ""}]
    _preview_and_confirm(db_session, rows)

    rows2 = [{"学号": "20230007", "班级": "二班", "姓名": "钱七", "手机号": "13900007788", "困难等级": ""}]
    batch2 = people_import.create_preview(db_session, "t.xlsx", build_xlsx(rows2), actor_id=None)
    db_session.commit()
    assert batch2.updated_rows == 1
    assert batch2.new_rows == 0

    people_import.confirm_import(db_session, batch2.id)
    db_session.commit()
    prof = db_session.scalar(select(PersonProfile).where(PersonProfile.student_no == "20230007"))
    assert prof.class_name == "二班"
    assert prof.phone == "13900007788"
    # 仍只有一个账号
    count = len(list(db_session.scalars(select(User).where(User.username == "20230007"))))
    assert count == 1


def test_missing_required_column_rejected(db_session):
    wb = Workbook()
    ws = wb.active
    ws.append(["学号", "姓名"])  # 缺列
    ws.append(["20230008", "孙八"])
    buf = io.BytesIO()
    wb.save(buf)
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        people_import.create_preview(db_session, "t.xlsx", buf.getvalue(), actor_id=None)
    assert ei.value.status_code == 422


def test_confirm_idempotent(db_session):
    rows = [{"学号": "20230009", "班级": "一班", "姓名": "周九", "手机号": "13900009999", "困难等级": ""}]
    batch = people_import.create_preview(db_session, "t.xlsx", build_xlsx(rows), actor_id=None)
    db_session.commit()
    people_import.confirm_import(db_session, batch.id)
    db_session.commit()
    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as ei:
        people_import.confirm_import(db_session, batch.id)
    assert ei.value.status_code == 409
