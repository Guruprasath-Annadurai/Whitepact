"""Add allowed_action_types/allowed_targets to governance_consent_proofs.

Revision ID: 0034
Revises: 0033
Create Date: 2026-08-29 00:00:00.000000

Heart Production Closure Gap A: closes the audit finding that
resolve_authority_grant() never consulted persisted consent, partly
because ConsentProof had no structured field to match a proof's scope
against an actual ActionRequest.action_type/target. Additive columns,
non-nullable with a `[]` server default so every existing row (from
before this migration) reads back as "no scope declared" -- which
governance/authority_resolver.py's wiring treats as matching no
action, fail-closed, never as matching every action. Nothing existing
is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034"
down_revision: str | None = "0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_consent_proofs",
        sa.Column(
            "allowed_action_types", sa.Text(), nullable=False, server_default="[]"
        ),
    )
    op.add_column(
        "governance_consent_proofs",
        sa.Column("allowed_targets", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("governance_consent_proofs", "allowed_targets")
    op.drop_column("governance_consent_proofs", "allowed_action_types")
