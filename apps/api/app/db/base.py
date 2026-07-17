"""SQLAlchemy 2.0 声明式基类与通用列类型约定。"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# 生产（Postgres）使用 JSONB，其他方言（如测试用 SQLite）回退到通用 JSON。
JSONBType = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """所有 ORM 模型的基类。"""


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
