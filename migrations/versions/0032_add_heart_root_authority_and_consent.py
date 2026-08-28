"""Add governance_root_authority_records and governance_consent_proofs tables.

Revision ID: 0032
Revises: 0031
Create Date: 2026-08-29 00:00:00.000000

Heart Production Integration Phase 3 (persistence): the first durable
storage for Heart Phase H3's `RootAuthorityRecord`
(governance/root_authority.py) and Phase H4's `ConsentProof`
(governance/consent_proof.py). Prior to this migration neither type
could be persisted at all -- see docs/heart-production/00_CURRENT_RUNTIME_MAP.md
section 14: "Nothing in the current schema is a RootAuthorityRecord,
ConsentProof, or true LegitimacyEnvelope." New, additive tables;
nothing existing is touched. See db/root_authority_repository.py and
db/consent_proof_repository.py.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: str | None = "0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_root_authority_records",
        sa.Column("root_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("root_type", sa.String(32), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=True),
        sa.Column("issuer", sa.String(255), nullable=False),
        sa.Column("verification_method", sa.String(128), nullable=False),
        sa.Column("authority_source", sa.String(36), nullable=True),
        sa.Column("jurisdiction", sa.String(64), nullable=True),
        sa.Column("evidence_refs", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.String(32), nullable=False),
        sa.Column("not_before", sa.String(32), nullable=True),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("revoked_by", sa.String(200), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("root_id"),
    )
    op.create_index("idx_rar_subject", "governance_root_authority_records", ["subject_id"])
    op.create_index("idx_rar_org", "governance_root_authority_records", ["organization_id"])
    op.create_index("idx_rar_source", "governance_root_authority_records", ["authority_source"])

    op.create_table(
        "governance_consent_proofs",
        sa.Column("consent_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("consenting_root_id", sa.String(36), nullable=False),
        sa.Column("grantee_id", sa.String(200), nullable=False),
        sa.Column("scope_description", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("consent_method", sa.String(32), nullable=False),
        sa.Column("evidence_refs", sa.Text(), nullable=False),
        sa.Column("consented_at", sa.String(32), nullable=False),
        sa.Column("not_before", sa.String(32), nullable=True),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("revoked_by", sa.String(200), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("consent_id"),
    )
    op.create_index("idx_cp_grantee", "governance_consent_proofs", ["grantee_id"])
    op.create_index("idx_cp_consenting_root", "governance_consent_proofs", ["consenting_root_id"])


def downgrade() -> None:
    op.drop_index("idx_cp_consenting_root", table_name="governance_consent_proofs")
    op.drop_index("idx_cp_grantee", table_name="governance_consent_proofs")
    op.drop_table("governance_consent_proofs")

    op.drop_index("idx_rar_source", table_name="governance_root_authority_records")
    op.drop_index("idx_rar_org", table_name="governance_root_authority_records")
    op.drop_index("idx_rar_subject", table_name="governance_root_authority_records")
    op.drop_table("governance_root_authority_records")
