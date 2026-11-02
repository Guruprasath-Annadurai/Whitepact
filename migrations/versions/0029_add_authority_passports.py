"""Add governance_authority_passports table.

Revision ID: 0029
Revises: 0028
Create Date: 2026-08-20 00:00:00.000000

Authority Everywhere Phase 5 (Authority Passport): a portable,
issuable, revocable, independently verifiable representation of a
principal's held authority, generalizing OrgAuthorityCeiling and
DelegationRecord. See governance/authority_passport.py and
db/authority_passport_repository.py. New, additive table; nothing
existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0029"
down_revision: str | None = "0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_authority_passports",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("principal_id", sa.String(200), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        sa.Column("source_id", sa.String(200), nullable=False),
        sa.Column("granted_action_types", sa.Text(), nullable=False),
        sa.Column("max_value_usd", sa.Float(), nullable=True),
        sa.Column("allowed_targets", sa.Text(), nullable=True),
        sa.Column("denied_targets", sa.Text(), nullable=True),
        sa.Column("require_approval_for", sa.Text(), nullable=True),
        sa.Column("max_delegation_depth", sa.Integer(), nullable=True),
        sa.Column("issued_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("revoked_by", sa.String(200), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ap_org", "governance_authority_passports", ["org_id"])
    op.create_index(
        "idx_ap_principal", "governance_authority_passports", ["org_id", "principal_id"]
    )


def downgrade() -> None:
    op.drop_index("idx_ap_principal", table_name="governance_authority_passports")
    op.drop_index("idx_ap_org", table_name="governance_authority_passports")
    op.drop_table("governance_authority_passports")
