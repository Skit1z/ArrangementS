"""人员导入批次记录。"""
from __future__ import annotations

import uuid

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, JSONBType, TimestampMixin, uuid_pk
from app.models.enums import ImportBatchStatus


class ImportBatch(Base, TimestampMixin):
    __tablename__ = "import_batches"

    id: Mapped[uuid.UUID] = uuid_pk()
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[ImportBatchStatus] = mapped_column(
        Enum(ImportBatchStatus, name="import_batch_status"),
        nullable=False,
        default=ImportBatchStatus.previewing,
    )
    total_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # 预览负载（逐行诊断），确认后清理或保留摘要。
    preview_payload: Mapped[dict | None] = mapped_column(JSONBType, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
