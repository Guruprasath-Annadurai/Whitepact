# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enforce database-level uniqueness for Paddle subscription bindings across tenants.

Revision ID: 0048
Revises: 0047
Create Date: 2026-09-17 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0048"
down_revision: str | None = "0047"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Pre-flight check: verify no duplicate paddle_subscription_id mappings exist across organizations.
    # Migration must refuse to proceed if conflicting tenant mappings exist rather than silently choosing a winner.
    conn = op.get_bind()
    dups = conn.execute(
        sa.text("""
            SELECT paddle_subscription_id, count(*)
            FROM organizations
            WHERE paddle_subscription_id IS NOT NULL
            GROUP BY paddle_subscription_id
            HAVING count(*) > 1
        """)
    ).fetchall()
    if dups:
        dup_details = ", ".join(f"{row[0]} ({row[1]} orgs)" for row in dups)
        raise ValueError(
            f"Cannot apply migration 0048: found duplicate paddle_subscription_id mappings across tenants: {dup_details}. "
            "Manual resolution required to avoid silent tenant remapping or data loss."
        )

    # 2. Upgrade idx_org_paddle_subscription to UNIQUE index
    op.drop_index("idx_org_paddle_subscription", table_name="organizations")
    op.create_index(
        "idx_org_paddle_subscription",
        "organizations",
        ["paddle_subscription_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_org_paddle_subscription", table_name="organizations")
    op.create_index(
        "idx_org_paddle_subscription",
        "organizations",
        ["paddle_subscription_id"],
        unique=False,
    )
