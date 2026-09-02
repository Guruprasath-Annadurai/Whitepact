"""Add delegation_chain to governance_evidence.

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-12 00:00:00.000000

Closes "authority model remains coarse... no delegation chains" --
AuthorityContext.delegation_chain (governance/models.py) is now carried
through to every EvidenceRecord for the audit trail: who delegated to
whom, through however many hops, not just the immediate grantor
authority_delegated_by already recorded.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_evidence",
        sa.Column("delegation_chain", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("governance_evidence", "delegation_chain")
