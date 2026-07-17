"""场地与黄楼固定班次模板（方案 7.1 / 2.2）。"""
from __future__ import annotations

import uuid
from datetime import time

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import VenueType


class Venue(Base, TimestampMixin):
    __tablename__ = "venues"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    venue_type: Mapped[VenueType] = mapped_column(
        Enum(VenueType, name="venue_type"), nullable=False
    )
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_required_people: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    default_prep_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    default_cleanup_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)

    shift_templates: Mapped[list["ShiftTemplate"]] = relationship(
        back_populates="venue", cascade="all, delete-orphan"
    )


class ShiftTemplate(Base):
    """黄楼固定班次模板。credited_minutes 为固定统计工时（不倍率、不取整）。"""

    __tablename__ = "shift_templates"

    id: Mapped[uuid.UUID] = uuid_pk()
    venue_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    credited_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    weekday_required_people: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    weekend_required_people: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    venue: Mapped["Venue"] = relationship(back_populates="shift_templates")
