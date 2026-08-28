"""Persist Heart root authority, consent proofs, and purpose bindings.

Revision ID: 0030
Revises: 0029
Create Date: 2026-08-26 00:00:00.000000
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
    with op.batch_alter_table("governance_evidence") as batch_op:
        batch_op.add_column(sa.Column("authority_grant_digest", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("legitimacy_digest", sa.String(64), nullable=True))

    op.create_table(
        "heart_root_authorities",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("root_type", sa.String(32), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hra_subject", "heart_root_authorities", ["org_id", "subject_id"])
    op.create_index("idx_hra_source", "heart_root_authorities", ["org_id", "authority_source"])

    op.create_table(
        "heart_consent_proofs",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("consenting_root_id", sa.String(36), nullable=False),
        sa.Column("grantee_id", sa.String(255), nullable=False),
        sa.Column("scope_description", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("consent_method", sa.String(40), nullable=False),
        sa.Column("evidence_refs", sa.Text(), nullable=False),
        sa.Column("consented_at", sa.String(32), nullable=False),
        sa.Column("not_before", sa.String(32), nullable=True),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("revoked_by", sa.String(200), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hcp_grantee", "heart_consent_proofs", ["org_id", "grantee_id"])
    op.create_index("idx_hcp_root", "heart_consent_proofs", ["org_id", "consenting_root_id"])

    op.create_table(
        "heart_purpose_bindings",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=False),
        sa.Column("principal_id", sa.String(255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("intent_ref", sa.String(36), nullable=False),
        sa.Column("consent_ref", sa.String(36), nullable=False),
        sa.Column("bound_at", sa.String(32), nullable=False),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_hpb_principal", "heart_purpose_bindings", ["org_id", "principal_id"])
    op.create_index(
        "idx_hpb_refs", "heart_purpose_bindings", ["org_id", "intent_ref", "consent_ref"]
    )


def downgrade() -> None:
    op.drop_index("idx_hpb_refs", table_name="heart_purpose_bindings")
    op.drop_index("idx_hpb_principal", table_name="heart_purpose_bindings")
    op.drop_table("heart_purpose_bindings")
    op.drop_index("idx_hcp_root", table_name="heart_consent_proofs")
    op.drop_index("idx_hcp_grantee", table_name="heart_consent_proofs")
    op.drop_table("heart_consent_proofs")
    op.drop_index("idx_hra_source", table_name="heart_root_authorities")
    op.drop_index("idx_hra_subject", table_name="heart_root_authorities")
    op.drop_table("heart_root_authorities")
    with op.batch_alter_table("governance_evidence") as batch_op:
        batch_op.drop_column("legitimacy_digest")
        batch_op.drop_column("authority_grant_digest")
