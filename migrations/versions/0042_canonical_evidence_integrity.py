# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Establish canonical, tenant-scoped evidence integrity state."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    columns = (
        sa.Column("authentication_method", sa.String(20)),
        sa.Column("request_fingerprint", sa.String(64)),
        sa.Column("arguments_fingerprint", sa.String(64)),
        sa.Column("purpose", sa.Text()),
        sa.Column("authority_version", sa.String(64)),
        sa.Column("consent_id", sa.String(36)),
        sa.Column("consent_version", sa.String(64)),
        sa.Column("consent_state", sa.String(20)),
        sa.Column("governance_epoch", sa.Integer()),
        sa.Column("approval_id", sa.String(36)),
        sa.Column("execution_authorization_id", sa.String(36)),
        sa.Column("execution_nonce_reference", sa.String(64)),
        sa.Column("execution_target", sa.String(200)),
        sa.Column("integrity_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "integrity_status",
            sa.String(32),
            nullable=False,
            server_default="LEGACY_CHAINED_V1",
        ),
        sa.Column("chain_sequence", sa.Integer()),
    )
    for column in columns:
        op.add_column("governance_evidence", column)
    with op.batch_alter_table("governance_evidence") as batch:
        batch.create_unique_constraint("uq_gev_org_sequence", ["org_id", "chain_sequence"])
    op.create_table(
        "governance_evidence_chain_heads",
        sa.Column("org_id", sa.String(36), primary_key=True),
        sa.Column("head_hash", sa.String(64)),
        sa.Column("sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"], name="fk_evidence_head_org", ondelete="RESTRICT"
        ),
    )


def downgrade() -> None:
    op.drop_table("governance_evidence_chain_heads")
    with op.batch_alter_table("governance_evidence") as batch:
        batch.drop_constraint("uq_gev_org_sequence", type_="unique")
    for name in (
        "chain_sequence",
        "integrity_status",
        "integrity_version",
        "execution_target",
        "execution_nonce_reference",
        "execution_authorization_id",
        "approval_id",
        "governance_epoch",
        "consent_state",
        "consent_version",
        "consent_id",
        "authority_version",
        "purpose",
        "arguments_fingerprint",
        "request_fingerprint",
        "authentication_method",
    ):
        op.drop_column("governance_evidence", name)
