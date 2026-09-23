# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Dashboard SAML AuthnRequest durable correlation.

Revision ID: 0058
Revises: 0057
Create Date: 2026-09-21 00:00:00.000000

Administrative identity-security state only. Does not grant execution
authority. Does not alter Phase 7A tables. Does not open Production Gate B.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dashboard_saml_transactions",
        sa.Column("request_id_hash", sa.String(length=64), primary_key=True),
        sa.Column("idp_entity_id", sa.String(length=512), nullable=False),
        sa.Column("acs_url", sa.String(length=512), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
        sa.Column("expires_at", sa.String(length=32), nullable=False),
        sa.Column("consumed_at", sa.String(length=32), nullable=True),
    )
    op.create_index("idx_dashboard_saml_expiry", "dashboard_saml_transactions", ["expires_at"])


def downgrade() -> None:
    op.drop_index("idx_dashboard_saml_expiry", table_name="dashboard_saml_transactions")
    op.drop_table("dashboard_saml_transactions")
