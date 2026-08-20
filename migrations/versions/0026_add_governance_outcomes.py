"""Add governance_outcomes table.

Revision ID: 0026
Revises: 0025
Create Date: 2026-08-20 00:00:00.000000

Authority Everywhere Phase 12 (Outcome Observation): what actually
happened when a governed action's permit was consumed, linked to the
governance_evidence row that authorized the attempt. See
governance/outcome.py and db/outcome_repository.py. New, additive
table; nothing existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026"
down_revision: str | None = "0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_outcomes",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=False),
        sa.Column("action_id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("observed_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_go_evidence", "governance_outcomes", ["evidence_id"])
    op.create_index("idx_go_org", "governance_outcomes", ["org_id"])


def downgrade() -> None:
    op.drop_index("idx_go_org", table_name="governance_outcomes")
    op.drop_index("idx_go_evidence", table_name="governance_outcomes")
    op.drop_table("governance_outcomes")
