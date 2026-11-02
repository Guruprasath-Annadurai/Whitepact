"""Multi-approver quorum: required_approvals + governance_approval_votes.

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-12 00:00:00.000000

Closes a real gap flagged repeatedly: "no multi-approver quorum or
delegation-chain approval." required_approvals defaults to 1, which
preserves the exact single-approver behavior every existing approval
had -- see governance/approval.py's required_approvals docstring and
db/approval_repository.py's resolve() quorum logic.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_approvals",
        sa.Column("required_approvals", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_table(
        "governance_approval_votes",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=False),
        sa.Column("resolver_identity_id", sa.String(200), nullable=False),
        sa.Column("outcome", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("approval_id", "resolver_identity_id", name="uq_gapv_approval_resolver"),
    )
    op.create_index("idx_gapv_approval", "governance_approval_votes", ["approval_id"])


def downgrade() -> None:
    op.drop_index("idx_gapv_approval", table_name="governance_approval_votes")
    op.drop_table("governance_approval_votes")
    op.drop_column("governance_approvals", "required_approvals")
