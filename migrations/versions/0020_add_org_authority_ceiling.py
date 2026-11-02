"""Add org_authority_ceilings table.

Revision ID: 0020
Revises: 0019
Create Date: 2026-08-16 00:00:00.000000

v3 authority-layer work: a structural ceiling no per-call
`AuthorityContext` built for an org can ever exceed, enforced via
`governance.validate_attenuation()` as the live `parent_authority` on
every hosted MCP tool call. One row per org; no row (or an all-null
row) means "no ceiling configured" -- existing orgs are unaffected.
New, additive table; nothing existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "org_authority_ceilings",
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("max_value_usd", sa.Float(), nullable=True),
        sa.Column("allowed_targets", sa.Text(), nullable=True),
        sa.Column("denied_targets", sa.Text(), nullable=True),
        sa.Column("max_delegation_depth", sa.Integer(), nullable=True),
        sa.Column("allowed_action_types", sa.Text(), nullable=True),
        sa.Column("require_approval_for", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("org_id"),
    )


def downgrade() -> None:
    op.drop_table("org_authority_ceilings")
