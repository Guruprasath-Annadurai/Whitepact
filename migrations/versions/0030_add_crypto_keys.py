"""Add governance_crypto_keys table.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-28 00:00:00.000000

Enterprise Neural Phase 2 Step 2 (Cryptographic Foundation + Key
Management, docs/enterprise-neural/02_PHASE2_DESIGN.md): persists
wrapped DEKs (never plaintext key material) for
governance/crypto/local_envelope.py's LocalEnvelopeKeyProvider, via
db/crypto_key_repository.py's CryptoKeyRepository, replacing the
non-persistent InMemoryWrappedKeyStore for real deployments. New,
additive table; nothing existing is touched. Nothing in the existing
codebase writes to this table yet -- call-site wiring is a later
step of the same phase.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030"
down_revision: str | None = "0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_crypto_keys",
        sa.Column("key_id", sa.String(300), nullable=False),
        sa.Column("purpose", sa.String(32), nullable=False),
        sa.Column("tenant_id", sa.String(200), nullable=False),
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
