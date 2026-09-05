# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Add OAuth 2.1 authorization state for hosted MCP clients.

Revision ID: 0030
Revises: 0029
Create Date: 2026-09-05 00:00:00.000000

All credential material is stored as a one-way SHA-256 digest. The tables
bind every code and token to one client, redirect, resource, tenant, subject,
role, and scope set.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "oauth_clients",
        sa.Column("client_id", sa.String(80), primary_key=True),
        sa.Column("client_name", sa.String(200), nullable=False),
        sa.Column("redirect_uris", sa.Text(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("revoked", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "oauth_authorization_requests",
        sa.Column("request_hash", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False),
        sa.Column("redirect_uri", sa.String(512), nullable=False),
        sa.Column("state", sa.String(512), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("resource", sa.String(512), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_oar_client", "oauth_authorization_requests", ["client_id"])
    op.create_table(
        "oauth_authorization_codes",
        sa.Column("code_hash", sa.String(64), primary_key=True),
        sa.Column("client_id", sa.String(80), nullable=False),
        sa.Column("redirect_uri", sa.String(512), nullable=False),
        sa.Column("code_challenge", sa.String(128), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(80), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("resource", sa.String(512), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_oac_client", "oauth_authorization_codes", ["client_id"])
    op.create_table(
        "oauth_credentials",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("token_type", sa.String(16), nullable=False),
        sa.Column("family_id", sa.String(80), nullable=False),
        sa.Column("client_id", sa.String(80), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(80), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("scopes", sa.Text(), nullable=False),
        sa.Column("resource", sa.String(512), nullable=False),
        sa.Column("issued_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("revoked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_oc_family", "oauth_credentials", ["family_id"])
    op.create_index("idx_oc_org", "oauth_credentials", ["org_id"])
    op.create_index("idx_oc_subject", "oauth_credentials", ["subject_id"])
    op.create_table(
        "oauth_auth_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("subject_id", sa.String(80), nullable=True),
        sa.Column("client_id", sa.String(80), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_oae_created", "oauth_auth_events", ["created_at"])
    op.create_index("idx_oae_org", "oauth_auth_events", ["org_id"])


def downgrade() -> None:
    op.drop_index("idx_oae_org", table_name="oauth_auth_events")
    op.drop_index("idx_oae_created", table_name="oauth_auth_events")
    op.drop_table("oauth_auth_events")
    op.drop_index("idx_oc_subject", table_name="oauth_credentials")
    op.drop_index("idx_oc_org", table_name="oauth_credentials")
    op.drop_index("idx_oc_family", table_name="oauth_credentials")
    op.drop_table("oauth_credentials")
    op.drop_index("idx_oac_client", table_name="oauth_authorization_codes")
    op.drop_table("oauth_authorization_codes")
    op.drop_index("idx_oar_client", table_name="oauth_authorization_requests")
    op.drop_table("oauth_authorization_requests")
    op.drop_table("oauth_clients")
