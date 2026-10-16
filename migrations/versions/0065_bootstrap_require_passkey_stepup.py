# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Add require_passkey_stepup to trust_fabric_bootstrap_records.

Revision ID: 0065
Revises: 0064
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0065"
down_revision: str | None = "0064"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "trust_fabric_bootstrap_records",
        sa.Column("require_passkey_stepup", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("trust_fabric_bootstrap_records", "require_passkey_stepup")
