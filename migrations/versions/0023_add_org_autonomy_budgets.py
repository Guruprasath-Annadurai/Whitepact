"""Add org_autonomy_budgets table.

Revision ID: 0023
Revises: 0022
Create Date: 2026-08-17 00:00:00.000000

v3 authority-layer work (Autonomy Budget): a rolling-window cap on how
many ALLOW/ALLOW_WITH_REDACTION decisions a single identity may accrue
before the next one is forced to REQUIRE_APPROVAL. One row per org; no
row means no budget configured -- existing orgs are unaffected. New,
additive table; nothing existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_autonomy_budgets",
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("max_autonomous_actions", sa.Integer(), nullable=False),
        sa.Column("window_minutes", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("org_id"),
    )


def downgrade() -> None:
    op.drop_table("org_autonomy_budgets")
