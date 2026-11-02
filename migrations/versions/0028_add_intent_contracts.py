"""Add governance_intent_contracts table.

Revision ID: 0028
Revises: 0027
Create Date: 2026-08-20 00:00:00.000000

Authority Everywhere Phase 4 (Intent Contract): the goal/bounds an
agent declares for a task before it starts taking actions, checked
against every subsequent action from that agent until it expires. See
governance/intent.py, db/intent_repository.py, and gateway.py's new
optional ``intent`` parameter. New, additive table; nothing existing
is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0028"
down_revision: str | None = "0027"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_intent_contracts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(200), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("max_value_usd", sa.Float(), nullable=True),
        sa.Column("allowed_targets", sa.Text(), nullable=True),
        sa.Column("denied_targets", sa.Text(), nullable=True),
        sa.Column("allowed_action_types", sa.Text(), nullable=True),
        sa.Column("declared_at", sa.String(32), nullable=False),
        sa.Column("valid_from", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gic_org", "governance_intent_contracts", ["org_id"])
    op.create_index("idx_gic_agent", "governance_intent_contracts", ["org_id", "agent_id"])


def downgrade() -> None:
    op.drop_index("idx_gic_agent", table_name="governance_intent_contracts")
    op.drop_index("idx_gic_org", table_name="governance_intent_contracts")
    op.drop_table("governance_intent_contracts")
