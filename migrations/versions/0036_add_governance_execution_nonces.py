"""Add governance_execution_nonces table.

Revision ID: 0036
Revises: 0035
Create Date: 2026-08-30 00:00:00.000000

Enterprise Readiness Phase 4 (replay protection): durable, atomic
consume-once storage for ExecutionAuthorization.nonce
(governance/execution.py). `nonce` as the primary key is the atomicity
guarantee itself -- a second consume attempt for the same nonce is a
UNIQUE-constraint violation, not something application code has to
lock around.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_execution_nonces",
        sa.Column("nonce", sa.String(length=64), primary_key=True),
        sa.Column("authorization_id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=False),
    )
    op.create_index(
        "idx_execution_nonces_consumed_at",
        "governance_execution_nonces",
        ["consumed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_execution_nonces_consumed_at", table_name="governance_execution_nonces")
    op.drop_table("governance_execution_nonces")
