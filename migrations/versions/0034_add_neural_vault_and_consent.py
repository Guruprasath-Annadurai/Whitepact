# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add neural vault and consent.

Revision 0034 follows 0033; original enterprise intent was 0031.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_neural_consent",
        sa.Column("consent_id", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(200), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("granted_at", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("consent_id"),
    )
    op.create_index(
        "idx_neural_consent_subject_category",
        "governance_neural_consent",
        ["subject_id", "category"],
    )

    op.create_table(
        "governance_neural_vault_index",
        sa.Column("entry_id", sa.String(64), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("subject_id", sa.String(200), nullable=False),
        sa.Column("session_id", sa.String(200), nullable=False),
        sa.Column("data_class", sa.String(32), nullable=False),
        sa.Column("device_reference", sa.String(200), nullable=True),
        sa.Column("captured_at", sa.String(32), nullable=False),
        sa.Column("retention_expires_at", sa.String(32), nullable=True),
        sa.Column("deleted_at", sa.String(32), nullable=True),
        sa.Column("encrypted_sync_copy", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("entry_id"),
    )
    op.create_index("idx_neural_vault_subject", "governance_neural_vault_index", ["subject_id"])
    op.create_index(
        "idx_neural_vault_subject_session",
        "governance_neural_vault_index",
        ["subject_id", "session_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_neural_vault_subject_session", table_name="governance_neural_vault_index")
    op.drop_index("idx_neural_vault_subject", table_name="governance_neural_vault_index")
    op.drop_table("governance_neural_vault_index")
    op.drop_index("idx_neural_consent_subject_category", table_name="governance_neural_consent")
    op.drop_table("governance_neural_consent")
