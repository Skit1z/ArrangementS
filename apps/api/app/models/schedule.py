"""周排班计划、岗位与人员分配（方案 7.3 / 7.4 / 12.1）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import (
    AssignmentSource,
    ExecutionStatus,
    PlanAssignmentStatus,
    PlanStatus,
    SlotSourceType,
    SlotStatus,
)


class WeeklyPlan(Base, TimestampMixin):
    __tablename__ = "weekly_plans"

    id: Mapped[uuid.UUID] = uuid_pk()
    week_start: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus, name="plan_status"), nullable=False, default=PlanStatus.draft
    )
    algorithm_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    random_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    slots: Mapped[list["DutySlot"]] = relationship(
        back_populates="plan", cascade="all, delete-orphan"
    )


class DutySlot(Base):
    """统一表示黄楼班次岗位与场地任务岗位。"""

    __tablename__ = "duty_slots"

    id: Mapped[uuid.UUID] = uuid_pk()
    weekly_plan_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("weekly_plans.id", ondelete="CASCADE"), nullable=False, index=True
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False
    )
    source_type: Mapped[SlotSourceType] = mapped_column(
        Enum(SlotSourceType, name="slot_source_type"), nullable=False
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        nullable=True
    )  # shift_template 或 venue_task id
    slot_start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    slot_end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    required_people: Mapped[int] = mapped_column(Integer, nullable=False)
    credited_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    month_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus, name="slot_status"), nullable=False, default=SlotStatus.open
    )
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    plan: Mapped["WeeklyPlan"] = relationship(back_populates="slots")
    assignments: Mapped[list["Assignment"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )


class Assignment(Base, TimestampMixin):
    __tablename__ = "assignments"
    __table_args__ = (UniqueConstraint("duty_slot_id", "position_index", name="uq_slot_position"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    duty_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("duty_slots.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    position_index: Mapped[int] = mapped_column(Integer, nullable=False)
    assignment_source: Mapped[AssignmentSource] = mapped_column(
        Enum(AssignmentSource, name="assignment_source"),
        nullable=False,
        default=AssignmentSource.auto,
    )
    plan_status: Mapped[PlanAssignmentStatus] = mapped_column(
        Enum(PlanAssignmentStatus, name="plan_assignment_status"),
        nullable=False,
        default=PlanAssignmentStatus.pending,
    )
    execution_status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status"),
        nullable=False,
        default=ExecutionStatus.pending,
    )
    raw_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    weighted_minutes_before_round: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, default=0
    )
    credited_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    balance_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    forced_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    replaced_assignment_id: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    slot: Mapped["DutySlot"] = relationship(back_populates="assignments")
