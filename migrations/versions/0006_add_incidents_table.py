"""Add the incidents table — real persistence for governance incident records.

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-21 00:00:00.000000

Backs POST /api/incidents and POST /api/alerts/webhook
(responsibleai.dashboard.app), replacing the previous state where
rai_incident_log's output was ephemeral (returned to the MCP caller but
never stored anywhere server-side) — a gap the 2026-07-21 tabletop drill
(compliance/TABLETOP_EXERCISE_2026-07-21.md) surfaced directly.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "incidents",
        sa.Column("id",                   sa.String(36),  nullable=False),
        sa.Column("created_at",           sa.String(32),  nullable=False),
        sa.Column("org_id",               sa.String(36),  nullable=True),
        sa.Column("source",               sa.String(20),  nullable=False, server_default="manual"),
        sa.Column("incident_type",        sa.String(50),  nullable=False),
        sa.Column("severity",             sa.String(20),  nullable=False),
        sa.Column("siem_event_type",      sa.String(50),  nullable=False),
        sa.Column("model_name",           sa.String(100), nullable=True),
        sa.Column("provider",             sa.String(100), nullable=True),
        sa.Column("description",          sa.Text(),      nullable=False),
        sa.Column("evidence_hash",        sa.String(16),  nullable=False),
        sa.Column("evidence_keys",        sa.Text(),      nullable=True),
        sa.Column("mitigated",            sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("status",               sa.String(20),  nullable=False, server_default="OPEN"),
        sa.Column("sla_resolution_hours", sa.Integer(),   nullable=False, server_default="24"),
        sa.Column("raw_payload",          sa.Text(),      nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_inc_org",      "incidents", ["org_id"])
    op.create_index("idx_inc_created",  "incidents", ["created_at"])
    op.create_index("idx_inc_severity", "incidents", ["severity"])
    op.create_index("idx_inc_status",   "incidents", ["status"])


def downgrade() -> None:
    op.drop_index("idx_inc_status",   table_name="incidents")
    op.drop_index("idx_inc_severity", table_name="incidents")
    op.drop_index("idx_inc_created",  table_name="incidents")
    op.drop_index("idx_inc_org",      table_name="incidents")
    op.drop_table("incidents")
