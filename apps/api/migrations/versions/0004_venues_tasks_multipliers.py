"""阶段四：场地/班次模板、特殊日期、临时任务、倍率规则

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

venue_type = sa.Enum("fixed_shift", "event_based", name="venue_type")
day_type = sa.Enum("workday", "weekend_rule", "closed", "custom", name="day_type")
special_date_source = sa.Enum("manual", "holiday_sync", name="special_date_source")
task_status = sa.Enum(
    "draft", "confirmed", "scheduled", "executing", "completed", "cancelled", name="task_status"
)


def upgrade() -> None:
    op.create_table(
        "venues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("code", sa.String(32), nullable=False, unique=True),
        sa.Column("venue_type", venue_type, nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("default_required_people", sa.Integer(), nullable=False),
        sa.Column("default_prep_minutes", sa.Integer(), nullable=False),
        sa.Column("default_cleanup_minutes", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("description", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "shift_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "venue_id", sa.Uuid(), sa.ForeignKey("venues.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("credited_minutes", sa.Integer(), nullable=False),
        sa.Column("weekday_required_people", sa.Integer(), nullable=False),
        sa.Column("weekend_required_people", sa.Integer(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_shift_templates_venue_id", "shift_templates", ["venue_id"])

    op.create_table(
        "special_dates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("day_type", day_type, nullable=False),
        sa.Column("custom_required_people", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("source", special_date_source, nullable=False),
        sa.Column(
            "confirmed_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_special_dates_date", "special_dates", ["date"], unique=True)

    op.create_table(
        "venue_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "venue_id", sa.Uuid(), sa.ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("title", sa.String(128), nullable=False),
        sa.Column("booking_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("booking_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("prep_minutes", sa.Integer(), nullable=False),
        sa.Column("cleanup_minutes", sa.Integer(), nullable=False),
        sa.Column("duty_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duty_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_people", sa.Integer(), nullable=False),
        sa.Column("organization", sa.String(128), nullable=True),
        sa.Column("contact_name", sa.String(64), nullable=True),
        sa.Column("contact_phone", sa.String(32), nullable=True),
        sa.Column("requirements", sa.String(512), nullable=True),
        sa.Column("notes", sa.String(512), nullable=True),
        sa.Column("is_temporary", sa.Boolean(), nullable=False),
        sa.Column("status", task_status, nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_venue_tasks_venue_id", "venue_tasks", ["venue_id"])
    op.create_index("ix_venue_tasks_duty_start_at", "venue_tasks", ["duty_start_at"])
    op.create_index("ix_venue_tasks_duty_end_at", "venue_tasks", ["duty_end_at"])

    op.create_table(
        "multiplier_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("multiplier", sa.Numeric(4, 2), nullable=False),
        sa.Column(
            "venue_id", sa.Uuid(), sa.ForeignKey("venues.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("weekdays", postgresql.JSONB(), nullable=True),
        sa.Column("effective_start_date", sa.Date(), nullable=True),
        sa.Column("effective_end_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("multiplier_rules")
    op.drop_table("venue_tasks")
    op.drop_index("ix_special_dates_date", table_name="special_dates")
    op.drop_table("special_dates")
    op.drop_table("shift_templates")
    op.drop_table("venues")
    task_status.drop(op.get_bind(), checkfirst=True)
    special_date_source.drop(op.get_bind(), checkfirst=True)
    day_type.drop(op.get_bind(), checkfirst=True)
    venue_type.drop(op.get_bind(), checkfirst=True)
