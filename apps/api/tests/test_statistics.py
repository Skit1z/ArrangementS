"""月度统计与导出测试（方案 11）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta


from app.core.security import hash_password
from app.models.enums import (
    ExecutionStatus,
    MonthlySummaryStatus,
    PersonStatus,
    PlanAssignmentStatus,
    PlanStatus,
    SlotSourceType,
    SlotStatus,
    UserRole,
    VenueType,
)
from app.models.person import PersonProfile
from app.models.schedule import Assignment, DutySlot, WeeklyPlan
from app.models.user import User
from app.models.venue import Venue
from app.services import schedule_stats, stats_export

MONTH = "2026-03"


def _person(db, i):
    u = User(
        username=f"st{i}", password_hash=hash_password("x"), role=UserRole.user, is_active=True
    )
    db.add(u)
    db.flush()
    p = PersonProfile(
        user_id=u.id,
        student_no=f"st{i}",
        class_name="一班",
        full_name=f"人{i}",
        phone="13800000000",
        status=PersonStatus.active,
    )
    db.add(p)
    db.flush()
    return p


def _venue(db, code="HL", vtype=VenueType.fixed_shift):
    v = Venue(name=code, code=code, venue_type=vtype, default_required_people=2)
    db.add(v)
    db.flush()
    return v


def _assignment(
    db, plan, venue, person, execution, credited=120, raw=120, weighted=120, balance=120
):
    from decimal import Decimal

    start = datetime(2026, 3, 3, 8, 0)
    slot = DutySlot(
        weekly_plan_id=plan.id,
        venue_id=venue.id,
        source_type=SlotSourceType.fixed_shift,
        slot_start_at=start,
        slot_end_at=start + timedelta(hours=2),
        required_people=1,
        credited_minutes=credited,
        month_key=MONTH,
        status=SlotStatus.filled,
    )
    db.add(slot)
    db.flush()
    a = Assignment(
        duty_slot_id=slot.id,
        person_id=person.id,
        position_index=0,
        plan_status=PlanAssignmentStatus.assigned,
        execution_status=execution,
        raw_minutes=raw,
        weighted_minutes_before_round=Decimal(weighted),
        credited_minutes=credited,
        balance_minutes=balance,
    )
    db.add(a)
    db.flush()
    return a


def _plan(db):
    plan = WeeklyPlan(
        week_start=date(2026, 3, 2),
        week_end=date(2026, 3, 8),
        revision=1,
        status=PlanStatus.published,
    )
    db.add(plan)
    db.flush()
    return plan


def test_recalculate_completed_and_balance(db_session):
    plan = _plan(db_session)
    v = _venue(db_session)
    p = _person(db_session, 0)
    _assignment(db_session, plan, v, p, ExecutionStatus.completed)
    db_session.commit()

    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()
    s = schedule_stats.get_summary(db_session, MONTH, p.id)
    assert s.completed_minutes == 120
    assert s.balance_minutes == 120


def test_absence_zero_completed_balance_preserved(db_session):
    plan = _plan(db_session)
    v = _venue(db_session)
    p = _person(db_session, 0)
    # 未到岗：credited 已被置 0，balance 保留 120
    _assignment(db_session, plan, v, p, ExecutionStatus.absent, credited=0, balance=120)
    db_session.commit()
    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()
    s = schedule_stats.get_summary(db_session, MONTH, p.id)
    assert s.completed_minutes == 0  # 实际完成 0
    assert s.balance_minutes == 120  # 平衡工时保留
    assert s.absence_count == 1


def test_venue_breakdown_dynamic(db_session):
    plan = _plan(db_session)
    v1 = _venue(db_session, "HL")
    v2 = _venue(db_session, "LT", VenueType.event_based)
    p = _person(db_session, 0)
    _assignment(db_session, plan, v1, p, ExecutionStatus.completed)
    _assignment(
        db_session, plan, v2, p, ExecutionStatus.completed, credited=90, raw=60, weighted=90
    )
    db_session.commit()
    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()
    breakdown = {
        b.venue_id: b.completed_minutes
        for b, _venue in schedule_stats.venue_breakdown(db_session, MONTH, p.id)
    }
    assert breakdown[v1.id] == 120
    assert breakdown[v2.id] == 90


def test_lock_prevents_recalc_overwrite(db_session):
    plan = _plan(db_session)
    v = _venue(db_session)
    p = _person(db_session, 0)
    _assignment(db_session, plan, v, p, ExecutionStatus.completed)
    db_session.commit()
    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()
    schedule_stats.lock_month(db_session, actor_id=None, month_key=MONTH)
    db_session.commit()

    s = schedule_stats.get_summary(db_session, MONTH, p.id)
    assert s.status == MonthlySummaryStatus.locked
    # 锁定后重算不覆盖
    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()
    db_session.refresh(s)
    assert s.status == MonthlySummaryStatus.locked


def test_adjustment_affects_completed_and_optionally_balance(db_session):
    plan = _plan(db_session)
    v = _venue(db_session)
    p = _person(db_session, 0)
    _assignment(db_session, plan, v, p, ExecutionStatus.completed)
    db_session.commit()
    schedule_stats.add_adjustment(
        db_session,
        actor_id=None,
        month_key=MONTH,
        person_id=p.id,
        minutes_delta=30,
        affect_balance=True,
        reason="补录",
    )
    db_session.commit()
    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()
    s = schedule_stats.get_summary(db_session, MONTH, p.id)
    assert s.completed_minutes == 150  # 120 + 30
    assert s.balance_minutes == 150


def test_export_produces_xlsx_without_sensitive(db_session):
    plan = _plan(db_session)
    v = _venue(db_session)
    p = _person(db_session, 0)
    _assignment(db_session, plan, v, p, ExecutionStatus.completed)
    db_session.commit()
    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()
    content = stats_export.build_export(db_session, MONTH)
    assert content[:2] == b"PK"  # xlsx(zip) 魔数
    assert len(content) > 0


# --- HTTP 层：admin 月度列表 / 个人明细应携带姓名（脱敏风格一致） ---
def test_monthly_endpoint_returns_names(client, db_session, seed_admin):
    """GET /statistics/monthly/{month} 与 .../people/{pid} 应返回 person_name/class_name/venue_name。"""
    from tests.conftest import csrf_headers, login

    plan = _plan(db_session)
    v = _venue(db_session, "HL")
    p = _person(db_session, 0)
    _assignment(db_session, plan, v, p, ExecutionStatus.completed)
    db_session.commit()
    schedule_stats.recalculate(db_session, MONTH)
    db_session.commit()

    # 复用 client fixture 会覆盖 get_db，但同一 db_session；需重新注入
    # client fixture 已在 conftest 注入 db_session，所以 seed_admin + 数据可见
    token = login(client, "admin", "admin1234")
    h = csrf_headers(token)

    monthly = client.get(f"/api/v1/statistics/monthly/{MONTH}", headers=h).json()
    assert monthly, "应有至少一条汇总"
    row = monthly[0]
    assert row["person_name"] == "人0"
    assert row["student_no"] == "st0"
    assert row["class_name"] == "一班"

    detail = client.get(f"/api/v1/statistics/monthly/{MONTH}/people/{p.id}", headers=h).json()
    assert detail["person_name"] == "人0"
    assert detail["venues"], "应有场地明细"
    assert detail["venues"][0]["venue_name"] == "HL"
