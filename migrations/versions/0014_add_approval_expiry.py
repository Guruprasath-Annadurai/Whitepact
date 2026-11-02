"""Add expires_at to governance_approvals.

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-12 00:00:00.000000

Closes a real gap: a REQUIRE_APPROVAL request had no time limit -- a
human could resolve (or an executor could consume) an approval
requested weeks or months ago, against a context that may no longer be
valid. See governance/approval.py's DEFAULT_APPROVAL_TTL_HOURS/
is_expired and db/approval_repository.py's resolve()/consume().
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_approvals",
        sa.Column("expires_at", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("governance_approvals", "expires_at")
