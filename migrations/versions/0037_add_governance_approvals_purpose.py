"""Add purpose column to governance_approvals.

Revision ID: 0037
Revises: 0036
Create Date: 2026-08-30 00:00:00.000000

Enterprise Readiness Phase 5 (purpose binding): a nullable `purpose`
column carrying the requested purpose a human approved
(governance/approval.py's ApprovalRequest.purpose), so
build_resume_action() can reconstruct it at resume time instead of
silently losing it across a REQUIRE_APPROVAL -> resume cycle. NULL
means "no purpose was declared," never "any purpose is authorized."
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("governance_approvals", sa.Column("purpose", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("governance_approvals", "purpose")
