# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Widen audit_log.key_id for web-session audit actors.

Revision ID: 0059
Revises: 0058
Create Date: 2026-09-21 00:00:00.000000

Web console audit rows use key_id values such as web:{user_uuid} (40
characters). varchar(36) truncated those writes on PostgreSQL, so
customer session/audit history failed closed in the background.
Administrative audit schema only. Does not grant execution authority.
Does not alter Phase 7A tables. Does not open Production Gate B.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0059"
down_revision: str | None = "0058"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log", recreate="auto") as batch_op:
        batch_op.alter_column(
            "key_id",
            existing_type=sa.String(length=36),
            type_=sa.String(length=64),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_log", recreate="auto") as batch_op:
        batch_op.alter_column(
            "key_id",
            existing_type=sa.String(length=64),
            type_=sa.String(length=36),
            existing_nullable=True,
        )
