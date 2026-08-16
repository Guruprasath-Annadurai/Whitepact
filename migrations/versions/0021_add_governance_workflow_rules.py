"""Add governance_workflow_rules table.

Revision ID: 0021
Revises: 0020
Create Date: 2026-08-16 00:00:00.000000

v3 authority-layer work (Workflow Authority Engine): persists per-org
forbidden action-sequence rules -- e.g. beneficiary.create ->
payment.limit.raise -> payment.execute within N minutes -- enforced live
on every hosted MCP tool call via
governance.workflow.check_composition_violation(). New, additive table;
nothing existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_workflow_rules",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("rule_id", sa.String(100), nullable=False),
        sa.Column("action_types", sa.Text(), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gwr_org", "governance_workflow_rules", ["org_id"])


def downgrade() -> None:
    op.drop_index("idx_gwr_org", table_name="governance_workflow_rules")
    op.drop_table("governance_workflow_rules")
