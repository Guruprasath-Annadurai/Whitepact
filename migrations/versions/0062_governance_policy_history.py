# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Append-only, hash-chained history of governance policy mutations.

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_policy_history",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("change", sa.String(length=32), nullable=False),
        sa.Column("rule_id", sa.String(length=128), nullable=True),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("actor_id", sa.String(length=128), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("rules_digest", sa.String(length=64), nullable=False),
        sa.Column("prev_entry_digest", sa.String(length=64), nullable=False),
        sa.Column("entry_digest", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("org_id", "version", name="uq_policy_history_org_version"),
    )
    op.create_index("ix_governance_policy_history_org_id", "governance_policy_history", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_governance_policy_history_org_id", table_name="governance_policy_history")
    op.drop_table("governance_policy_history")
