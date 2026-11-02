"""Add trust_passports — real persistence for the open Trust Index standard.

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-22 00:00:00.000000

Backs POST /api/trust-index/assess, GET /api/trust-index/verify/{id},
GET /api/trust-index/certified, and POST /api/trust-index/certify/{id}
(responsibleai.dashboard.app). Also backs POST /api/evaluate, which now
persists its passport here too instead of discarding it after one response —
see compliance/TRUST_INDEX_SPEC.md for why a citable score needs a durable,
independently-verifiable record behind it.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "trust_passports",
        sa.Column("id",                    sa.String(36),  nullable=False),
        sa.Column("org_id",                sa.String(36),  nullable=True),
        sa.Column("source",                sa.String(20),  nullable=False),
        sa.Column("spec_version",          sa.String(20),  nullable=False),
        sa.Column("model_name",            sa.String(100), nullable=False),
        sa.Column("provider",              sa.String(100), nullable=False),
        sa.Column("overall_score",         sa.Float(),     nullable=False),
        sa.Column("grade",                 sa.String(2),   nullable=False),
        sa.Column("risk_level",            sa.String(20),  nullable=False),
        sa.Column("fairness",              sa.Float(),     nullable=False),
        sa.Column("privacy",               sa.Float(),     nullable=False),
        sa.Column("security",              sa.Float(),     nullable=False),
        sa.Column("robustness",            sa.Float(),     nullable=False),
        sa.Column("compliance",            sa.Float(),     nullable=False),
        sa.Column("authenticity",          sa.Float(),     nullable=False),
        sa.Column("bias_summary",          sa.Text(),      nullable=True),
        sa.Column("hallucination_summary", sa.Text(),      nullable=True),
        sa.Column("security_summary",      sa.Text(),      nullable=True),
        sa.Column("compliance_summary",    sa.Text(),      nullable=True),
        sa.Column("privacy_summary",       sa.Text(),      nullable=True),
        sa.Column("generated_at",          sa.String(32),  nullable=False),
        sa.Column("verification_hash",     sa.String(64),  nullable=False),
        sa.Column("certified",             sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("certified_at",          sa.String(32),  nullable=True),
        sa.Column("certified_by",          sa.String(200), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_tp_org",       "trust_passports", ["org_id"])
    op.create_index("idx_tp_model",     "trust_passports", ["model_name", "provider"])
    op.create_index("idx_tp_certified", "trust_passports", ["certified"])
    op.create_index("idx_tp_generated", "trust_passports", ["generated_at"])


def downgrade() -> None:
    op.drop_index("idx_tp_generated", table_name="trust_passports")
    op.drop_index("idx_tp_certified", table_name="trust_passports")
    op.drop_index("idx_tp_model", table_name="trust_passports")
    op.drop_index("idx_tp_org", table_name="trust_passports")
    op.drop_table("trust_passports")
