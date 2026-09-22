# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Add human web identities, secure sessions, and API-key metadata.

Revision ID: 0031
Revises: 0030
Create Date: 2026-09-05 18:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("provisioner_key_id", sa.String(64), nullable=True),
    )
    op.create_table(
        "web_users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email", sa.String(254), nullable=False, unique=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("email_verified_at", sa.String(32), nullable=True),
        sa.Column("disabled", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_web_users_email", "web_users", ["email"])
    op.create_table(
        "web_memberships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.UniqueConstraint("user_id", "org_id", name="uq_web_membership_user_org"),
    )
    op.create_index("idx_web_memberships_user", "web_memberships", ["user_id"])
    op.create_index("idx_web_memberships_org", "web_memberships", ["org_id"])
    op.create_table(
        "web_sessions",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("last_seen_at", sa.String(32), nullable=False),
        sa.Column("revoked", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_web_sessions_user", "web_sessions", ["user_id"])
    op.create_index("idx_web_sessions_expires", "web_sessions", ["expires_at"])
    op.create_table(
        "web_verification_tokens",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("consumed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_web_verification_user", "web_verification_tokens", ["user_id"])
    op.create_index("idx_web_verification_expiry", "web_verification_tokens", ["expires_at"])
    op.create_table(
        "org_api_key_metadata",
        sa.Column("key_id", sa.String(36), primary_key=True),
        sa.Column("prefix", sa.String(20), nullable=False),
        sa.Column("environment", sa.String(8), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("rotated_from_id", sa.String(36), nullable=True),
    )
    op.create_index("idx_api_key_metadata_prefix", "org_api_key_metadata", ["prefix"])


def downgrade() -> None:
    op.drop_index("idx_api_key_metadata_prefix", table_name="org_api_key_metadata")
    op.drop_table("org_api_key_metadata")
    op.drop_index("idx_web_verification_expiry", table_name="web_verification_tokens")
    op.drop_index("idx_web_verification_user", table_name="web_verification_tokens")
    op.drop_table("web_verification_tokens")
    op.drop_index("idx_web_sessions_expires", table_name="web_sessions")
    op.drop_index("idx_web_sessions_user", table_name="web_sessions")
    op.drop_table("web_sessions")
    op.drop_index("idx_web_memberships_org", table_name="web_memberships")
    op.drop_index("idx_web_memberships_user", table_name="web_memberships")
    op.drop_table("web_memberships")
    op.drop_index("idx_web_users_email", table_name="web_users")
    op.drop_table("web_users")
    op.drop_column("organizations", "provisioner_key_id")
