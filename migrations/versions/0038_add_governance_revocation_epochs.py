# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add governance revocation epochs.

Revision 0038 follows 0037; original enterprise intent was 0035.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0038"
down_revision: str | None = "0037"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_revocation_epochs",
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("scope", sa.String(length=64), primary_key=True),
        sa.Column("epoch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("governance_revocation_epochs")
