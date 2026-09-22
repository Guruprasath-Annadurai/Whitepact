# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add consent proof scope fields.

Revision 0037 follows 0036; original enterprise intent was 0034.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0037"
down_revision: str | None = "0036"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "governance_consent_proofs",
        sa.Column("allowed_action_types", sa.Text(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "governance_consent_proofs",
        sa.Column("allowed_targets", sa.Text(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("governance_consent_proofs", "allowed_targets")
    op.drop_column("governance_consent_proofs", "allowed_action_types")
