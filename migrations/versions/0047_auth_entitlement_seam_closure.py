# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Add enterprise web identity, invitation, OAuth flow state, and Paddle entitlement state.

Revision ID: 0047
Revises: 0046
Create Date: 2026-09-16 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0047"
down_revision: str | None = "0046"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Add Paddle and Entitlement columns to organizations table
    op.add_column("organizations", sa.Column("paddle_customer_id", sa.String(64), nullable=True))
    op.add_column("organizations", sa.Column("paddle_subscription_id", sa.String(64), nullable=True))
    op.add_column(
        "organizations",
        sa.Column("entitlement_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("organizations", sa.Column("entitlement_updated_at", sa.String(32), nullable=True))
    op.add_column("organizations", sa.Column("paddle_last_occurred_at", sa.String(36), nullable=True))
    op.create_index(
        "idx_org_paddle_customer", "organizations", ["paddle_customer_id"], unique=True
    )
    op.create_index(
        "idx_org_paddle_subscription", "organizations", ["paddle_subscription_id"]
    )

    # 2. Add session_id column to iam_step_up_nonces for authenticated-session binding
    op.add_column("iam_step_up_nonces", sa.Column("session_id", sa.String(128), nullable=True))

    # 3. Add web_identity_providers table for OIDC provider linkages
    op.create_table(
        "web_identity_providers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("web_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("issuer", sa.String(512), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("email_at_link", sa.String(254), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.UniqueConstraint("issuer", "subject", name="uq_web_identity_provider_subject"),
    )
    op.create_index("idx_web_identity_provider_user", "web_identity_providers", ["user_id"])

    # 4. Add web_invitations table for tenant invitations
    op.create_table(
        "web_invitations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("invited_by_user_id", sa.String(36), sa.ForeignKey("web_users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("accepted_by_user_id", sa.String(36), sa.ForeignKey("web_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("consumed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_web_invitations_org", "web_invitations", ["org_id"])
    op.create_index("idx_web_invitations_email", "web_invitations", ["email"])

    # 5. Add oauth_flow_states table for durable multi-replica OIDC authorization state
    op.create_table(
        "oauth_flow_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("tenant_id", sa.String(36), nullable=True),
        sa.Column("session_id", sa.String(64), nullable=True),
        sa.Column("nonce", sa.String(64), nullable=False),
        sa.Column("pkce_verifier", sa.String(128), nullable=True),
        sa.Column("redirect_uri", sa.String(512), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("consumed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_oauth_flow_states_expiry", "oauth_flow_states", ["expires_at"])

    # 6. Add paddle_webhook_events table for durable replay and chronological protection
    op.create_table(
        "paddle_webhook_events",
        sa.Column("event_id", sa.String(100), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("occurred_at", sa.String(36), nullable=True),
        sa.Column("entity_id", sa.String(100), nullable=True),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="processing"),
        sa.Column("received_at", sa.String(32), nullable=False),
        sa.Column("processed_at", sa.String(32), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("idx_paddle_events_org", "paddle_webhook_events", ["org_id"])


def downgrade() -> None:
    op.drop_table("paddle_webhook_events")
    op.drop_table("oauth_flow_states")
    op.drop_table("web_invitations")
    op.drop_table("web_identity_providers")
    op.drop_column("iam_step_up_nonces", "session_id")
    op.drop_index("idx_org_paddle_subscription", table_name="organizations")
    op.drop_index("idx_org_paddle_customer", table_name="organizations")
    op.drop_column("organizations", "paddle_last_occurred_at")
    op.drop_column("organizations", "entitlement_updated_at")
    op.drop_column("organizations", "entitlement_version")
    op.drop_column("organizations", "paddle_subscription_id")
    op.drop_column("organizations", "paddle_customer_id")
