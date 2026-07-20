"""月度工时统计（方案 11 / 12.1）。分场地按维度存储，新增场地无需改表结构。"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
from app.models.enums import MonthlySummaryStatus


class MonthlyHourSummary(Base):
    __tablename__ = "monthly_hour_summaries"
    __table_args__ = (UniqueConstraint("person_id", "month", name="uq_person_month"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    month: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # 当月 1 号
    balance_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completed_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    multiplier_extra_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    leave_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    swap_out_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    replacement_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    absence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[MonthlySummaryStatus] = mapped_column(
        Enum(MonthlySummaryStatus, name="monthly_summary_status"),
        nullable=False,
        default=MonthlySummaryStatus.draft,
    )
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class MonthlyVenueHourSummary(Base):
    __tablename__ = "monthly_venue_hour_summaries"
    __table_args__ = (
        UniqueConstraint("person_id", "month", "venue_id", name="uq_person_month_venue"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    month: Mapped[date] = mapped_column(Date, nullable=False)
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
    )
    completed_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HourAdjustment(Base):
    __tablename__ = "hour_adjustments"

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    month: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    minutes_delta: Mapped[int] = mapped_column(Integer, nullable=False)
    affect_balance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    source_assignment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
