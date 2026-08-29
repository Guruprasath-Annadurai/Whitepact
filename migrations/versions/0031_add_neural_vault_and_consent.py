"""Add governance_neural_consent and governance_neural_vault_index tables.

Revision ID: 0031
Revises: 0030
Create Date: 2026-08-28 00:00:00.000000

Enterprise Neural Phase 4 Step 2 (Neural Data Classification + Privacy
Boundary, docs/enterprise-neural/04_PHASE4_DESIGN.md): persists the
per-category consent ledger (governance/neural/types.py's
ConsentRecord) and the Neural Vault *index* -- metadata and references
about captured NeuralPayloads, never raw N0/N1/N2 content by default,
see the design doc Sec 6. New, additive tables; nothing existing is
touched. Nothing in the existing codebase writes to these tables yet --
no BCI device adapter (Phase 5) or decoder (Phase 6) exists to produce
real data.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: str | None = "0030"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_neural_consent",
        sa.Column("consent_id", sa.String(64), nullable=False),
        sa.Column("subject_id", sa.String(200), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=True),
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
