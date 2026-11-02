"""Add tool_trust_scores table.

Revision ID: 0024
Revises: 0023
Create Date: 2026-08-19 00:00:00.000000

Authority Everywhere Phase 8 (Tool Trust Network): one row per
org-registered upstream MCP server, holding its current deterministic
trust score/tier plus an optional admin override. New, additive table;
a server with no row is treated as unscanned (see
governance/tool_trust.py's unscanned_score()) -- nothing existing is
touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tool_trust_scores",
        sa.Column("server_id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False),
        sa.Column("has_been_scanned", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("incident_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scan_report_id", sa.String(36), nullable=True),
        sa.Column("scan_summary", sa.Text(), nullable=True),
        sa.Column("last_scanned_at", sa.String(32), nullable=True),
        sa.Column("admin_override_tier", sa.String(20), nullable=True),
        sa.Column("admin_override_by", sa.String(200), nullable=True),
        sa.Column("admin_override_reason", sa.Text(), nullable=True),
        sa.Column("admin_override_at", sa.String(32), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("server_id"),
    )
    op.create_index("idx_tts_org", "tool_trust_scores", ["org_id"])


def downgrade() -> None:
    op.drop_index("idx_tts_org", table_name="tool_trust_scores")
    op.drop_table("tool_trust_scores")
