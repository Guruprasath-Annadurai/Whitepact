# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add heart root authority and consent.

Revision 0035 follows 0034; original enterprise intent was 0032.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_root_authority_records",
        sa.Column("root_id", sa.String(36), nullable=False),
        sa.Column("subject_id", sa.String(255), nullable=False),
        sa.Column("root_type", sa.String(32), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        sa.UniqueConstraint("root_id", "organization_id", name="uq_root_tenant"),
        sa.ForeignKeyConstraint(
            ["authority_source", "organization_id"],
            [
                "governance_root_authority_records.root_id",
                "governance_root_authority_records.organization_id",
            ],
            name="fk_root_parent_tenant",
            ondelete="RESTRICT",
        ),
    )
    op.create_index("idx_rar_subject", "governance_root_authority_records", ["subject_id"])
    op.create_index("idx_rar_org", "governance_root_authority_records", ["organization_id"])
    op.create_index("idx_rar_source", "governance_root_authority_records", ["authority_source"])

    op.create_table(
        "governance_consent_proofs",
        sa.Column("consent_id", sa.String(36), nullable=False),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(
            ["consenting_root_id", "organization_id"],
            [
                "governance_root_authority_records.root_id",
                "governance_root_authority_records.organization_id",
            ],
            name="fk_consent_root_tenant",
            ondelete="RESTRICT",
        ),
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
