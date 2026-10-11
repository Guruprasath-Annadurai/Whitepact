# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Single-use TOTP time step for API-key step-up.

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
    with op.batch_alter_table("org_api_keys") as batch:
        batch.add_column(sa.Column("mfa_last_timestep", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("org_api_keys") as batch:
        batch.drop_column("mfa_last_timestep")
