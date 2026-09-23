# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add crypto keys.

Revision 0033 follows 0032; original enterprise intent was 0030.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0033"
down_revision: str | None = "0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_crypto_keys",
        sa.Column("key_id", sa.String(300), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column(
            "tenant_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("environment", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("wrapped_dek", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.PrimaryKeyConstraint("key_id"),
    )
    op.create_index(
        "idx_crypto_keys_lookup",
        "governance_crypto_keys",
        ["purpose", "tenant_id", "environment", "status", "version"],
    )


def downgrade() -> None:
    op.drop_index("idx_crypto_keys_lookup", table_name="governance_crypto_keys")
    op.drop_table("governance_crypto_keys")
