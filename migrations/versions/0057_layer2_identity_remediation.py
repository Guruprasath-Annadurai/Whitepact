# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Layer 2 identity security remediation: durable OAuth, abuse counters, four-eyes.

Revision ID: 0057
Revises: 0056
Create Date: 2026-09-20 00:00:00.000000

Administrative identity-security state only. Does not grant execution
authority. Does not alter Phase 7A tables. Does not open Production Gate B.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0057"
down_revision: str | None = "0056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "identity_oauth_transactions",
        sa.Column("state_hash", sa.String(length=64), primary_key=True),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("nonce", sa.String(length=64), nullable=False),
        sa.Column("pkce_verifier", sa.String(length=128), nullable=False),
        sa.Column("redirect_uri", sa.String(length=512), nullable=False),
        sa.Column("intended_org_id", sa.String(length=36), nullable=True),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
        sa.Column("code_hash", sa.String(length=64), nullable=True),
    )
    op.create_index("idx_identity_oauth_expiry", "identity_oauth_transactions", ["expires_at"])

    op.create_table(
        "identity_rate_counters",
        sa.Column("bucket_key", sa.String(length=256), primary_key=True),
        sa.Column("window_start", sa.String(length=32), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )

    op.create_table(
        "identity_four_eyes_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "requester_user_id",
            sa.String(length=36),
            sa.ForeignKey("web_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "approver_user_id",
            sa.String(length=36),
            sa.ForeignKey("web_users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("parameters_json", sa.Text(), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("security_version", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("approved_at", sa.String(length=32), nullable=True),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
    )
    op.create_index("idx_identity_four_eyes_org", "identity_four_eyes_requests", ["org_id"])
    op.create_index("idx_identity_four_eyes_requester", "identity_four_eyes_requests", ["requester_user_id"])


def downgrade() -> None:
    op.drop_index("idx_identity_four_eyes_requester", table_name="identity_four_eyes_requests")
    op.drop_index("idx_identity_four_eyes_org", table_name="identity_four_eyes_requests")
    op.drop_table("identity_four_eyes_requests")
    op.drop_table("identity_rate_counters")
    op.drop_index("idx_identity_oauth_expiry", table_name="identity_oauth_transactions")
    op.drop_table("identity_oauth_transactions")
