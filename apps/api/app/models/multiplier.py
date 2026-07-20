"""倍率规则（方案 2.6）。end_time 为 00:00 表示 24:00（当日结束）。"""

from __future__ import annotations

import uuid
from datetime import date, time
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Time
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONBType, uuid_pk
from app.models.enums import VenueType  # noqa: F401 - 保持 enum 注册顺序稳定


class MultiplierRule(Base):
    __tablename__ = "multiplier_rules"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)  # 00:00 表示 24:00
    multiplier: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    venue_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("venues.id", ondelete="CASCADE"), nullable=True
    )
    weekdays: Mapped[list | None] = mapped_column(JSONBType, nullable=True)  # [1..7]，None=全部
    effective_start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
