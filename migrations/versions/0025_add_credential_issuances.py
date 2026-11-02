"""Add credential_issuances table.

Revision ID: 0025
Revises: 0024
Create Date: 2026-08-19 00:00:00.000000

Authority Everywhere Phase 10 (JIT Credential Broker): an audit trail
of credential issuance events, never the credential value itself. One
row per JITCredential actually issued -- see
governance/jit_credential.py and db/credential_issuance_repository.py.
New, additive table; nothing existing is touched.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: str | None = "0024"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credential_issuances",
        sa.Column("credential_id", sa.String(36), nullable=False),
        sa.Column("authorization_id", sa.String(36), nullable=False),
        sa.Column("action_id", sa.String(36), nullable=False),
        sa.Column("server_id", sa.String(36), nullable=False),
        sa.Column("org_id", sa.String(36), nullable=True),
        sa.Column("agent_id", sa.String(200), nullable=True),
        sa.Column("had_credential", sa.Integer(), nullable=False),
        sa.Column("issued_at", sa.String(32), nullable=False),
        sa.Column("expires_at", sa.String(32), nullable=False),
        sa.Column("consumed_at", sa.String(32), nullable=True),
        sa.PrimaryKeyConstraint("credential_id"),
    )
    op.create_index("idx_ci_org", "credential_issuances", ["org_id"])
    op.create_index("idx_ci_server", "credential_issuances", ["server_id"])


def downgrade() -> None:
    op.drop_index("idx_ci_server", table_name="credential_issuances")
    op.drop_index("idx_ci_org", table_name="credential_issuances")
    op.drop_table("credential_issuances")
