"""Policy versioning: policy_version on governance_evidence,
governance_policy_versions table.

Revision ID: 0015
Revises: 0014
Create Date: 2026-08-12 00:00:00.000000

Closes a real gap: evidence could not say exactly which version of an
org's policy rule set it was evaluated against -- only that "a Policy"
was or wasn't consulted. See governance/policy.py's Policy.version and
db/policy_repository.py's version bump on every mutation.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_evidence",
        sa.Column("policy_version", sa.Integer(), nullable=True),
    )
    op.create_table(
        "governance_policy_versions",
        sa.Column("org_id", sa.String(36), primary_key=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("governance_policy_versions")
    op.drop_column("governance_evidence", "policy_version")
