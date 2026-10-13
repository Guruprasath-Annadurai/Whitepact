# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Cloud — durable admin grants and employee lifecycle.

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ts = sa.DateTime(timezone=True)
    op.create_table(
        "cloud_employees",
        sa.Column("employee_id", sa.String(length=128), primary_key=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("updated_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "status IN ('active', 'suspended', 'terminated')",
            name="chk_cloud_employee_status",
        ),
    )
    op.create_table(
        "cloud_admin_grant_claims",
        sa.Column("grant_id", sa.String(length=64), primary_key=True),
        sa.Column("employee_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("role", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=128), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("resource_target", sa.String(length=256), nullable=False),
        sa.Column("permissions_json", sa.Text(), nullable=False),
        sa.Column("policy_id", sa.String(length=128), nullable=False),
        sa.Column("approved_by", sa.String(length=128), nullable=True),
        sa.Column("execution_id", sa.String(length=64), nullable=False, unique=True),
        sa.Column("audit_correlation_id", sa.String(length=64), nullable=False),
        sa.Column("signature_hmac", sa.String(length=128), nullable=False),
        sa.Column("issued_at", ts, nullable=False),
        sa.Column("expires_at", ts, nullable=False),
    )
    op.create_table(
        "cloud_admin_grant_state",
        sa.Column(
            "grant_id",
            sa.String(length=64),
            sa.ForeignKey("cloud_admin_grant_claims.grant_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("revoked_at", ts, nullable=True),
        sa.Column("consumed_at", ts, nullable=True),
        sa.Column("updated_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "cloud_offboarding_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("employee_id", sa.String(length=128), nullable=False, index=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="in_progress"),
        sa.Column("started_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("completed_at", ts, nullable=True),
    )
    op.create_table(
        "cloud_offboarding_steps",
        sa.Column("step_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "run_id",
            sa.String(length=64),
            sa.ForeignKey("cloud_offboarding_runs.run_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_name", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("completed_at", ts, nullable=True),
        sa.UniqueConstraint("run_id", "step_name", name="uq_offboarding_run_step"),
    )


def downgrade() -> None:
    op.drop_table("cloud_offboarding_steps")
    op.drop_table("cloud_offboarding_runs")
    op.drop_table("cloud_admin_grant_state")
    op.drop_table("cloud_admin_grant_claims")
    op.drop_table("cloud_employees")
