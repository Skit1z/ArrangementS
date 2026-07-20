"""人员档案。敏感字段（身份证号 / 银行卡号）密文保存，仅额外存后四位。"""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Enum, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, uuid_pk
from app.models.enums import PersonStatus


class PersonProfile(Base, TimestampMixin):
    __tablename__ = "person_profiles"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False
    )
    student_no: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    class_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(32), nullable=False)
    difficulty_level: Mapped[str | None] = mapped_column(String(32), nullable=True)

    id_card_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    id_card_last4: Mapped[str | None] = mapped_column(String(8), nullable=True)
    bank_card_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    bank_card_last4: Mapped[str | None] = mapped_column(String(8), nullable=True)

    status: Mapped[PersonStatus] = mapped_column(
        Enum(PersonStatus, name="person_status"),
        nullable=False,
        default=PersonStatus.active,
        index=True,
    )
    is_in_scheduling_pool: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    user: Mapped["User"] = relationship(back_populates="profile")  # noqa: F821
