"""阶段三：课表上传/课程规则、不可值班区间与申请

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

parse_status = sa.Enum("pending", "parsing", "parsed", "failed", name="parse_status")
review_status = sa.Enum(
    "draft", "pending", "approved", "rejected", "superseded", name="review_status"
)
availability_source = sa.Enum(
    "course", "user_request", "admin", "leave", "suspension", name="availability_source"
)
availability_status = sa.Enum("active", "expired", name="availability_status")
request_status = sa.Enum(
    "pending", "approved", "rejected", "withdrawn", "expired", name="request_status"
)
# building_type 已在 0002 创建；此处复用（create_type=False 避免重复创建）
building_type = postgresql.ENUM("all", "main", "second", name="building_type", create_type=False)


def upgrade() -> None:
    op.create_table(
        "timetable_uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "semester_id",
            sa.Uuid(),
            sa.ForeignKey("semesters.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "uploader_user_id",
            sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(255), nullable=True),
        sa.Column("file_hash", sa.String(128), nullable=True),
        sa.Column("parse_status", parse_status, nullable=False),
        sa.Column("review_status", review_status, nullable=False),
        sa.Column("parser_version", sa.String(32), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_timetable_uploads_person_id", "timetable_uploads", ["person_id"])
    op.create_index("ix_timetable_uploads_semester_id", "timetable_uploads", ["semester_id"])

    op.create_table(
        "course_rules",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "timetable_upload_id",
            sa.Uuid(),
            sa.ForeignKey("timetable_uploads.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("course_name", sa.String(128), nullable=True),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("period_start", sa.Integer(), nullable=False),
        sa.Column("period_end", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Integer(), nullable=True),
        sa.Column("week_end", sa.Integer(), nullable=True),
        sa.Column("week_parity", sa.String(8), nullable=False),
        sa.Column("explicit_weeks", postgresql.JSONB(), nullable=True),
        sa.Column("location_code", sa.String(32), nullable=True),
        sa.Column("building_type", building_type, nullable=True),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("confidence", sa.Numeric(4, 3), nullable=True),
        sa.Column("needs_review", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_course_rules_timetable_upload_id", "course_rules", ["timetable_upload_id"])

    op.create_table(
        "availability_blocks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", availability_source, nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", availability_status, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("source_ref_id", sa.Uuid(), nullable=True),
        sa.Column(
            "approved_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_availability_blocks_person_id", "availability_blocks", ["person_id"])
    op.create_index("ix_availability_blocks_start_at", "availability_blocks", ["start_at"])
    op.create_index("ix_availability_blocks_end_at", "availability_blocks", ["end_at"])

    op.create_table(
        "availability_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "person_id",
            sa.Uuid(),
            sa.ForeignKey("person_profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recurrence_rule", sa.String(64), nullable=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("status", request_status, nullable=False),
        sa.Column(
            "reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("review_comment", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_availability_requests_person_id", "availability_requests", ["person_id"])


def downgrade() -> None:
    op.drop_table("availability_requests")
    op.drop_table("availability_blocks")
    op.drop_table("course_rules")
    op.drop_table("timetable_uploads")
    request_status.drop(op.get_bind(), checkfirst=True)
    availability_status.drop(op.get_bind(), checkfirst=True)
    availability_source.drop(op.get_bind(), checkfirst=True)
    review_status.drop(op.get_bind(), checkfirst=True)
    parse_status.drop(op.get_bind(), checkfirst=True)
