"""system_settings table for runtime K-V config

Revision ID: 0009_system_settings
Revises: 0008_overtime_requests
Create Date: 2026-07-21 17:30:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_system_settings"
down_revision = "0008_overtime_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(64), primary_key=True),
        sa.Column("value", sa.String(512), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column("updated_at", sa.String(64), nullable=True),
    )
    # 默认寒暑假 6 周
    op.execute(
        "INSERT INTO system_settings (key, value, description) VALUES "
        "('trailing_vacation_weeks', '6', '学期结束后自动寒暑假默认周数（5-8）') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("system_settings")
