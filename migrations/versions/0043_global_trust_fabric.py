# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Establish WhitePact Phase 3 Global Trust Fabric & Principal Intelligence tables.

Creates:
- trust_fabric_principals
- trust_fabric_identifiers
- trust_fabric_sources
- trust_fabric_assertions
- trust_fabric_relationships
- trust_fabric_authority_edges
- trust_fabric_trust_roots
- trust_fabric_bootstrap_records
- trust_fabric_passports
- trust_fabric_conflicts
- trust_fabric_challenges
- trust_fabric_federated_assertions
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0043"
down_revision: str | None = "0042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Principals
    op.create_table(
        "trust_fabric_principals",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("principal_type", sa.String(32), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("lifecycle_state", sa.String(32), nullable=False, server_default="PENDING_VERIFICATION"),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )
    op.create_index("idx_tf_prin_org", "trust_fabric_principals", ["org_id"])
    op.create_index("idx_tf_prin_state", "trust_fabric_principals", ["lifecycle_state"])
    op.create_index("idx_tf_prin_type", "trust_fabric_principals", ["principal_type"])

    # 2. Identifiers
    op.create_table(
        "trust_fabric_identifiers",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("identifier_type", sa.String(32), nullable=False),
        sa.Column("raw_value", sa.String(512), nullable=False),
        sa.Column("normalized_value", sa.String(512), nullable=False),
        sa.Column("is_primary", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("verified_at", sa.String(32), nullable=True),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("source_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_tf_ident_norm", "trust_fabric_identifiers", ["normalized_value", "identifier_type"])
    op.create_index("idx_tf_ident_prin", "trust_fabric_identifiers", ["principal_id"])
    op.create_index("idx_tf_ident_org", "trust_fabric_identifiers", ["org_id"])
    op.create_index(
        "idx_tf_ident_active_uniq",
        "trust_fabric_identifiers",
        ["org_id", "identifier_type", "normalized_value"],
        unique=True,
        postgresql_where=sa.text("revoked_at IS NULL"),
        sqlite_where=sa.text("revoked_at IS NULL"),
    )

    # 3. Sources
    op.create_table(
        "trust_fabric_sources",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_tier", sa.String(10), nullable=False),
        sa.Column("provider_type", sa.String(64), nullable=False),
        sa.Column("endpoint_or_uri", sa.String(512), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_tf_src_tier", "trust_fabric_sources", ["source_tier"])
    op.create_index("idx_tf_src_org", "trust_fabric_sources", ["org_id"])

    # 4. Assertions
    op.create_table(
        "trust_fabric_assertions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_value", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(64), nullable=False),
        sa.Column("source_tier", sa.String(10), nullable=False),
        sa.Column("verification_method", sa.String(64), nullable=False),
        sa.Column("assurance_level", sa.String(20), nullable=False),
        sa.Column("disclosure_class", sa.String(32), nullable=False),
        sa.Column("verified_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("last_checked_at", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
    )
    op.create_index("idx_tf_asst_prin_field", "trust_fabric_assertions", ["principal_id", "field_name"])
    op.create_index("idx_tf_asst_org", "trust_fabric_assertions", ["org_id"])

    # 5. Relationships
    op.create_table(
        "trust_fabric_relationships",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "subject_principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.String(32), nullable=False),
        sa.Column("role_title", sa.String(100), nullable=True),
        sa.Column("verification_state", sa.String(32), nullable=False, server_default="UNVERIFIED"),
        sa.Column("valid_from", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("source_id", sa.String(64), nullable=False),
    )
    op.create_index("idx_tf_rel_subject", "trust_fabric_relationships", ["subject_principal_id"])
    op.create_index("idx_tf_rel_target", "trust_fabric_relationships", ["target_principal_id"])
    op.create_index("idx_tf_rel_org", "trust_fabric_relationships", ["org_id"])

    # 6. Authority Edges
    op.create_table(
        "trust_fabric_authority_edges",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "grantor_principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "grantee_principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("action_type", sa.String(100), nullable=False),
        sa.Column("resource_pattern", sa.String(255), nullable=False, server_default="*"),
        sa.Column("ceiling_limit_usd", sa.Float(), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="USD"),
        sa.Column("delegation_depth", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("valid_from", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
        sa.Column("revoked_by", sa.String(64), nullable=True),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
    )
    op.create_index("idx_tf_auth_grantee", "trust_fabric_authority_edges", ["grantee_principal_id"])
    op.create_index("idx_tf_auth_action", "trust_fabric_authority_edges", ["action_type"])
    op.create_index("idx_tf_auth_org", "trust_fabric_authority_edges", ["org_id"])

    # 7. Trust Roots
    op.create_table(
        "trust_fabric_trust_roots",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "root_principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("root_public_key", sa.String(512), nullable=False),
        sa.Column("key_algorithm", sa.String(32), nullable=False, server_default="Ed25519"),
        sa.Column("established_at", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("canonical_digest", sa.String(64), nullable=False),
    )
    op.create_index("idx_tf_root_org", "trust_fabric_trust_roots", ["org_id"])

    # 8. Bootstrap Records
    op.create_table(
        "trust_fabric_bootstrap_records",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("consumed_at", sa.String(32), nullable=True),
        sa.Column("claimed_by_principal_id", sa.String(64), nullable=True),
        sa.Column("nonce", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.String(32), nullable=False),
    )
    op.create_index("idx_tf_boot_org", "trust_fabric_bootstrap_records", ["org_id"])
    op.create_index("idx_tf_boot_nonce", "trust_fabric_bootstrap_records", ["nonce"])

    # 9. Passports
    op.create_table(
        "trust_fabric_passports",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.String(20), nullable=False, server_default="3.0"),
        sa.Column("passport_type", sa.String(32), nullable=False),
        sa.Column("claims_json", sa.Text(), nullable=False),
        sa.Column("assurance_vector_json", sa.Text(), nullable=False),
        sa.Column("generated_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("verification_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("signing_key_id", sa.String(64), nullable=True),
        sa.Column("revoked_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_tf_pass_prin", "trust_fabric_passports", ["principal_id"])
    op.create_index("idx_tf_pass_org", "trust_fabric_passports", ["org_id"])

    # 10. Conflicts
    op.create_table(
        "trust_fabric_conflicts",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column(
            "principal_id",
            sa.String(64),
            sa.ForeignKey("trust_fabric_principals.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("field_or_claim", sa.String(100), nullable=False),
        sa.Column("assertion_id_a", sa.String(64), nullable=False),
        sa.Column("assertion_id_b", sa.String(64), nullable=False),
        sa.Column("conflict_type", sa.String(32), nullable=False),
        sa.Column("detected_at", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="UNRESOLVED"),
        sa.Column("resolution_reason", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_tf_conf_prin", "trust_fabric_conflicts", ["principal_id"])
    op.create_index("idx_tf_conf_org", "trust_fabric_conflicts", ["org_id"])

    # 11. Challenges
    op.create_table(
        "trust_fabric_challenges",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("principal_id", sa.String(64), nullable=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("challenge_type", sa.String(32), nullable=False),
        sa.Column("target_identifier", sa.String(512), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False, unique=True),
        sa.Column("expected_response_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="PENDING"),
        sa.Column("issued_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("completed_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_tf_chal_nonce", "trust_fabric_challenges", ["nonce"])
    op.create_index("idx_tf_chal_org", "trust_fabric_challenges", ["org_id"])

    # 12. Federated Assertions
    op.create_table(
        "trust_fabric_federated_assertions",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("issuer_org_id", sa.String(36), nullable=False),
        sa.Column("audience_org_id", sa.String(36), nullable=False),
        sa.Column("subject_principal_id", sa.String(64), nullable=False),
        sa.Column("claim_type", sa.String(64), nullable=False),
        sa.Column("claim_payload_json", sa.Text(), nullable=False),
        sa.Column("nonce", sa.String(64), nullable=False, unique=True),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("key_id", sa.String(64), nullable=False),
        sa.Column("issued_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("revoked_at", sa.String(32), nullable=True),
    )
    op.create_index("idx_tf_fed_nonce", "trust_fabric_federated_assertions", ["nonce"])
    op.create_index("idx_tf_fed_audience", "trust_fabric_federated_assertions", ["audience_org_id"])


def downgrade() -> None:
    op.drop_table("trust_fabric_federated_assertions")
    op.drop_table("trust_fabric_challenges")
    op.drop_table("trust_fabric_conflicts")
    op.drop_table("trust_fabric_passports")
    op.drop_table("trust_fabric_bootstrap_records")
    op.drop_table("trust_fabric_trust_roots")
    op.drop_table("trust_fabric_authority_edges")
    op.drop_table("trust_fabric_relationships")
    op.drop_table("trust_fabric_assertions")
    op.drop_table("trust_fabric_sources")
    op.drop_table("trust_fabric_identifiers")
    op.drop_table("trust_fabric_principals")
