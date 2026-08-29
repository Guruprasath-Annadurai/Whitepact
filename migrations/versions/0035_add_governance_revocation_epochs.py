"""Add governance_revocation_epochs table.

Revision ID: 0035
Revises: 0034
Create Date: 2026-08-29 00:00:00.000000

Heart Production Closure Gap B: persists Heart Phase H9's
RevocationEpoch (governance/revocation_kernel.py), previously a purely
in-memory primitive with zero call sites. Composite primary key
(organization_id, scope); organization_id="" (not NULL) represents "no
tenant", matching this codebase's existing convention for
governance_crypto_keys.tenant_id.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0035"
down_revision: str | None = "0034"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "governance_revocation_epochs",
        sa.Column("organization_id", sa.String(length=36), primary_key=True),
        sa.Column("scope", sa.String(length=64), primary_key=True),
        sa.Column("epoch", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_at", sa.String(length=32), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("governance_revocation_epochs")
