"""Add public_incident_reports — the public, crowd-reported AI Incident Database.

Revision ID: 0009
Revises: 0008
Create Date: 2026-07-22 00:00:00.000000

Distinct from the private `incidents` table (a single org's own operational
incidents) — this is a moderated, publicly disclosed registry of AI failures
across any model/provider, modeled on how CVE became critical infrastructure
without MITRE needing to be the biggest security vendor. Backs
POST /api/incident-db/report, GET /api/incident-db, GET /api/incident-db/{id},
GET /api/incident-db/check (paid pre-deployment check), GET /api/incident-db/verify,
and the admin review endpoints in responsibleai.dashboard.app.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "public_incident_reports",
        sa.Column("id",                sa.String(36),  nullable=False),
        sa.Column("public_id",         sa.String(20),  nullable=True),
        sa.Column("status",            sa.String(20),  nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("title",             sa.String(300), nullable=False),
        sa.Column("description",       sa.Text(),      nullable=False),
        sa.Column("incident_type",     sa.String(50),  nullable=False),
        sa.Column("severity",          sa.String(20),  nullable=False),
        sa.Column("affected_model",    sa.String(100), nullable=False),
        sa.Column("affected_provider", sa.String(100), nullable=False),
        sa.Column("affected_version",  sa.String(100), nullable=True),
        sa.Column("reporter_name",     sa.String(200), nullable=True),
        sa.Column("reporter_contact",  sa.Text(),      nullable=True),  # EncryptedString -> Text
        sa.Column("evidence",          sa.Text(),      nullable=True),
        sa.Column("tags",              sa.Text(),      nullable=True),
        sa.Column("submitted_at",      sa.String(32),  nullable=False),
        sa.Column("reviewed_at",       sa.String(32),  nullable=True),
        sa.Column("reviewed_by",       sa.String(200), nullable=True),
        sa.Column("rejection_reason",  sa.Text(),      nullable=True),
        sa.Column("published_at",      sa.String(32),  nullable=True),
        sa.Column("entry_hash",        sa.String(64),  nullable=True),
        sa.Column("prev_hash",         sa.String(64),  nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_id"),
    )
    op.create_index("idx_pir_status", "public_incident_reports", ["status"])
    op.create_index("idx_pir_model", "public_incident_reports", ["affected_model", "affected_provider"])
    op.create_index("idx_pir_severity", "public_incident_reports", ["severity"])
    op.create_index("idx_pir_submitted", "public_incident_reports", ["submitted_at"])
    op.create_index("idx_pir_published_at", "public_incident_reports", ["published_at"])


def downgrade() -> None:
    op.drop_index("idx_pir_published_at", table_name="public_incident_reports")
    op.drop_index("idx_pir_submitted", table_name="public_incident_reports")
    op.drop_index("idx_pir_severity", table_name="public_incident_reports")
    op.drop_index("idx_pir_model", table_name="public_incident_reports")
    op.drop_index("idx_pir_status", table_name="public_incident_reports")
    op.drop_table("public_incident_reports")
