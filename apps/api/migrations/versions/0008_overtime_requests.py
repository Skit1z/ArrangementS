"""阶段九：加班申请与临时班次

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-19
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Update slot_source_type enum to include 'manual'
    op.execute("ALTER TYPE slot_source_type ADD VALUE IF NOT EXISTS 'manual'")

    # 2. Create overtime_requests table
    op.create_table(
        "overtime_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("venue_id", sa.Uuid(), sa.ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        # use the existing request_status enum
        sa.Column("status", sa.Enum(name="request_status", create_type=False), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("generated_slot_id", sa.Uuid(), sa.ForeignKey("duty_slots.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )
    op.create_index("ix_overtime_requests_person_id", "overtime_requests", ["person_id"])


def downgrade() -> None:
    op.drop_table("overtime_requests")
    # Removing enum value is not supported out-of-the-box in Postgres cleanly, so we skip it.
