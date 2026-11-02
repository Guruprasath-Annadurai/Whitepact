"""Add governance_policies table.

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-12 00:00:00.000000

WhitePact Enterprise Foundation v2 — closes a gap flagged in
MIGRATION_WHITEPACT_V2.md Section 8.2: policy rules previously only
existed as in-code `PolicyRule`/`Policy` objects, constructed fresh per
call site. This table persists them per-org, ordered by `position`
(first-match-wins, matching `Policy.evaluate()`'s own semantics) — see
db/policy_repository.py. New, additive table; nothing existing is
touched.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_policies",
        sa.Column("id",           sa.String(36),  nullable=False),
        sa.Column("org_id",       sa.String(36),  nullable=False),
        sa.Column("rule_id",      sa.String(100), nullable=False),
        sa.Column("reason_code",  sa.String(100), nullable=False),
        sa.Column("effect",       sa.String(30),  nullable=False),
        sa.Column("risk_tiers",   sa.Text(),      nullable=True),
        sa.Column("action_types", sa.Text(),      nullable=True),
        sa.Column("targets",      sa.Text(),      nullable=True),
        sa.Column("position",     sa.Integer(),   nullable=False),
        sa.Column("created_at",   sa.String(32),  nullable=False),
        sa.Column("updated_at",   sa.String(32),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gpol_org", "governance_policies", ["org_id"])
    op.create_index("idx_gpol_position", "governance_policies", ["org_id", "position"])


def downgrade() -> None:
    op.drop_index("idx_gpol_position", table_name="governance_policies")
    op.drop_index("idx_gpol_org", table_name="governance_policies")
    op.drop_table("governance_policies")
