"""系统级配置项 (K-V)，用于存储运行期可调整的参数。"""

from __future__ import annotations

import uuid

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemSetting(Base):
    """系统配置表 - 运行时可调整的参数。"""

    __tablename__ = "system_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[uuid.UUID | None] = mapped_column(nullable=True)
