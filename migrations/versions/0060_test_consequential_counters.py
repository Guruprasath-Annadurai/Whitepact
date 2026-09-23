# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable synthetic counter for governed exactly-once proofs.

Revision ID: 0060
Revises: 0059
Create Date: 2026-09-21 00:00:00.000000

Observability table for ``test.counter.increment``. Not an authority
table. Does not alter Phase 7A runtime schema. Does not open Gate B.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0060"
down_revision: str | None = "0059"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "test_consequential_counters",
        sa.Column("organization_id", sa.String(length=36), primary_key=True),
        sa.Column("counter", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("downstream_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("test_consequential_counters")
