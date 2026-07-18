"""加班申请模块。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import RequestStatus


class OvertimeRequest(Base, TimestampMixin):
    __tablename__ = "overtime_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, name="request_status"), nullable=False, default=RequestStatus.pending
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    generated_slot_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("duty_slots.id", ondelete="SET NULL"), nullable=True
    )

    person: Mapped["PersonProfile"] = relationship()
    venue: Mapped["Venue"] = relationship()
    reviewer: Mapped["User"] = relationship()
    generated_slot: Mapped["DutySlot"] = relationship()
