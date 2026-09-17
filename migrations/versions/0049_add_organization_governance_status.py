# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Add organizations.governance_status independent of billing.

Revision ID: 0049
Revises: 0048
Create Date: 2026-09-17 00:00:00.000000

Human/admin organization lifecycle (ACTIVE / SUSPENDED / DISABLED) is
not billing state. Stripe/Paddle continue to mutate plan and
subscription_status only. This column is the durable authority input
for hosted execution and Phase 7A pre-effect revalidation.

Phase 7A runtime tables therefore start at 0050, not 0049.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0049"
down_revision: str | None = "0048"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column(
            "governance_status",
            sa.String(length=16),
            nullable=False,
            server_default="ACTIVE",
        ),
    )
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.create_check_constraint(
            "chk_org_governance_status",
            "organizations",
            "governance_status IN ('ACTIVE', 'SUSPENDED', 'DISABLED')",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("chk_org_governance_status", "organizations", type_="check")
    op.drop_column("organizations", "governance_status")
