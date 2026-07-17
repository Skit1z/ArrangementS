"""学期、课程节次时间、教学楼代码映射（方案 4.1 / 4.2）。"""
from __future__ import annotations

import uuid
from datetime import date, time

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import BuildingType


class Semester(Base, TimestampMixin):
    __tablename__ = "semesters"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    first_monday: Mapped[date] = mapped_column(Date, nullable=False)
    week_count: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    course_buffer_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    course_buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=10)

    period_rules: Mapped[list["CoursePeriodRule"]] = relationship(
        back_populates="semester", cascade="all, delete-orphan"
    )
    building_rules: Mapped[list["BuildingCodeRule"]] = relationship(
        back_populates="semester", cascade="all, delete-orphan"
    )


class CoursePeriodRule(Base):
    """某学期下“节次组 + 教学楼类型 -> 时间段”的映射。"""

    __tablename__ = "course_period_rules"

    id: Mapped[uuid.UUID] = uuid_pk()
    semester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period_group: Mapped[str] = mapped_column(String(16), nullable=False)  # 如 "1-2"
    building_type: Mapped[BuildingType] = mapped_column(
        Enum(BuildingType, name="building_type"), nullable=False
    )
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    semester: Mapped["Semester"] = relationship(back_populates="period_rules")


class BuildingCodeRule(Base):
    """教室代码前缀 -> 教学楼类型。"""

    __tablename__ = "building_code_rules"

    id: Mapped[uuid.UUID] = uuid_pk()
    semester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semesters.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    building_type: Mapped[BuildingType] = mapped_column(
        Enum(BuildingType, name="building_type"), nullable=False
    )
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    semester: Mapped["Semester"] = relationship(back_populates="building_rules")
