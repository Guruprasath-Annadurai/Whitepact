# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable short-lived governance execution authorizations.

Revision ID: 0051
Revises: 0050
Create Date: 2026-09-18 00:00:00.000000

Durable statuses are ISSUED and CONSUMED only. Expiration is derived
from expires_at. Revocation is derived from governance epoch mismatch.
Authorization is never execution authority after epoch drift.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0051"
down_revision: str | None = "0050"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ts = sa.DateTime(timezone=True)
    op.create_table(
        "governance_execution_authorizations",
        sa.Column("authorization_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column(
            "request_id",
            sa.String(length=64),
            sa.ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("target_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("issuer_epoch", sa.Integer(), nullable=False),
        sa.Column("expires_at", ts, nullable=False),
        sa.Column("oneshot_authority_id", sa.String(length=64), nullable=False),
        sa.Column(
            "approval_id",
            sa.String(length=36),
            sa.ForeignKey("governance_approvals.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ISSUED"),
        sa.Column("issued_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("consumed_at", ts, nullable=True),
        sa.CheckConstraint("status IN ('ISSUED', 'CONSUMED')", name="chk_exec_auth_status"),
        sa.UniqueConstraint("oneshot_authority_id", name="uq_exec_auth_oneshot"),
    )
    op.create_index(
        "idx_exec_auth_request",
        "governance_execution_authorizations",
        ["request_id"],
        unique=True,
    )
    op.create_index(
        "idx_exec_auth_org_status",
        "governance_execution_authorizations",
        ["organization_id", "status"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX idx_exec_auth_approval_id
            ON governance_execution_authorizations (approval_id)
            WHERE approval_id IS NOT NULL
            """
        )
    else:
        op.create_index(
            "idx_exec_auth_approval_id",
            "governance_execution_authorizations",
            ["approval_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("idx_exec_auth_org_status", table_name="governance_execution_authorizations")
    op.drop_index("idx_exec_auth_request", table_name="governance_execution_authorizations")
    op.drop_index("idx_exec_auth_approval_id", table_name="governance_execution_authorizations")
    op.drop_table("governance_execution_authorizations")
    _ = bind
