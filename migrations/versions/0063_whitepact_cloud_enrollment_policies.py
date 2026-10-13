# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Employee authorized permissions and admin policy registry.

Revision ID: 0063
Revises: 0062
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0063"
down_revision: str | None = "0062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "cloud_employees",
        sa.Column("authorized_permissions_json", sa.Text(), nullable=False, server_default="[]"),
    )
    op.create_table(
        "cloud_admin_policies",
        sa.Column("policy_id", sa.String(length=128), primary_key=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_approver", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )


def downgrade() -> None:
    op.drop_table("cloud_admin_policies")
    op.drop_column("cloud_employees", "authorized_permissions_json")
