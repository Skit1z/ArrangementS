"""蓝厅 / 图书馆报告厅临时任务（方案 7.2）。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import TaskStatus


class VenueTask(Base, TimestampMixin):
    __tablename__ = "venue_tasks"

    id: Mapped[uuid.UUID] = uuid_pk()
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    booking_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    booking_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    prep_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    cleanup_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    duty_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    duty_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    required_people: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    organization: Mapped[str | None] = mapped_column(String(128), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    requirements: Mapped[str | None] = mapped_column(String(512), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(512), nullable=True)
    is_temporary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status"), nullable=False, default=TaskStatus.draft
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
