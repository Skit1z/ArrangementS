"""个人排班约束（方案 5.3）。强制/偏好统一存储，类型 + JSON 值。"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONBType, TimestampMixin, uuid_pk


class PersonConstraint(Base, TimestampMixin):
    __tablename__ = "person_constraints"

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 如 suspend / weekly_limit / forbid_venue / forbid_weekday / forbid_date /
    #    forbid_time / no_pair_with / only_venue / prefer_weekday ...
    constraint_type: Mapped[str] = mapped_column(String(64), nullable=False)
    constraint_value: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    is_hard: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    effective_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
