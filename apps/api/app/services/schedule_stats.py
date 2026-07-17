"""月度工时统计（方案 11 / 2.5）。

- 排班平衡工时(balance)：用于公平；请假移出=0、未到岗保留。
- 实际完成工时(completed)：完成计入；请假/未到岗/取消=0。
- 分场地按 venue 维度动态统计，不硬编码具体场地。
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    ExecutionStatus,
    MonthlySummaryStatus,
    SwapStatus,
)
from app.models.schedule import Assignment, DutySlot
from app.models.statistics import (
    HourAdjustment,
    MonthlyHourSummary,
    MonthlyVenueHourSummary,
)
from app.models.swap import SwapRequest
from app.services.audit_service import record_audit


def month_to_date(month_key: str) -> date:
    year, month = month_key.split("-")
    return date(int(year), int(month), 1)


def _assignments_in_month(db: Session, month_key: str):
    return db.execute(
        select(Assignment, DutySlot)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(DutySlot.month_key == month_key, Assignment.person_id.isnot(None))
    ).all()


def recalculate(db: Session, month_key: str) -> int:
    """重算某月统计。已锁定的人员汇总跳过（方案 11.2）。返回处理人数。"""
    month = month_to_date(month_key)
    rows = _assignments_in_month(db, month_key)

    # person -> 聚合
    agg: dict[uuid.UUID, dict] = {}
    venue_agg: dict[tuple[uuid.UUID, uuid.UUID], dict] = {}
    for a, slot in rows:
        pid = a.person_id
        rec = agg.setdefault(pid, dict(balance=0, completed=0, extra=0, leave=0, absence=0))
        rec["balance"] += a.balance_minutes
        completed = a.credited_minutes if a.execution_status == ExecutionStatus.completed else 0
        rec["completed"] += completed
        if a.credited_minutes > a.raw_minutes:
            rec["extra"] += a.credited_minutes - a.raw_minutes
        if a.execution_status == ExecutionStatus.absent:
            rec["absence"] += 1
        if a.execution_status == ExecutionStatus.leave:
            rec["leave"] += 1
        vkey = (pid, slot.venue_id)
        vrec = venue_agg.setdefault(vkey, dict(completed=0, balance=0))
        vrec["completed"] += completed
        vrec["balance"] += a.balance_minutes

    _apply_swap_counts(db, month_key, agg)
    _apply_adjustments(db, month, agg)

    now = datetime.now(timezone.utc)
    processed = 0
    for pid, rec in agg.items():
        summary = db.scalar(
            select(MonthlyHourSummary).where(
                MonthlyHourSummary.person_id == pid, MonthlyHourSummary.month == month
            )
        )
        if summary is not None and summary.status == MonthlySummaryStatus.locked:
            continue
        if summary is None:
            summary = MonthlyHourSummary(person_id=pid, month=month)
            db.add(summary)
        summary.balance_minutes = rec["balance"]
        summary.completed_minutes = rec["completed"]
        summary.multiplier_extra_minutes = rec["extra"]
        summary.leave_count = rec["leave"]
        summary.absence_count = rec["absence"]
        summary.swap_out_count = rec.get("swap_out", 0)
        summary.replacement_count = rec.get("replacement", 0)
        summary.status = MonthlySummaryStatus.draft
        summary.calculated_at = now
        processed += 1

    _write_venue_summaries(db, month, venue_agg, now)
    db.flush()
    return processed


def _apply_swap_counts(db: Session, month_key: str, agg: dict) -> None:
    approved = db.execute(
        select(SwapRequest, DutySlot)
        .join(Assignment, SwapRequest.assignment_id == Assignment.id)
        .join(DutySlot, Assignment.duty_slot_id == DutySlot.id)
        .where(SwapRequest.status == SwapStatus.approved, DutySlot.month_key == month_key)
    ).all()
    for swap, _slot in approved:
        out = agg.setdefault(swap.requester_person_id, dict(balance=0, completed=0, extra=0, leave=0, absence=0))
        out["swap_out"] = out.get("swap_out", 0) + 1
        if swap.selected_person_id is not None:
            rep = agg.setdefault(swap.selected_person_id, dict(balance=0, completed=0, extra=0, leave=0, absence=0))
            rep["replacement"] = rep.get("replacement", 0) + 1


def _apply_adjustments(db: Session, month: date, agg: dict) -> None:
    rows = db.scalars(select(HourAdjustment).where(HourAdjustment.month == month))
    for adj in rows:
        rec = agg.setdefault(adj.person_id, dict(balance=0, completed=0, extra=0, leave=0, absence=0))
        rec["completed"] += adj.minutes_delta
        if adj.affect_balance:
            rec["balance"] += adj.minutes_delta


def _write_venue_summaries(db: Session, month: date, venue_agg: dict, now: datetime) -> None:
    for (pid, vid), vrec in venue_agg.items():
        row = db.scalar(
            select(MonthlyVenueHourSummary).where(
                MonthlyVenueHourSummary.person_id == pid,
                MonthlyVenueHourSummary.month == month,
                MonthlyVenueHourSummary.venue_id == vid,
            )
        )
        if row is None:
            row = MonthlyVenueHourSummary(person_id=pid, month=month, venue_id=vid)
            db.add(row)
        row.completed_minutes = vrec["completed"]
        row.balance_minutes = vrec["balance"]
        row.calculated_at = now


def lock_month(db: Session, actor_id: uuid.UUID | None, month_key: str) -> int:
    month = month_to_date(month_key)
    now = datetime.now(timezone.utc)
    rows = list(db.scalars(select(MonthlyHourSummary).where(MonthlyHourSummary.month == month)))
    for s in rows:
        s.status = MonthlySummaryStatus.locked
        s.locked_at = now
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="statistics.lock",
        entity_type="monthly_summary", entity_id=month_key,
    )
    return len(rows)


def add_adjustment(
    db: Session, *, actor_id: uuid.UUID | None, month_key: str, person_id: uuid.UUID,
    minutes_delta: int, affect_balance: bool, reason: str,
) -> HourAdjustment:
    month = month_to_date(month_key)
    adj = HourAdjustment(
        person_id=person_id, month=month, minutes_delta=minutes_delta,
        affect_balance=affect_balance, reason=reason, created_by=actor_id,
    )
    db.add(adj)
    db.flush()
    record_audit(
        db, actor_user_id=actor_id, action="statistics.adjust",
        entity_type="hour_adjustment", entity_id=adj.id,
        after_data={"person_id": str(person_id), "minutes_delta": minutes_delta},
    )
    return adj


def list_monthly(db: Session, month_key: str) -> list[MonthlyHourSummary]:
    month = month_to_date(month_key)
    return list(
        db.scalars(
            select(MonthlyHourSummary)
            .where(MonthlyHourSummary.month == month)
            .order_by(MonthlyHourSummary.person_id)
        )
    )


def venue_breakdown(db: Session, month_key: str, person_id: uuid.UUID) -> list[MonthlyVenueHourSummary]:
    month = month_to_date(month_key)
    return list(
        db.scalars(
            select(MonthlyVenueHourSummary).where(
                MonthlyVenueHourSummary.month == month,
                MonthlyVenueHourSummary.person_id == person_id,
            )
        )
    )


def get_summary(db: Session, month_key: str, person_id: uuid.UUID) -> MonthlyHourSummary:
    month = month_to_date(month_key)
    s = db.scalar(
        select(MonthlyHourSummary).where(
            MonthlyHourSummary.month == month, MonthlyHourSummary.person_id == person_id
        )
    )
    if s is None:
        raise HTTPException(status_code=404, detail="该月该人员统计不存在，请先重算")
    return s
