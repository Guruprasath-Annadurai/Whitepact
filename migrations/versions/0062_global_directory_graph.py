# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Global Entity & Trust Graph (Global Directory) persistence.

Revision ID: 0062
Revises: 0061
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0062"
down_revision: str | None = "0061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "global_directory_entities",
        sa.Column("entity_id", sa.String(length=64), primary_key=True),
        sa.Column("entity_type", sa.String(length=32), nullable=False),
        sa.Column("canonical_name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("canonical_urls_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("evidence_state", sa.String(length=32), nullable=False),
        sa.Column("freshness_state", sa.String(length=32), nullable=False),
        sa.Column("data_scope", sa.String(length=32), nullable=False, server_default="GLOBAL_PUBLIC_EVIDENCE"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("first_observed_at", sa.String(length=32), nullable=True),
        sa.Column("last_observed_at", sa.String(length=32), nullable=True),
        sa.Column("last_verified_at", sa.String(length=32), nullable=True),
    )
    op.create_index("idx_gd_entities_type_name", "global_directory_entities", ["entity_type", "canonical_name"])

    op.create_table(
        "global_directory_aliases",
        sa.Column("alias_id", sa.String(length=64), primary_key=True),
        sa.Column("entity_id", sa.String(length=64), sa.ForeignKey("global_directory_entities.entity_id"), nullable=False),
        sa.Column("alias_normalized", sa.String(length=256), nullable=False),
        sa.UniqueConstraint("alias_normalized", name="uq_gd_alias_normalized"),
    )
    op.create_index("idx_gd_aliases_entity", "global_directory_aliases", ["entity_id"])

    op.create_table(
        "global_directory_identifiers",
        sa.Column("identifier_id", sa.String(length=64), primary_key=True),
        sa.Column("entity_id", sa.String(length=64), sa.ForeignKey("global_directory_entities.entity_id"), nullable=False),
        sa.Column("identifier_type", sa.String(length=64), nullable=False),
        sa.Column("normalized_value", sa.String(length=512), nullable=False),
        sa.UniqueConstraint("identifier_type", "normalized_value", name="uq_gd_identifier"),
    )

    op.create_table(
        "global_directory_sources",
        sa.Column("source_id", sa.String(length=64), primary_key=True),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("source_type", sa.String(length=64), nullable=False),
        sa.Column("publisher", sa.String(length=256), nullable=True),
        sa.Column("retrieved_at", sa.String(length=32), nullable=False),
        sa.Column("published_at", sa.String(length=32), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("quality_tier", sa.String(length=64), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("retrieval_status", sa.String(length=32), nullable=False),
        sa.UniqueConstraint("canonical_url", "content_hash", name="uq_gd_source_url_hash"),
    )

    op.create_table(
        "global_directory_claims",
        sa.Column("claim_id", sa.String(length=64), primary_key=True),
        sa.Column("subject_entity_id", sa.String(length=64), sa.ForeignKey("global_directory_entities.entity_id"), nullable=False),
        sa.Column("predicate", sa.String(length=64), nullable=False),
        sa.Column("object_entity_id", sa.String(length=64), sa.ForeignKey("global_directory_entities.entity_id"), nullable=True),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("evidence_state", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("first_seen_at", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.String(length=32), nullable=False),
        sa.Column("last_verified_at", sa.String(length=32), nullable=True),
        sa.Column("valid_from", sa.String(length=32), nullable=True),
        sa.Column("valid_until", sa.String(length=32), nullable=True),
        sa.Column("source_refs_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_index("idx_gd_claims_subject", "global_directory_claims", ["subject_entity_id"])

    op.create_table(
        "global_directory_claim_evidence",
        sa.Column("evidence_id", sa.String(length=64), primary_key=True),
        sa.Column("claim_id", sa.String(length=64), sa.ForeignKey("global_directory_claims.claim_id"), nullable=False),
        sa.Column("source_id", sa.String(length=64), sa.ForeignKey("global_directory_sources.source_id"), nullable=False),
        sa.Column("excerpt_redacted", sa.Text(), nullable=False),
        sa.Column("support_type", sa.String(length=16), nullable=False),
    )

    op.create_table(
        "global_directory_relationships",
        sa.Column("relationship_id", sa.String(length=64), primary_key=True),
        sa.Column("subject_entity_id", sa.String(length=64), sa.ForeignKey("global_directory_entities.entity_id"), nullable=False),
        sa.Column("predicate", sa.String(length=64), nullable=False),
        sa.Column("object_entity_id", sa.String(length=64), sa.ForeignKey("global_directory_entities.entity_id"), nullable=False),
        sa.Column("evidence_state", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("first_seen_at", sa.String(length=32), nullable=False),
        sa.Column("last_seen_at", sa.String(length=32), nullable=False),
        sa.Column("valid_from", sa.String(length=32), nullable=True),
        sa.Column("valid_until", sa.String(length=32), nullable=True),
    )

    op.create_table(
        "global_directory_discovery_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("query_text", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("budgets_json", sa.Text(), nullable=False),
        sa.Column("started_at", sa.String(length=32), nullable=False),
        sa.Column("completed_at", sa.String(length=32), nullable=True),
        sa.Column("org_id", sa.String(length=36), nullable=True),
    )

    op.create_table(
        "global_directory_suppressions",
        sa.Column("suppression_id", sa.String(length=64), primary_key=True),
        sa.Column("entity_id", sa.String(length=64), nullable=True),
        sa.Column("field_name", sa.String(length=128), nullable=True),
        sa.Column("suppression_kind", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("global_directory_suppressions")
    op.drop_table("global_directory_discovery_runs")
    op.drop_table("global_directory_relationships")
    op.drop_table("global_directory_claim_evidence")
    op.drop_table("global_directory_claims")
    op.drop_table("global_directory_sources")
    op.drop_table("global_directory_identifiers")
    op.drop_table("global_directory_aliases")
    op.drop_table("global_directory_entities")
