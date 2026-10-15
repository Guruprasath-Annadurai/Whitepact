"""Add upstream_mcp_servers -- the MCP Upstream Gateway's registry.

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-12 00:00:00.000000

The largest remaining gap flagged repeatedly in this session's gap
reports: WhitePact governed its own 27 in-process tools but had no way
to proxy a governed call to a third-party MCP server. This table is the
org-scoped, SSRF-validated registry of approved upstream servers -- see
governance/upstream.py and governance/upstream_executor.py.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "upstream_mcp_servers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("enabled", sa.Integer, nullable=False, server_default="1"),
        sa.Column("auth_token", sa.Text(), nullable=True),
        sa.Column("added_by", sa.String(200), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ums_org", "upstream_mcp_servers", ["org_id"])


def downgrade() -> None:
    op.drop_index("idx_ums_org", table_name="upstream_mcp_servers")
    op.drop_table("upstream_mcp_servers")
