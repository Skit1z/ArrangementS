"""寒暑假与假期可值班白名单（方案 4.8）。"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, TimestampMixin, uuid_pk


class VacationPeriod(Base, TimestampMixin):
    __tablename__ = "vacation_periods"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    semester_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("semesters.id", ondelete="SET NULL"), nullable=True
    )
    # 假期黄楼保留哪些班次模板（默认保留 1 个）。存 shift_template id 列表。
    yellow_shift_template_ids: Mapped[list | None] = mapped_column(JSONBType, nullable=True)
    required_people: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    availabilities: Mapped[list["VacationAvailability"]] = relationship(
        back_populates="vacation_period", cascade="all, delete-orphan"
    )


class VacationAvailability(Base):
    """假期内某人可值班的具体时间段。同一人可多条，保存时合并重叠区间。"""

    __tablename__ = "vacation_availabilities"

    id: Mapped[uuid.UUID] = uuid_pk()
    vacation_period_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vacation_periods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    vacation_period: Mapped["VacationPeriod"] = relationship(back_populates="availabilities")
