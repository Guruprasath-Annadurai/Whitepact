# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add governance approvals purpose.

Revision 0040 follows 0039; original enterprise intent was 0037.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: str | None = "0039"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("governance_approvals", sa.Column("purpose", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("governance_approvals", "purpose")
