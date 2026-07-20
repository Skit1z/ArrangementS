"""假期与假期可值班白名单测试。"""

from __future__ import annotations

from datetime import date, datetime

from app.services import vacation_service


def _person(db):
    from app.core.security import hash_password
    from app.models.enums import UserRole
    from app.models.person import PersonProfile
    from app.models.user import User

    user = User(username="s1", password_hash=hash_password("x"), role=UserRole.user, is_active=True)
    db.add(user)
    db.flush()
    prof = PersonProfile(
        user_id=user.id, student_no="s1", class_name="一班", full_name="甲", phone="13800000000"
    )
    db.add(prof)
    db.flush()
    return prof


def dt(day, hh):
    return datetime(2026, 2, day, hh, 0)


def test_set_availabilities_merges(db_session):
    prof = _person(db_session)
    vac = vacation_service.create_vacation(
        db_session,
        actor_id=None,
        name="寒假",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )
    db_session.commit()
    result = vacation_service.set_availabilities(
        db_session,
        actor_id=None,
        vacation_id=vac.id,
        person_id=prof.id,
        intervals=[(dt(10, 8), dt(10, 12)), (dt(10, 11), dt(10, 16))],
    )
    db_session.commit()
    assert len(result) == 1  # 合并为一段 08:00-16:00
    assert result[0].start_at == dt(10, 8)
    assert result[0].end_at == dt(10, 16)


def test_whitelist_availability_check(db_session):
    prof = _person(db_session)
    vac = vacation_service.create_vacation(
        db_session,
        actor_id=None,
        name="寒假",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )
    vacation_service.set_availabilities(
        db_session,
        actor_id=None,
        vacation_id=vac.id,
        person_id=prof.id,
        intervals=[(dt(10, 8), dt(10, 12))],
    )
    db_session.commit()
    # 完整落在区间内 → 可用
    assert vacation_service.is_person_available(db_session, vac.id, prof.id, dt(10, 8), dt(10, 10))
    # 超出区间 → 不可用（白名单语义）
    assert not vacation_service.is_person_available(
        db_session, vac.id, prof.id, dt(10, 11), dt(10, 14)
    )
    # 未登记的另一天 → 不可用
    assert not vacation_service.is_person_available(
        db_session, vac.id, prof.id, dt(15, 8), dt(15, 10)
    )


def test_set_availabilities_replaces(db_session):
    prof = _person(db_session)
    vac = vacation_service.create_vacation(
        db_session,
        actor_id=None,
        name="寒假",
        start_date=date(2026, 2, 1),
        end_date=date(2026, 2, 28),
    )
    vacation_service.set_availabilities(
        db_session,
        actor_id=None,
        vacation_id=vac.id,
        person_id=prof.id,
        intervals=[(dt(10, 8), dt(10, 12))],
    )
    db_session.commit()
    vacation_service.set_availabilities(
        db_session,
        actor_id=None,
        vacation_id=vac.id,
        person_id=prof.id,
        intervals=[(dt(11, 14), dt(11, 18))],
    )
    db_session.commit()
    rows = vacation_service.list_availabilities(db_session, vac.id)
    assert len(rows) == 1
    assert rows[0].start_at == dt(11, 14)
