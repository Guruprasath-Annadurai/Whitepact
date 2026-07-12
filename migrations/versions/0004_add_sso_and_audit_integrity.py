"""Add sso_required to organizations and hash-chain integrity to audit_log.

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-12 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("organizations", recreate="auto") as batch_op:
        batch_op.add_column(
            sa.Column("sso_required", sa.Integer, nullable=False, server_default="0")
        )

    with op.batch_alter_table("audit_log", recreate="auto") as batch_op:
        batch_op.add_column(sa.Column("entry_hash", sa.String(64), nullable=True))
        batch_op.add_column(sa.Column("prev_hash", sa.String(64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("audit_log", recreate="auto") as batch_op:
        batch_op.drop_column("prev_hash")
        batch_op.drop_column("entry_hash")

    with op.batch_alter_table("organizations", recreate="auto") as batch_op:
        batch_op.drop_column("sso_required")
