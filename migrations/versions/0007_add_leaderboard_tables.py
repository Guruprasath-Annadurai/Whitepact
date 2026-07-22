"""Add leaderboard_models and leaderboard_runs — the public cross-model trust leaderboard.

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-22 00:00:00.000000

Backs GET /api/leaderboard (public), GET /api/leaderboard/{model}/{provider}/history
(public), GET /api/leaderboard/{model}/{provider}/diagnostic (PRO/ENTERPRISE gated),
and the admin registry/run-trigger endpoints in responsibleai.dashboard.app. Neither
table carries an org_id — this data is global and public by design.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "leaderboard_models",
        sa.Column("id",           sa.String(36),  nullable=False),
        sa.Column("model",        sa.String(100), nullable=False),
        sa.Column("provider",     sa.String(50),  nullable=False),
        sa.Column("display_name", sa.String(150), nullable=True),
        sa.Column("adapter",      sa.String(20),  nullable=False, server_default="mock"),
        sa.Column("active",       sa.Integer(),   nullable=False, server_default="1"),
        sa.Column("added_at",     sa.String(32),  nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lbm_active", "leaderboard_models", ["active"])
    op.create_index(
        "idx_lbm_model_provider", "leaderboard_models", ["model", "provider"], unique=True,
    )

    op.create_table(
        "leaderboard_runs",
        sa.Column("id",                     sa.String(36),  nullable=False),
        sa.Column("model",                  sa.String(100), nullable=False),
        sa.Column("provider",               sa.String(50),  nullable=False),
        sa.Column("created_at",             sa.String(32),  nullable=False),
        sa.Column("methodology_version",    sa.String(20),  nullable=False),
        sa.Column("overall_score",          sa.Float(),     nullable=False),
        sa.Column("grade",                  sa.String(2),   nullable=False),
        sa.Column("risk_level",             sa.String(20),  nullable=False),
        sa.Column("fairness",               sa.Float(),     nullable=False),
        sa.Column("privacy",                sa.Float(),     nullable=False),
        sa.Column("security",               sa.Float(),     nullable=False),
        sa.Column("robustness",             sa.Float(),     nullable=False),
        sa.Column("compliance",             sa.Float(),     nullable=False),
        sa.Column("authenticity",           sa.Float(),     nullable=False),
        sa.Column("dimensions_live",        sa.Text(),      nullable=False),
        sa.Column("truthfulqa_accuracy",    sa.Float(),     nullable=False),
        sa.Column("bbq_bias_rate",          sa.Float(),     nullable=False),
        sa.Column("hellaswag_accuracy",     sa.Float(),     nullable=False),
        sa.Column("security_score",         sa.Float(),     nullable=False),
        sa.Column("privacy_pii_leak_rate",  sa.Float(),     nullable=False),
        sa.Column("avg_hallucination_risk", sa.Float(),     nullable=False),
        sa.Column("sample_size",            sa.Integer(),   nullable=False),
        sa.Column("findings",               sa.Text(),      nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lbr_model_provider", "leaderboard_runs", ["model", "provider"])
    op.create_index("idx_lbr_created", "leaderboard_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_lbr_created", table_name="leaderboard_runs")
    op.drop_index("idx_lbr_model_provider", table_name="leaderboard_runs")
    op.drop_table("leaderboard_runs")

    op.drop_index("idx_lbm_model_provider", table_name="leaderboard_models")
    op.drop_index("idx_lbm_active", table_name="leaderboard_models")
    op.drop_table("leaderboard_models")
