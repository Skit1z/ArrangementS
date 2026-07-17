"""阶段七：请假、换班、公开替班报名

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-17
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

leave_status = sa.Enum("pending", "approved", "rejected", "withdrawn", "cancelled", name="leave_status")
swap_mode = sa.Enum("targeted", "open", name="swap_mode")
swap_status = sa.Enum(
    "awaiting_target", "open_collecting", "pending_admin", "approved", "rejected", "withdrawn", "expired",
    name="swap_status",
)
swap_candidate_status = sa.Enum("applied", "selected", "rejected", "expired", name="swap_candidate_status")


def upgrade() -> None:
    op.create_table(
        "leave_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assignment_id", sa.Uuid(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applicant_person_id", sa.Uuid(), sa.ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("attachment_key", sa.String(255), nullable=True),
        sa.Column("is_emergency", sa.Boolean(), nullable=False),
        sa.Column("status", leave_status, nullable=False),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_comment", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_leave_requests_assignment_id", "leave_requests", ["assignment_id"])
    op.create_index("ix_leave_requests_applicant_person_id", "leave_requests", ["applicant_person_id"])

    op.create_table(
        "swap_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("assignment_id", sa.Uuid(), sa.ForeignKey("assignments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_person_id", sa.Uuid(), sa.ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode", swap_mode, nullable=False),
        sa.Column("target_person_id", sa.Uuid(), sa.ForeignKey("person_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("selected_person_id", sa.Uuid(), sa.ForeignKey("person_profiles.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", swap_status, nullable=False),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("reviewer_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_comment", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_swap_requests_assignment_id", "swap_requests", ["assignment_id"])
    op.create_index("ix_swap_requests_requester_person_id", "swap_requests", ["requester_person_id"])

    op.create_table(
        "swap_candidates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("swap_request_id", sa.Uuid(), sa.ForeignKey("swap_requests.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_person_id", sa.Uuid(), sa.ForeignKey("person_profiles.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", swap_candidate_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_swap_candidates_swap_request_id", "swap_candidates", ["swap_request_id"])


def downgrade() -> None:
    op.drop_table("swap_candidates")
    op.drop_table("swap_requests")
    op.drop_table("leave_requests")
    swap_candidate_status.drop(op.get_bind(), checkfirst=True)
    swap_status.drop(op.get_bind(), checkfirst=True)
    swap_mode.drop(op.get_bind(), checkfirst=True)
    leave_status.drop(op.get_bind(), checkfirst=True)
