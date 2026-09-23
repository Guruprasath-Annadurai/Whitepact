# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Phase 1: add evidence chain uniqueness.

Revision 0036 follows 0035; original enterprise intent was 0033.
Website revisions 0030–0032 are preserved. No legacy revision stamping.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0036"
down_revision: str | None = "0035"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    invalid = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM governance_evidence e LEFT JOIN organizations o "
                "ON e.org_id = o.id WHERE e.org_id IS NULL OR o.id IS NULL LIMIT 1"
            )
        )
        .first()
    )
    if invalid:
        raise RuntimeError(
            "Evidence tenant ownership is missing; migration refuses to alter historical evidence"
        )
    fork = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT 1 FROM governance_evidence GROUP BY org_id, prev_hash "
                "HAVING COUNT(*) > 1 LIMIT 1"
            )
        )
        .first()
    )
    if fork:
        raise RuntimeError(
            "Evidence chain fork detected; preserve and investigate historical evidence"
        )
    with op.batch_alter_table("governance_evidence") as batch:
        batch.alter_column("org_id", existing_type=sa.String(36), nullable=False)
        batch.create_foreign_key(
            "fk_evidence_org", "organizations", ["org_id"], ["id"], ondelete="RESTRICT"
        )
    op.create_index(
        "idx_gev_chain_link",
        "governance_evidence",
        ["org_id", "prev_hash"],
        unique=True,
        sqlite_where=sa.text("prev_hash IS NOT NULL"),
        postgresql_where=sa.text("prev_hash IS NOT NULL"),
    )
    op.create_index(
        "idx_gev_chain_genesis",
        "governance_evidence",
        ["org_id"],
        unique=True,
        sqlite_where=sa.text("prev_hash IS NULL"),
        postgresql_where=sa.text("prev_hash IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_gev_chain_genesis", table_name="governance_evidence")
    op.drop_index("idx_gev_chain_link", table_name="governance_evidence")
    with op.batch_alter_table("governance_evidence") as batch:
        batch.drop_constraint("fk_evidence_org", type_="foreignkey")
        batch.alter_column("org_id", existing_type=sa.String(36), nullable=True)
