# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable runtime execution attempts, independent of requests and authorizations.

Revision ID: 0052
Revises: 0051
Create Date: 2026-09-18 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0052"
down_revision: str | None = "0051"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    ts = sa.DateTime(timezone=True)
    op.create_table(
        "runtime_execution_attempts",
        sa.Column("attempt_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "request_id",
            sa.String(length=64),
            sa.ForeignKey("runtime_execution_requests.request_id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "authorization_id",
            sa.String(length=64),
            sa.ForeignKey(
                "governance_execution_authorizations.authorization_id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("worker_id", sa.String(length=64), nullable=True),
        sa.Column("lease_id", sa.String(length=64), nullable=True),
        sa.Column("lease_generation", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("effect_id", sa.String(length=64), nullable=False),
        sa.Column("effect_state", sa.String(length=32), nullable=False, server_default="NO_EFFECT"),
        sa.Column("evidence_status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("backend_start_token_hash", sa.String(length=64), nullable=True),
        sa.Column("pre_effect_decision", sa.String(length=32), nullable=True),
        sa.Column("reconciliation_state", sa.String(length=32), nullable=True),
        sa.Column("admitted_at", ts, nullable=True),
        sa.Column("backend_started_at", ts, nullable=True),
        sa.Column("effect_claimed_at", ts, nullable=True),
        sa.Column("completed_at", ts, nullable=True),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "state IN ('PENDING','LEASED','ADMITTED','BACKEND_STARTING','RUNNING',"
            "'COMPLETED','FAILED_PRE_EXECUTION','FAILED','UNCERTAIN')",
            name="chk_attempt_state",
        ),
        sa.CheckConstraint(
            "effect_state IN ('NO_EFFECT','EFFECT_STARTING','EFFECT_TRANSMITTING',"
            "'EFFECT_CONFIRMED','EFFECT_FAILED','EFFECT_UNCERTAIN')",
            name="chk_effect_state",
        ),
        sa.CheckConstraint(
            "evidence_status IN ('PENDING','COMMITTED','INCOMPLETE')",
            name="chk_attempt_evidence_status",
        ),
        sa.CheckConstraint(
            """
            (
                state = 'PENDING'
                AND worker_id IS NULL
                AND lease_id IS NULL
                AND lease_generation IS NULL
            )
            OR
            (
                state = 'FAILED_PRE_EXECUTION'
                AND (
                    (worker_id IS NULL AND lease_id IS NULL AND lease_generation IS NULL)
                    OR
                    (worker_id IS NOT NULL AND lease_id IS NOT NULL AND lease_generation IS NOT NULL)
                )
            )
            OR
            (
                state IN ('LEASED','ADMITTED','BACKEND_STARTING','RUNNING','COMPLETED','FAILED','UNCERTAIN')
                AND worker_id IS NOT NULL
                AND lease_id IS NOT NULL
                AND lease_generation IS NOT NULL
            )
            """,
            name="chk_attempt_lease_fields",
        ),
    )
    op.create_index(
        "idx_attempt_exec_number",
        "runtime_execution_attempts",
        ["request_id", "attempt_number"],
        unique=True,
    )
    op.create_index(
        "idx_attempt_effect_id",
        "runtime_execution_attempts",
        ["effect_id"],
        unique=True,
    )
    op.create_index(
        "idx_attempt_auth_id",
        "runtime_execution_attempts",
        ["authorization_id"],
    )
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE UNIQUE INDEX idx_attempt_active_execution
            ON runtime_execution_attempts (request_id)
            WHERE state IN ('LEASED', 'ADMITTED', 'BACKEND_STARTING', 'RUNNING')
            """
        )
    else:
        op.create_index(
            "idx_attempt_active_execution",
            "runtime_execution_attempts",
            ["request_id"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    op.drop_index("idx_attempt_auth_id", table_name="runtime_execution_attempts")
    op.drop_index("idx_attempt_effect_id", table_name="runtime_execution_attempts")
    op.drop_index("idx_attempt_exec_number", table_name="runtime_execution_attempts")
    op.drop_index("idx_attempt_active_execution", table_name="runtime_execution_attempts")
    op.drop_table("runtime_execution_attempts")
    _ = bind
