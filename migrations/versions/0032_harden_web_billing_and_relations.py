# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Harden website relations and add durable billing state.

Revision ID: 0032
Revises: 0031
Create Date: 2026-09-06 17:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("subscription_status", sa.String(32), nullable=False, server_default="inactive"),
    )
    with op.batch_alter_table("web_memberships") as batch:
        batch.create_foreign_key(
            "fk_web_memberships_user", "web_users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_foreign_key(
            "fk_web_memberships_org", "organizations", ["org_id"], ["id"], ondelete="CASCADE"
        )
    with op.batch_alter_table("web_sessions") as batch:
        batch.create_foreign_key(
            "fk_web_sessions_user", "web_users", ["user_id"], ["id"], ondelete="CASCADE"
        )
        batch.create_foreign_key(
            "fk_web_sessions_org", "organizations", ["org_id"], ["id"], ondelete="CASCADE"
        )
    with op.batch_alter_table("web_verification_tokens") as batch:
        batch.create_foreign_key(
            "fk_web_tokens_user", "web_users", ["user_id"], ["id"], ondelete="CASCADE"
        )
    with op.batch_alter_table("org_api_key_metadata") as batch:
        batch.create_foreign_key(
            "fk_api_key_metadata_key", "org_api_keys", ["key_id"], ["id"], ondelete="CASCADE"
        )
    op.create_table(
        "stripe_webhook_events",
        sa.Column("event_id", sa.String(255), primary_key=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("received_at", sa.String(32), nullable=False),
        sa.Column("processed_at", sa.String(32)),
        sa.Column("last_error", sa.Text()),
    )
    op.create_index("idx_stripe_events_org", "stripe_webhook_events", ["org_id"])
    op.create_index("idx_stripe_events_status", "stripe_webhook_events", ["status"])


def downgrade() -> None:
    op.drop_index("idx_stripe_events_status", table_name="stripe_webhook_events")
    op.drop_index("idx_stripe_events_org", table_name="stripe_webhook_events")
    op.drop_table("stripe_webhook_events")
    with op.batch_alter_table("org_api_key_metadata") as batch:
        batch.drop_constraint("fk_api_key_metadata_key", type_="foreignkey")
    with op.batch_alter_table("web_verification_tokens") as batch:
        batch.drop_constraint("fk_web_tokens_user", type_="foreignkey")
    with op.batch_alter_table("web_sessions") as batch:
        batch.drop_constraint("fk_web_sessions_org", type_="foreignkey")
        batch.drop_constraint("fk_web_sessions_user", type_="foreignkey")
    with op.batch_alter_table("web_memberships") as batch:
        batch.drop_constraint("fk_web_memberships_org", type_="foreignkey")
        batch.drop_constraint("fk_web_memberships_user", type_="foreignkey")
    op.drop_column("organizations", "subscription_status")
