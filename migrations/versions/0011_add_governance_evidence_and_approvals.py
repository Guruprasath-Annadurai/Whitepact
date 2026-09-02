"""Add governance_evidence and governance_approvals tables.

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-11 00:00:00.000000

WhitePact Enterprise Foundation v2 Phases 11-12 (see
MIGRATION_WHITEPACT_V2.md Section 8): persisted, hash-chained
GovernanceDecision evidence (governance_evidence, one independently
verifiable chain per organization -- see db/evidence_repository.py) and
persisted, resolvable REQUIRE_APPROVAL requests (governance_approvals,
see db/approval_repository.py). Both are new, additive tables; nothing
existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_evidence",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("action_id", sa.String(36), nullable=False),
        sa.Column("agent_id", sa.String(36), nullable=False),
        sa.Column("identity_id", sa.String(200), nullable=False),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("argument_keys", sa.Text(), nullable=True),
        sa.Column("authority_delegated_by", sa.String(200), nullable=False),
        sa.Column("risk_tier", sa.String(20), nullable=True),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("framework", sa.String(50), nullable=True),
        sa.Column("provider", sa.String(50), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("evaluated_at", sa.String(32), nullable=False),
        sa.Column("recorded_at", sa.String(32), nullable=False),
        sa.Column("entry_hash", sa.String(64), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gev_org", "governance_evidence", ["org_id"])
    op.create_index("idx_gev_action", "governance_evidence", ["action_id"])
    op.create_index("idx_gev_decision", "governance_evidence", ["decision"])
    op.create_index("idx_gev_recorded", "governance_evidence", ["recorded_at"])

    op.create_table(
        "governance_approvals",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("action_id", sa.String(36), nullable=False),
        sa.Column("evidence_id", sa.String(36), nullable=True),
        sa.Column("action_type", sa.String(50), nullable=False),
        sa.Column("target", sa.String(200), nullable=False),
        sa.Column("reason_codes", sa.Text(), nullable=False),
        sa.Column("risk_tier", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("requested_by", sa.String(200), nullable=True),
        sa.Column("requested_at", sa.String(32), nullable=False),
        sa.Column("resolved_by", sa.String(200), nullable=True),
        sa.Column("resolved_at", sa.String(32), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_gap_org", "governance_approvals", ["org_id"])
    op.create_index("idx_gap_status", "governance_approvals", ["status"])
    op.create_index("idx_gap_requested", "governance_approvals", ["requested_at"])
    op.create_index("idx_gap_action", "governance_approvals", ["action_id"])


def downgrade() -> None:
    op.drop_index("idx_gap_action", table_name="governance_approvals")
    op.drop_index("idx_gap_requested", table_name="governance_approvals")
    op.drop_index("idx_gap_status", table_name="governance_approvals")
    op.drop_index("idx_gap_org", table_name="governance_approvals")
    op.drop_table("governance_approvals")

    op.drop_index("idx_gev_recorded", table_name="governance_evidence")
    op.drop_index("idx_gev_decision", table_name="governance_evidence")
    op.drop_index("idx_gev_action", table_name="governance_evidence")
    op.drop_index("idx_gev_org", table_name="governance_evidence")
    op.drop_table("governance_evidence")
