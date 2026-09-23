# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Worker leases, execution fences, and dispatch outbox.

Revision ID: 0053
Revises: 0052
Create Date: 2026-09-18 00:00:00.000000

Redis is transport only. Lease/fence/outbox rows are infrastructure,
never execution authority. Fence generation advances on every
acquisition and reacquisition so stale workers cannot execute.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0053"
down_revision: str | None = "0052"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ts = sa.DateTime(timezone=True)
    op.create_table(
        "runtime_execution_fences",
        sa.Column(
            "request_id",
            sa.String(length=64),
            sa.ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("current_generation", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("created_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "runtime_worker_leases",
        sa.Column("lease_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(length=64),
            sa.ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "attempt_id",
            sa.String(length=64),
            sa.ForeignKey("runtime_execution_attempts.attempt_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("worker_id", sa.String(length=64), nullable=False),
        sa.Column("lease_generation", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="ACTIVE"),
        sa.Column("acquired_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("heartbeat_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", ts, nullable=False),
        sa.Column("released_at", ts, nullable=True),
        sa.CheckConstraint(
            "status IN ('ACTIVE','COMPLETED','EXPIRED','REVOKED','FAILED')",
            name="chk_lease_status",
        ),
    )
    op.create_index(
        "idx_runtime_worker_leases_generation",
        "runtime_worker_leases",
        ["request_id", "lease_generation"],
        unique=True,
    )
    op.create_table(
        "runtime_execution_dispatch_outbox",
        sa.Column("outbox_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(length=64),
            sa.ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "attempt_id",
            sa.String(length=64),
            sa.ForeignKey("runtime_execution_attempts.attempt_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("publisher_id", sa.String(length=64), nullable=True),
        sa.Column("claimed_at", ts, nullable=True),
        sa.Column("published_at", ts, nullable=True),
        sa.Column("acknowledged_at", ts, nullable=True),
        sa.Column("queue_ticket_id", sa.String(length=64), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "status IN ('PENDING','PUBLISHING','PUBLISHED','ACKNOWLEDGED','CANCELLED','EXPIRED')",
            name="chk_outbox_status",
        ),
    )
    op.create_index(
        "idx_outbox_status_created",
        "runtime_execution_dispatch_outbox",
        ["status", "created_at"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution
            ON runtime_worker_leases (request_id)
            WHERE status = 'ACTIVE'
            """
        )
        op.execute(
            """
            CREATE INDEX idx_runtime_worker_leases_reaper
            ON runtime_worker_leases (status, expires_at)
            WHERE status = 'ACTIVE'
            """
        )
        op.execute(
            """
            CREATE UNIQUE INDEX idx_outbox_active_attempt
            ON runtime_execution_dispatch_outbox (attempt_id)
            WHERE status IN ('PENDING', 'PUBLISHING', 'PUBLISHED')
            """
        )
    else:
        op.create_index(
            "idx_runtime_worker_leases_active_execution",
            "runtime_worker_leases",
            ["request_id"],
        )
        op.create_index(
            "idx_outbox_active_attempt",
            "runtime_execution_dispatch_outbox",
            ["attempt_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("idx_outbox_status_created", table_name="runtime_execution_dispatch_outbox")
    op.drop_index("idx_outbox_active_attempt", table_name="runtime_execution_dispatch_outbox")
    op.drop_table("runtime_execution_dispatch_outbox")
    op.drop_index(
        "idx_runtime_worker_leases_generation", table_name="runtime_worker_leases"
    )
    op.drop_index(
        "idx_runtime_worker_leases_active_execution", table_name="runtime_worker_leases"
    )
    if bind.dialect.name == "postgresql":
        op.drop_index("idx_runtime_worker_leases_reaper", table_name="runtime_worker_leases")
    op.drop_table("runtime_worker_leases")
    op.drop_table("runtime_execution_fences")
