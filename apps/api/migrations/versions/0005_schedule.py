"""阶段五：周排班计划、岗位、人员分配

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

plan_status = sa.Enum("draft", "published", "archived", name="plan_status")
slot_source_type = sa.Enum("fixed_shift", "venue_task", name="slot_source_type")
slot_status = sa.Enum("open", "filled", "cancelled", name="slot_status")
assignment_source = sa.Enum(
    "auto", "manual", "swap", "replacement", "forced", name="assignment_source"
)
plan_assignment_status = sa.Enum(
    "pending", "assigned", "vacant", "replaced", "cancelled", name="plan_assignment_status"
)
execution_status = sa.Enum(
    "pending", "completed", "absent", "leave", "swapped", "task_cancelled", name="execution_status"
)


def upgrade() -> None:
    op.create_table(
        "weekly_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("week_start", sa.Date(), nullable=False, unique=True),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("status", plan_status, nullable=False),
        sa.Column("algorithm_version", sa.String(32), nullable=True),
        sa.Column("random_seed", sa.Integer(), nullable=True),
        sa.Column(
            "generated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "published_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_weekly_plans_week_start", "weekly_plans", ["week_start"], unique=True)

    op.create_table(
        "duty_slots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "weekly_plan_id",
            sa.Uuid(),
            sa.ForeignKey("weekly_plans.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "venue_id", sa.Uuid(), sa.ForeignKey("venues.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("source_type", slot_source_type, nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=True),
        sa.Column("slot_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("slot_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("required_people", sa.Integer(), nullable=False),
        sa.Column("credited_minutes", sa.Integer(), nullable=False),
        sa.Column("month_key", sa.String(7), nullable=False),
        sa.Column("status", slot_status, nullable=False),
        sa.Column("is_locked", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_duty_slots_weekly_plan_id", "duty_slots", ["weekly_plan_id"])
    op.create_index("ix_duty_slots_slot_start_at", "duty_slots", ["slot_start_at"])
    op.create_index("ix_duty_slots_slot_end_at", "duty_slots", ["slot_end_at"])
    op.create_index("ix_duty_slots_month_key", "duty_slots", ["month_key"])

    op.create_table(
        "assignments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "duty_slot_id",
            sa.Uuid(),
            sa.ForeignKey("duty_slots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("position_index", sa.Integer(), nullable=False),
        sa.Column("assignment_source", assignment_source, nullable=False),
        sa.Column("plan_status", plan_assignment_status, nullable=False),
        sa.Column("execution_status", execution_status, nullable=False),
        sa.Column("raw_minutes", sa.Integer(), nullable=False),
        sa.Column("weighted_minutes_before_round", sa.Numeric(8, 2), nullable=False),
        sa.Column("credited_minutes", sa.Integer(), nullable=False),
        sa.Column("balance_minutes", sa.Integer(), nullable=False),
        sa.Column("forced_reason", sa.String(255), nullable=True),
        sa.Column("replaced_assignment_id", sa.Uuid(), nullable=True),
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
        sa.UniqueConstraint("duty_slot_id", "position_index", name="uq_slot_position"),
    )
    op.create_index("ix_assignments_duty_slot_id", "assignments", ["duty_slot_id"])
    op.create_index("ix_assignments_person_id", "assignments", ["person_id"])


def downgrade() -> None:
    op.drop_table("assignments")
    op.drop_table("duty_slots")
    op.drop_index("ix_weekly_plans_week_start", table_name="weekly_plans")
    op.drop_table("weekly_plans")
    execution_status.drop(op.get_bind(), checkfirst=True)
    plan_assignment_status.drop(op.get_bind(), checkfirst=True)
    assignment_source.drop(op.get_bind(), checkfirst=True)
    slot_status.drop(op.get_bind(), checkfirst=True)
    slot_source_type.drop(op.get_bind(), checkfirst=True)
    plan_status.drop(op.get_bind(), checkfirst=True)
