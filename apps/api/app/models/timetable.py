"""课表上传与解析出的课程规则（方案 4.4 / 4.5 / 12.1）。"""
from __future__ import annotations

import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Time,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, JSONBType, TimestampMixin, uuid_pk
from app.models.enums import BuildingType, ParseStatus, ReviewStatus


class TimetableUpload(Base, TimestampMixin):
    __tablename__ = "timetable_uploads"

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    semester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("semesters.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    uploader_user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    parse_status: Mapped[ParseStatus] = mapped_column(
        Enum(ParseStatus, name="parse_status"), nullable=False, default=ParseStatus.pending
    )
    review_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_status"), nullable=False, default=ReviewStatus.draft
    )
    parser_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    course_rules: Mapped[list["CourseRule"]] = relationship(
        back_populates="upload", cascade="all, delete-orphan"
    )


class CourseRule(Base):
    __tablename__ = "course_rules"

    id: Mapped[uuid.UUID] = uuid_pk()
    timetable_upload_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("timetable_uploads.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=周一 .. 7=周日
    period_start: Mapped[int] = mapped_column(Integer, nullable=False)
    period_end: Mapped[int] = mapped_column(Integer, nullable=False)
    week_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    week_parity: Mapped[str] = mapped_column(String(8), nullable=False, default="all")
    explicit_weeks: Mapped[list | None] = mapped_column(JSONBType, nullable=True)
    location_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    building_type: Mapped[BuildingType | None] = mapped_column(
        Enum(BuildingType, name="building_type"), nullable=True
    )
    start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    upload: Mapped["TimetableUpload"] = relationship(back_populates="course_rules")
