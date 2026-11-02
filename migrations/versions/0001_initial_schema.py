"""Initial schema — all tables.

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "token_usage",
        sa.Column("id",            sa.Integer(),    nullable=False),
        sa.Column("request_id",    sa.String(64),   nullable=False),
        sa.Column("provider",      sa.String(50),   nullable=False),
        sa.Column("model",         sa.String(100),  nullable=False),
        sa.Column("team",          sa.String(100),  nullable=False, server_default="default"),
        sa.Column("application",   sa.String(100),  nullable=False, server_default="default"),
        sa.Column("input_tokens",  sa.Integer(),    nullable=False),
        sa.Column("output_tokens", sa.Integer(),    nullable=False),
        sa.Column("cached_tokens", sa.Integer(),    nullable=False, server_default="0"),
        sa.Column("input_cost",    sa.Float(),      nullable=False, server_default="0.0"),
        sa.Column("output_cost",   sa.Float(),      nullable=False, server_default="0.0"),
        sa.Column("total_cost",    sa.Float(),      nullable=False, server_default="0.0"),
        sa.Column("prompt_hash",   sa.String(64),   nullable=True),
        sa.Column("metadata",      sa.Text(),       nullable=True),
        sa.Column("recorded_at",   sa.String(32),   nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("request_id"),
    )
    op.create_index("idx_tu_provider",  "token_usage", ["provider"])
    op.create_index("idx_tu_model",     "token_usage", ["model"])
    op.create_index("idx_tu_team",      "token_usage", ["team"])
    op.create_index("idx_tu_recorded",  "token_usage", ["recorded_at"])

    op.create_table(
        "trust_scores",
        sa.Column("id",           sa.Integer(),    nullable=False),
        sa.Column("model_name",   sa.String(100),  nullable=False),
        sa.Column("provider",     sa.String(100),  nullable=False),
        sa.Column("overall",      sa.Float(),      nullable=False),
        sa.Column("grade",        sa.String(2),    nullable=False),
        sa.Column("risk_level",   sa.String(20),   nullable=False),
        sa.Column("fairness",     sa.Float(),      nullable=False),
        sa.Column("privacy",      sa.Float(),      nullable=False),
        sa.Column("security",     sa.Float(),      nullable=False),
        sa.Column("robustness",   sa.Float(),      nullable=False),
        sa.Column("compliance",   sa.Float(),      nullable=False),
        sa.Column("authenticity", sa.Float(),      nullable=False),
        sa.Column("metadata",     sa.Text(),       nullable=True),
        sa.Column("recorded_at",  sa.String(32),   nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_ts_model",    "trust_scores", ["model_name"])
    op.create_index("idx_ts_provider", "trust_scores", ["provider"])
    op.create_index("idx_ts_recorded", "trust_scores", ["recorded_at"])

    op.create_table(
        "organizations",
        sa.Column("id",                 sa.String(36),   nullable=False),
        sa.Column("name",               sa.String(200),  nullable=False),
        sa.Column("slug",               sa.String(100),  nullable=False),
        sa.Column("monthly_budget_usd", sa.Float(),      nullable=False, server_default="10000.0"),
        sa.Column("created_at",         sa.String(32),   nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )
    op.create_index("idx_org_slug", "organizations", ["slug"])

    op.create_table(
        "org_api_keys",
        sa.Column("id",           sa.String(36),   nullable=False),
        sa.Column("org_id",       sa.String(36),   nullable=False),
        sa.Column("key_hash",     sa.String(64),   nullable=False),
        sa.Column("name",         sa.String(200),  nullable=False),
        sa.Column("role",         sa.String(20),   nullable=False, server_default="ANALYST"),
        sa.Column("created_at",   sa.String(32),   nullable=False),
        sa.Column("last_used_at", sa.String(32),   nullable=True),
        sa.Column("revoked",      sa.Integer(),    nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("idx_oak_org",  "org_api_keys", ["org_id"])
    op.create_index("idx_oak_hash", "org_api_keys", ["key_hash"])

    op.create_table(
        "audit_log",
        sa.Column("id",          sa.String(36),   nullable=False),
        sa.Column("timestamp",   sa.String(32),   nullable=False),
        sa.Column("org_id",      sa.String(36),   nullable=True),
        sa.Column("key_id",      sa.String(36),   nullable=True),
        sa.Column("endpoint",    sa.String(256),  nullable=False),
        sa.Column("method",      sa.String(10),   nullable=False),
        sa.Column("status_code", sa.Integer(),    nullable=True),
        sa.Column("ip_address",  sa.String(64),   nullable=True),
        sa.Column("request_id",  sa.String(64),   nullable=True),
        sa.Column("duration_ms", sa.Float(),      nullable=True),
        sa.Column("user_agent",  sa.String(512),  nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_al_timestamp", "audit_log", ["timestamp"])
    op.create_index("idx_al_org",       "audit_log", ["org_id"])
    op.create_index("idx_al_endpoint",  "audit_log", ["endpoint"])

    op.create_table(
        "eval_runs",
        sa.Column("id",         sa.String(36),   nullable=False),
        sa.Column("run_type",   sa.String(20),   nullable=False),
        sa.Column("model",      sa.String(100),  nullable=False),
        sa.Column("provider",   sa.String(100),  nullable=False, server_default=""),
        sa.Column("suite",      sa.String(50),   nullable=True),
        sa.Column("org_id",     sa.String(36),   nullable=True),
        sa.Column("created_at", sa.String(32),   nullable=False),
        sa.Column("payload",    sa.Text(),       nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_er_model",      "eval_runs", ["model"])
    op.create_index("idx_er_run_type",   "eval_runs", ["run_type"])
    op.create_index("idx_er_created_at", "eval_runs", ["created_at"])
    op.create_index("idx_er_org",        "eval_runs", ["org_id"])

    op.create_table(
        "eval_baselines",
        sa.Column("id",         sa.String(36),   nullable=False),
        sa.Column("model",      sa.String(100),  nullable=False),
        sa.Column("suite",      sa.String(50),   nullable=False),
        sa.Column("metric",     sa.String(100),  nullable=False),
        sa.Column("score",      sa.Float(),      nullable=False),
        sa.Column("org_id",     sa.String(36),   nullable=True),
        sa.Column("updated_at", sa.String(32),   nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_eb_model", "eval_baselines", ["model"])
    op.create_index("idx_eb_suite", "eval_baselines", ["suite"])
    op.create_index("idx_eb_org",   "eval_baselines", ["org_id"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id",            sa.String(36),  nullable=False),
        sa.Column("webhook_id",    sa.String(36),  nullable=False),
        sa.Column("event",         sa.String(64),  nullable=False),
        sa.Column("payload",       sa.Text(),      nullable=False),
        sa.Column("status",        sa.String(20),  nullable=False, server_default="pending"),
        sa.Column("attempts",      sa.Integer(),   nullable=False, server_default="0"),
        sa.Column("max_retries",   sa.Integer(),   nullable=False, server_default="3"),
        sa.Column("status_code",   sa.Integer(),   nullable=True),
        sa.Column("last_error",    sa.Text(),      nullable=True),
        sa.Column("created_at",    sa.String(32),  nullable=False),
        sa.Column("next_retry_at", sa.String(32),  nullable=True),
        sa.Column("delivered_at",  sa.String(32),  nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_wd_webhook", "webhook_deliveries", ["webhook_id"])
    op.create_index("idx_wd_status",  "webhook_deliveries", ["status"])
    op.create_index("idx_wd_retry",   "webhook_deliveries", ["next_retry_at"])


def downgrade() -> None:
    op.drop_table("webhook_deliveries")
    op.drop_table("eval_baselines")
    op.drop_table("eval_runs")
    op.drop_table("audit_log")
    op.drop_table("org_api_keys")
    op.drop_table("organizations")
    op.drop_table("trust_scores")
    op.drop_table("token_usage")
