# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable containment association before container creation. Revision0066."""

import sqlalchemy as sa
from alembic import op

revision = "0066"
down_revision = "0065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "runtime_containment_records",
        sa.Column("execution_id", sa.String(64), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("owner_generation", sa.String(64), nullable=False),
        sa.Column("backend_identity", sa.String(128), nullable=False),
        sa.Column("authorization_id", sa.String(64), nullable=False),
        sa.Column("action_digest", sa.String(64), nullable=False),
        sa.Column("admission_epoch", sa.Integer, nullable=False),
        sa.Column("expected_container_name", sa.String(128), nullable=False),
        sa.Column("container_id", sa.String(64)),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("created_at", sa.String(32), nullable=False),
        sa.Column("updated_at", sa.String(32), nullable=False),
        sa.CheckConstraint(
            "state IN ('PREPARING','ACTIVE','UNRESOLVED','CONTAINED')",
            name="chk_runtime_containment_state",
        ),
        sa.CheckConstraint("admission_epoch >= 0", name="chk_runtime_containment_epoch"),
        sa.CheckConstraint(
            "state NOT IN ('ACTIVE','CONTAINED') OR container_id IS NOT NULL",
            name="chk_runtime_containment_receipt",
        ),
    )
    op.create_index(
        "idx_runtime_containment_org_state",
        "runtime_containment_records",
        ["organization_id", "state"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        conn.execute(sa.text("LOCK TABLE runtime_containment_records IN ACCESS EXCLUSIVE MODE"))
    if conn.scalar(sa.text("SELECT count(*) FROM runtime_containment_records")):
        raise RuntimeError("Downgrade refused: runtime containment evidence must be retained")
    op.drop_index("idx_runtime_containment_org_state", table_name="runtime_containment_records")
    op.drop_table("runtime_containment_records")
