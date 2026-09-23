# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Bind approvals to authentication, authority, policy, epoch and target state."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: str | None = "0040"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("governance_approvals", sa.Column("authentication_method", sa.String(20)))
    op.add_column("governance_approvals", sa.Column("revocation_epoch", sa.Integer()))
    op.add_column("governance_approvals", sa.Column("authority_version", sa.String(64)))
    op.add_column("governance_approvals", sa.Column("policy_version", sa.Integer()))
    op.add_column("governance_approvals", sa.Column("target_fingerprint", sa.String(64)))


def downgrade() -> None:
    op.drop_column("governance_approvals", "target_fingerprint")
    op.drop_column("governance_approvals", "policy_version")
    op.drop_column("governance_approvals", "authority_version")
    op.drop_column("governance_approvals", "revocation_epoch")
    op.drop_column("governance_approvals", "authentication_method")
