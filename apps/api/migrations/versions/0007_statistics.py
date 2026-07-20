"""阶段八：月度工时统计、分场地统计、工时调整

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

monthly_summary_status = sa.Enum(
    "calculating", "draft", "confirmed", "locked", name="monthly_summary_status"
)


def upgrade() -> None:
    op.create_table(
        "monthly_hour_summaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("balance_minutes", sa.Integer(), nullable=False),
        sa.Column("completed_minutes", sa.Integer(), nullable=False),
        sa.Column("multiplier_extra_minutes", sa.Integer(), nullable=False),
        sa.Column("leave_count", sa.Integer(), nullable=False),
        sa.Column("swap_out_count", sa.Integer(), nullable=False),
        sa.Column("replacement_count", sa.Integer(), nullable=False),
        sa.Column("absence_count", sa.Integer(), nullable=False),
        sa.Column("status", monthly_summary_status, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("person_id", "month", name="uq_person_month"),
    )
    op.create_index("ix_monthly_hour_summaries_person_id", "monthly_hour_summaries", ["person_id"])
    op.create_index("ix_monthly_hour_summaries_month", "monthly_hour_summaries", ["month"])

    op.create_table(
        "monthly_venue_hour_summaries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column(
            "venue_id", sa.Uuid(), sa.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("completed_minutes", sa.Integer(), nullable=False),
        sa.Column("balance_minutes", sa.Integer(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("person_id", "month", "venue_id", name="uq_person_month_venue"),
    )
    op.create_index(
        "ix_monthly_venue_hour_summaries_person_id", "monthly_venue_hour_summaries", ["person_id"]
    )

    op.create_table(
        "hour_adjustments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("month", sa.Date(), nullable=False),
        sa.Column("minutes_delta", sa.Integer(), nullable=False),
        sa.Column("affect_balance", sa.Boolean(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("source_assignment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_hour_adjustments_person_id", "hour_adjustments", ["person_id"])
    op.create_index("ix_hour_adjustments_month", "hour_adjustments", ["month"])


def downgrade() -> None:
    op.drop_table("hour_adjustments")
    op.drop_table("monthly_venue_hour_summaries")
    op.drop_index("ix_monthly_hour_summaries_month", table_name="monthly_hour_summaries")
    op.drop_index("ix_monthly_hour_summaries_person_id", table_name="monthly_hour_summaries")
    op.drop_table("monthly_hour_summaries")
    monthly_summary_status.drop(op.get_bind(), checkfirst=True)
