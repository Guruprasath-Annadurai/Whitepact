# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add governance execution nonces.

Revision 0039 follows 0038; original enterprise intent was 0036.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: str | None = "0038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_execution_nonces",
        sa.Column("nonce", sa.String(length=64), primary_key=True),
        sa.Column("authorization_id", sa.String(length=36), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("consumed_at", sa.String(length=32), nullable=False),
    )
    op.create_index(
        "idx_execution_nonces_consumed_at",
        "governance_execution_nonces",
        ["consumed_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_execution_nonces_consumed_at", table_name="governance_execution_nonces")
    op.drop_table("governance_execution_nonces")
