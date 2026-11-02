"""Widen audit_log.ip_address to Text for opt-in field-level encryption.

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-21 00:00:00.000000

`ip_address` was String(64), sized for a plain IPv4/IPv6 string. It's now
optionally encrypted at the application layer (see
`responsibleai.db.encryption.EncryptedString`, opt-in via
`RAI_FIELD_ENCRYPTION_KEY`) — Fernet ciphertext for a short string is
noticeably longer than the raw value, so the column needs to be
unbounded Text rather than a fixed 64-char String. This is a widening-only
change: existing plaintext values remain valid Text values unchanged,
and encryption only starts once a deployer sets the key.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("audit_log", recreate="auto") as batch_op:
        batch_op.alter_column(
            "ip_address",
            existing_type=sa.String(64),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("audit_log", recreate="auto") as batch_op:
        batch_op.alter_column(
            "ip_address",
            existing_type=sa.Text(),
            type_=sa.String(64),
            existing_nullable=True,
        )
