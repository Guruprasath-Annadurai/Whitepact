"""Add governance_delegations table.

Revision ID: 0022
Revises: 0021
Create Date: 2026-08-16 00:00:00.000000

v3 authority-layer work (Core Invariant #2, Delegation Graph): persists
the actual graph of who delegated authority to whom -- distinct from
AuthorityContext.delegation_chain (an in-memory, per-call identity_id
list). Enables get_authority_chain(), explain_authority(), and
revoke_branch() (cascading revocation). New, additive table; nothing
existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0022"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_delegations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("from_identity_id", sa.String(200), nullable=True),
        sa.Column("to_identity_id", sa.String(200), nullable=False),
        sa.Column("granted_action_types", sa.Text(), nullable=False),
        sa.Column("constraints", sa.Text(), nullable=True),
        sa.Column("require_approval_for", sa.Text(), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("granted_by", sa.String(200), nullable=False),
        sa.Column("granted_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("revoked_by", sa.String(200), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gdel_org", "governance_delegations", ["org_id"])
    op.create_index("idx_gdel_to", "governance_delegations", ["org_id", "to_identity_id"])
    op.create_index("idx_gdel_from", "governance_delegations", ["org_id", "from_identity_id"])


def downgrade() -> None:
    op.drop_index("idx_gdel_from", table_name="governance_delegations")
    op.drop_index("idx_gdel_to", table_name="governance_delegations")
    op.drop_index("idx_gdel_org", table_name="governance_delegations")
    op.drop_table("governance_delegations")
