"""换班申请与公开替班报名（方案 6.2 / 12.1）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import SwapCandidateStatus, SwapMode, SwapStatus


class SwapRequest(Base, TimestampMixin):
    __tablename__ = "swap_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    assignment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    requester_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mode: Mapped[SwapMode] = mapped_column(Enum(SwapMode, name="swap_mode"), nullable=False)
    target_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="SET NULL"), nullable=True
    )
    selected_person_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[SwapStatus] = mapped_column(
        Enum(SwapStatus, name="swap_status"), nullable=False
    )
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_comment: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    candidates: Mapped[list["SwapCandidate"]] = relationship(
        back_populates="swap_request", cascade="all, delete-orphan"
    )


class SwapCandidate(Base):
    __tablename__ = "swap_candidates"

    id: Mapped[uuid.UUID] = uuid_pk()
    swap_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("swap_requests.id", ondelete="CASCADE"), nullable=False, index=True
    )
    candidate_person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[SwapCandidateStatus] = mapped_column(
        Enum(SwapCandidateStatus, name="swap_candidate_status"),
        nullable=False,
        default=SwapCandidateStatus.applied,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    swap_request: Mapped["SwapRequest"] = relationship(back_populates="candidates")
