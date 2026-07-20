"""阶段二：学期/课程时间/教学楼映射、个人约束、假期与假期可值班名单

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

building_type = sa.Enum("all", "main", "second", name="building_type")


def upgrade() -> None:
    op.create_table(
        "semesters",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("first_monday", sa.Date(), nullable=False),
        sa.Column("week_count", sa.Integer(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("course_buffer_enabled", sa.Boolean(), nullable=False),
        sa.Column("course_buffer_minutes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_semesters_is_current", "semesters", ["is_current"])

    op.create_table(
        "course_period_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "semester_id",
            sa.Uuid(),
            sa.ForeignKey("semesters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_group", sa.String(16), nullable=False),
        sa.Column("building_type", building_type, nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_course_period_rules_semester_id", "course_period_rules", ["semester_id"])

    op.create_table(
        "building_code_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "semester_id",
            sa.Uuid(),
            sa.ForeignKey("semesters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prefix", sa.String(16), nullable=False),
        sa.Column("building_type", building_type, nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_building_code_rules_semester_id", "building_code_rules", ["semester_id"])

    op.create_table(
        "person_constraints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("constraint_type", sa.String(64), nullable=False),
        sa.Column("constraint_value", postgresql.JSONB(), nullable=True),
        sa.Column("is_hard", sa.Boolean(), nullable=False),
        sa.Column("effective_start", sa.Date(), nullable=True),
        sa.Column("effective_end", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_person_constraints_person_id", "person_constraints", ["person_id"])

    op.create_table(
        "vacation_periods",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column(
            "semester_id",
            sa.Uuid(),
            sa.ForeignKey("semesters.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("yellow_shift_template_ids", postgresql.JSONB(), nullable=True),
        sa.Column("required_people", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )

    op.create_table(
        "vacation_availabilities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "vacation_period_id",
            sa.Uuid(),
            sa.ForeignKey("vacation_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column(
            "created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index(
        "ix_vacation_availabilities_vacation_period_id",
        "vacation_availabilities",
        ["vacation_period_id"],
    )
    op.create_index(
        "ix_vacation_availabilities_person_id", "vacation_availabilities", ["person_id"]
    )


def downgrade() -> None:
    op.drop_table("vacation_availabilities")
    op.drop_table("vacation_periods")
    op.drop_table("person_constraints")
    op.drop_table("building_code_rules")
    op.drop_table("course_period_rules")
    op.drop_index("ix_semesters_is_current", table_name="semesters")
    op.drop_table("semesters")
    building_type.drop(op.get_bind(), checkfirst=True)
