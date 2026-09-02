"""Add action_digest to governance_approvals.

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-12 00:00:00.000000

Closes a real gap: an ApprovalRequest previously bound only to
action_type/target, not the actual argument values a human reviewed —
so nothing detected a mutated (e.g. a changed payment amount) or
replayed approval. See governance/approval.py's compute_action_digest()/
matches_action() and db/approval_repository.py's consume().
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_approvals",
        sa.Column("action_digest", sa.String(64), nullable=False, server_default=""),
    )


def downgrade() -> None:
    op.drop_column("governance_approvals", "action_digest")
