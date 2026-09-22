# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable Sovereign shadow observations (non-authoritative analytics).

Revision ID: 0061
Revises: 0060
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0061"
down_revision: str | None = "0060"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sovereign_shadow_observations",
        sa.Column("shadow_observation_id", sa.String(length=64), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False, index=True),
        sa.Column("environment", sa.String(length=64), nullable=True),
        sa.Column("agent_id", sa.String(length=128), nullable=True),
        sa.Column("action_type", sa.String(length=128), nullable=True),
        sa.Column("target_redacted", sa.String(length=256), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("shadow_disposition", sa.String(length=64), nullable=False),
        sa.Column("reason_codes_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("protocol_version", sa.String(length=32), nullable=False),
        sa.Column("schema_version", sa.String(length=32), nullable=False),
        sa.Column("diagnostic_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.String(length=32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sovereign_shadow_observations")
