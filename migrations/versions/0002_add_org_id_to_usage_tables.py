"""Add org_id column to token_usage and trust_scores for per-org data isolation.

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-27 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("token_usage", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.String(36), nullable=True))
        batch_op.create_index("idx_tu_org", ["org_id"])

    with op.batch_alter_table("trust_scores", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("org_id", sa.String(36), nullable=True))
        batch_op.create_index("idx_ts_org", ["org_id"])


def downgrade() -> None:
    with op.batch_alter_table("trust_scores", recreate="auto") as batch_op:
        batch_op.drop_index("idx_ts_org")
        batch_op.drop_column("org_id")

    with op.batch_alter_table("token_usage", recreate="auto") as batch_op:
        batch_op.drop_index("idx_tu_org")
        batch_op.drop_column("org_id")
