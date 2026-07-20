"""特殊日期（节假日/调休/停班/自定义）。方案 2.2 / 2.9 / 12.1。"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, uuid_pk
from app.models.enums import DayType, SpecialDateSource


class SpecialDate(Base):
    __tablename__ = "special_dates"

    id: Mapped[uuid.UUID] = uuid_pk()
    date: Mapped[date] = mapped_column(Date, unique=True, nullable=False, index=True)
    day_type: Mapped[DayType] = mapped_column(Enum(DayType, name="day_type"), nullable=False)
    custom_required_people: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[SpecialDateSource] = mapped_column(
        Enum(SpecialDateSource, name="special_date_source"),
        nullable=False,
        default=SpecialDateSource.manual,
    )
    confirmed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
