"""Add billing plan and Stripe fields to organizations for tiered MCP monetization.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-09 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("plan", sa.String(20), nullable=False, server_default="FREE"))
        batch_op.add_column(sa.Column("stripe_customer_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("stripe_subscription_id", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("plan_renews_at", sa.String(32), nullable=True))
        batch_op.create_index("idx_org_stripe_customer", ["stripe_customer_id"])

    op.create_table(
        "mcp_tool_calls",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("tool_name", sa.String(64), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.String(32), nullable=False),
        sa.Column("allowed", sa.Integer, nullable=False, default=1),
    )
    op.create_index("idx_mcp_calls_org", "mcp_tool_calls", ["org_id"])
    op.create_index("idx_mcp_calls_ts", "mcp_tool_calls", ["timestamp"])


def downgrade() -> None:
    op.drop_index("idx_mcp_calls_ts", table_name="mcp_tool_calls")
    op.drop_index("idx_mcp_calls_org", table_name="mcp_tool_calls")
    op.drop_table("mcp_tool_calls")

    with op.batch_alter_table("organizations", recreate="auto") as batch_op:
        batch_op.drop_index("idx_org_stripe_customer")
        batch_op.drop_column("plan_renews_at")
        batch_op.drop_column("stripe_subscription_id")
        batch_op.drop_column("stripe_customer_id")
        batch_op.drop_column("plan")
