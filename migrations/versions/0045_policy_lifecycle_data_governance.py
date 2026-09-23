# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Policy Lifecycle, Data Governance & Tenant Erasure migration.

Creates:
- governance_policy_revisions
- governance_policy_activations
- data_retention_policies
- data_lifecycle_requests
- data_holds
- tenant_tombstones
- restore_reconciliation_records
Adds policy_digest column to governance_evidence.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0045"
down_revision: str | None = "0044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. governance_policy_revisions
    op.create_table(
        "governance_policy_revisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("revision_num", sa.Integer(), nullable=False),
        sa.Column("rules_json", sa.Text(), nullable=False),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("change_reason", sa.Text(), nullable=False),
        sa.Column("approval_id", sa.String(36), nullable=True),
        sa.UniqueConstraint("org_id", "revision_num", name="uq_pol_rev_org_num"),
    )
    op.create_index("idx_pol_rev_org_num", "governance_policy_revisions", ["org_id", "revision_num"])
    op.create_index("idx_pol_rev_digest", "governance_policy_revisions", ["org_id", "content_digest"])

    # 2. governance_policy_activations
    op.create_table(
        "governance_policy_activations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "revision_id",
            sa.String(36),
            sa.ForeignKey("governance_policy_revisions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("content_digest", sa.String(64), nullable=False),
        sa.Column("activated_at", sa.String(64), nullable=False),
        sa.Column("activated_by", sa.String(200), nullable=False),
        sa.Column("governance_epoch", sa.Integer(), nullable=False),
        sa.Column("previous_activation_id", sa.String(36), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("idx_pol_act_org_active", "governance_policy_activations", ["org_id", "is_active"])

    # 3. data_retention_policies
    op.create_table(
        "data_retention_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("data_category", sa.String(50), nullable=False),
        sa.Column("retention_period_seconds", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("updated_at", sa.String(64), nullable=False),
        sa.UniqueConstraint("org_id", "data_category", name="uq_retention_org_cat"),
    )
    op.create_index("idx_retention_org", "data_retention_policies", ["org_id"])

    # 4. data_lifecycle_requests
    op.create_table(
        "data_lifecycle_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("request_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("requested_at", sa.String(64), nullable=False),
        sa.Column("completed_at", sa.String(64), nullable=True),
        sa.Column("requested_by", sa.String(200), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("verification_status", sa.String(32), nullable=True),
    )
    op.create_index("idx_lifecycle_org_status", "data_lifecycle_requests", ["org_id", "status"])

    # 5. data_holds
    op.create_table(
        "data_holds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "org_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("data_category", sa.String(50), nullable=False),
        sa.Column("hold_reason", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.String(64), nullable=False),
        sa.Column("created_by", sa.String(200), nullable=False),
        sa.Column("released_at", sa.String(64), nullable=True),
        sa.Column("released_by", sa.String(200), nullable=True),
    )
    op.create_index("idx_holds_org_cat_active", "data_holds", ["org_id", "data_category", "active"])

    # 6. tenant_tombstones
    op.create_table(
        "tenant_tombstones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=False, unique=True),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("generation_id", sa.String(64), nullable=False),
        sa.Column("tombstoned_at", sa.String(64), nullable=False),
        sa.Column("tombstoned_by", sa.String(200), nullable=False),
        sa.Column("authority_hash", sa.String(64), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=False),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_tombstone_org", "tenant_tombstones", ["org_id"])
    op.create_index("idx_tombstone_gen", "tenant_tombstones", ["generation_id"])

    # 7. restore_reconciliation_records
    op.create_table(
        "restore_reconciliation_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("restored_at", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("tombstones_detected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tenants_quarantined", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("reconciled_by", sa.String(200), nullable=False),
    )
    op.create_index("idx_restore_rec_status", "restore_reconciliation_records", ["status"])

    # 8. Add policy_digest to governance_evidence
    with op.batch_alter_table("governance_evidence") as batch_op:
        batch_op.add_column(sa.Column("policy_digest", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("governance_evidence") as batch_op:
        batch_op.drop_column("policy_digest")

    op.drop_table("restore_reconciliation_records")
    op.drop_table("tenant_tombstones")
    op.drop_table("data_holds")
    op.drop_table("data_lifecycle_requests")
    op.drop_table("data_retention_policies")
    op.drop_table("governance_policy_activations")
    op.drop_table("governance_policy_revisions")
