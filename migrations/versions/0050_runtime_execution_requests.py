# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable immutable runtime execution requests.

Revision ID: 0050
Revises: 0049
Create Date: 2026-09-18 00:00:00.000000

The request row is evidence and admission state. It is NOT execution
authority. Lifecycle is RECORDED only; operational progress lives on
attempts. UPDATE/DELETE are rejected by trigger.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0050"
down_revision: str | None = "0049"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    json_type: sa.types.TypeEngine = (
        postgresql.JSONB() if bind.dialect.name == "postgresql" else sa.JSON()
    )
    ts = sa.DateTime(timezone=True)
    op.create_table(
        "runtime_execution_requests",
        sa.Column("request_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
        sa.Column("principal_id", sa.String(length=64), nullable=False),
        sa.Column("agent_id", sa.String(length=64), nullable=False),
        sa.Column("identity_id", sa.String(length=64), nullable=False),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("target", sa.String(length=256), nullable=False),
        sa.Column("action_digest", sa.String(length=64), nullable=False),
        sa.Column("target_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("canonical_action_payload", sa.Text(), nullable=False),
        sa.Column("approved_arguments", json_type, nullable=False),
        sa.Column("observed_governance_epoch", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "approval_id",
            sa.String(length=36),
            sa.ForeignKey("governance_approvals.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("server_id", sa.String(length=128), nullable=True),
        sa.Column(
            "lifecycle",
            sa.String(length=16),
            nullable=False,
            server_default="RECORDED",
        ),
        sa.Column("created_at", ts, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("lifecycle = 'RECORDED'", name="chk_exec_req_lifecycle"),
    )
    op.create_index(
        "idx_exec_req_org_idempotency",
        "runtime_execution_requests",
        ["organization_id", "idempotency_key"],
        unique=True,
    )
    op.create_index(
        "idx_exec_req_action_digest",
        "runtime_execution_requests",
        ["organization_id", "action_digest"],
    )
    op.create_index(
        "idx_exec_req_org_created",
        "runtime_execution_requests",
        ["organization_id", "created_at"],
    )
    if bind.dialect.name == "postgresql":
        op.execute(
            """
            CREATE OR REPLACE FUNCTION reject_execution_request_mutation()
            RETURNS TRIGGER AS $$
            BEGIN
                RAISE EXCEPTION
                    'runtime_execution_requests is immutable and append-only: UPDATE and DELETE are prohibited';
            END;
            $$ LANGUAGE plpgsql;
            """
        )
        op.execute(
            """
            CREATE TRIGGER prevent_execution_request_mutation
            BEFORE UPDATE OR DELETE ON runtime_execution_requests
            FOR EACH ROW EXECUTE FUNCTION reject_execution_request_mutation();
            """
        )
    else:
        op.execute(
            """
            CREATE TRIGGER prevent_execution_request_update
            BEFORE UPDATE ON runtime_execution_requests
            BEGIN
                SELECT RAISE(ABORT, 'runtime_execution_requests is immutable');
            END;
            """
        )
        op.execute(
            """
            CREATE TRIGGER prevent_execution_request_delete
            BEFORE DELETE ON runtime_execution_requests
            BEGIN
                SELECT RAISE(ABORT, 'runtime_execution_requests is immutable');
            END;
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS prevent_execution_request_mutation ON runtime_execution_requests")
        op.execute("DROP FUNCTION IF EXISTS reject_execution_request_mutation()")
    else:
        op.execute("DROP TRIGGER IF EXISTS prevent_execution_request_update")
        op.execute("DROP TRIGGER IF EXISTS prevent_execution_request_delete")
    op.drop_index("idx_exec_req_org_created", table_name="runtime_execution_requests")
    op.drop_index("idx_exec_req_action_digest", table_name="runtime_execution_requests")
    op.drop_index("idx_exec_req_org_idempotency", table_name="runtime_execution_requests")
    op.drop_table("runtime_execution_requests")
