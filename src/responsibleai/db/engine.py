"""Async SQLAlchemy engine factory — SQLite for dev/test, PostgreSQL for production."""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import (
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from responsibleai.db.encryption import EncryptedString

logger = logging.getLogger(__name__)

metadata = MetaData()

token_usage = Table(
    "token_usage",
    metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("request_id",    String(64),  nullable=False, unique=True),
    Column("org_id",        String(36),  nullable=True),
    Column("provider",      String(50),  nullable=False),
    Column("model",         String(100), nullable=False),
    Column("team",          String(100), nullable=False, default="default"),
    Column("application",   String(100), nullable=False, default="default"),
    Column("input_tokens",  Integer,     nullable=False),
    Column("output_tokens", Integer,     nullable=False),
    Column("cached_tokens", Integer,     nullable=False, default=0),
    Column("input_cost",    Float,       nullable=False, default=0.0),
    Column("output_cost",   Float,       nullable=False, default=0.0),
    Column("total_cost",    Float,       nullable=False, default=0.0),
    Column("prompt_hash",   String(64),  nullable=True),
    Column("metadata",      Text,        nullable=True),
    Column("recorded_at",   String(32),  nullable=False),
    Index("idx_tu_org",        "org_id"),
    Index("idx_tu_provider",   "provider"),
    Index("idx_tu_model",      "model"),
    Index("idx_tu_team",       "team"),
    Index("idx_tu_recorded",   "recorded_at"),
)

trust_scores = Table(
    "trust_scores",
    metadata,
    Column("id",           Integer, primary_key=True, autoincrement=True),
    Column("org_id",       String(36),  nullable=True),
    Column("model_name",   String(100), nullable=False),
    Column("provider",     String(100), nullable=False),
    Column("overall",      Float,       nullable=False),
    Column("grade",        String(2),   nullable=False),
    Column("risk_level",   String(20),  nullable=False),
    Column("fairness",     Float,       nullable=False),
    Column("privacy",      Float,       nullable=False),
    Column("security",     Float,       nullable=False),
    Column("robustness",   Float,       nullable=False),
    Column("compliance",   Float,       nullable=False),
    Column("authenticity", Float,       nullable=False),
    Column("metadata",     Text,        nullable=True),
    Column("recorded_at",  String(32),  nullable=False),
    Index("idx_ts_org",      "org_id"),
    Index("idx_ts_model",    "model_name"),
    Index("idx_ts_provider", "provider"),
    Index("idx_ts_recorded", "recorded_at"),
)

organizations = Table(
    "organizations",
    metadata,
    Column("id",                      String(36),  primary_key=True),
    Column("name",                    String(200), nullable=False),
    Column("slug",                    String(100), nullable=False, unique=True),
    Column("monthly_budget_usd",      Float,       nullable=False, default=10_000.0),
    Column("created_at",              String(32),  nullable=False),
    Column("plan",                    String(20),  nullable=False, default="FREE"),
    Column("stripe_customer_id",      String(64),  nullable=True),
    Column("stripe_subscription_id",  String(64),  nullable=True),
    Column("plan_renews_at",          String(32),  nullable=True),
    Column("sso_required",            Integer,     nullable=False, default=0),
    Column("mfa_required",            Integer,     nullable=False, default=0),
    Index("idx_org_slug", "slug"),
    Index("idx_org_stripe_customer", "stripe_customer_id"),
)

mcp_tool_calls = Table(
    "mcp_tool_calls",
    metadata,
    Column("id",        String(36),  primary_key=True),
    Column("org_id",    String(36),  nullable=True),
    Column("tool_name", String(64),  nullable=False),
    Column("tier",      String(20),  nullable=False),
    Column("timestamp", String(32),  nullable=False),
    Column("allowed",   Integer,     nullable=False, default=1),
    Index("idx_mcp_calls_org", "org_id"),
    Index("idx_mcp_calls_ts",  "timestamp"),
)

org_api_keys = Table(
    "org_api_keys",
    metadata,
    Column("id",           String(36),  primary_key=True),
    Column("org_id",       String(36),  nullable=False),
    Column("key_hash",     String(64),  nullable=False, unique=True),
    Column("name",         String(200), nullable=False),
    Column("role",         String(20),  nullable=False, default="ANALYST"),
    Column("created_at",   String(32),  nullable=False),
    Column("last_used_at", String(32),  nullable=True),
    Column("revoked",      Integer,     nullable=False, default=0),
    # TOTP MFA (RFC 6238) — see auth/mfa.py. mfa_secret is opt-in encrypted
    # (EncryptedString, see db/encryption.py); mfa_backup_codes is a JSON list
    # of SHA-256 hashes, each single-use. enrolled=0 until the first
    # verify() call succeeds, so a secret that was issued but never
    # confirmed can't silently gate login.
    Column("mfa_secret",       EncryptedString(), nullable=True),
    Column("mfa_enrolled",     Integer,     nullable=False, default=0),
    Column("mfa_backup_codes", Text,        nullable=True),
    Index("idx_oak_org",  "org_id"),
    Index("idx_oak_hash", "key_hash"),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id",          String(36),  primary_key=True),
    Column("timestamp",   String(32),  nullable=False),
    Column("org_id",      String(36),  nullable=True),
    Column("key_id",      String(36),  nullable=True),
    Column("endpoint",    String(256), nullable=False),
    Column("method",      String(10),  nullable=False),
    Column("status_code", Integer,     nullable=True),
    # EncryptedString: opt-in via RAI_FIELD_ENCRYPTION_KEY (see db/encryption.py).
    # Stored as Text (not a fixed-width String) to fit Fernet ciphertext,
    # which is longer than a raw IP address — see migration 0005.
    Column("ip_address",  EncryptedString(),  nullable=True),
    Column("request_id",  String(64),  nullable=True),
    Column("duration_ms", Float,       nullable=True),
    Column("user_agent",  String(512), nullable=True),
    Column("entry_hash",  String(64),  nullable=True),
    Column("prev_hash",   String(64),  nullable=True),
    Index("idx_al_timestamp", "timestamp"),
    Index("idx_al_org",       "org_id"),
    Index("idx_al_endpoint",  "endpoint"),
)

eval_runs = Table(
    "eval_runs",
    metadata,
    Column("id",          String(36),   primary_key=True),
    Column("run_type",    String(20),   nullable=False),   # "comparison" | "benchmark" | "dataset_scan"
    Column("model",       String(100),  nullable=False),
    Column("provider",    String(100),  nullable=False, default=""),
    Column("suite",       String(50),   nullable=True),
    Column("org_id",      String(36),   nullable=True),
    Column("created_at",  String(32),   nullable=False),
    Column("payload",     Text,         nullable=False),   # JSON-serialised result dict
    Index("idx_er_model",      "model"),
    Index("idx_er_run_type",   "run_type"),
    Index("idx_er_created_at", "created_at"),
    Index("idx_er_org",        "org_id"),
)

eval_baselines = Table(
    "eval_baselines",
    metadata,
    Column("id",         String(36),  primary_key=True),
    Column("model",      String(100), nullable=False),
    Column("suite",      String(50),  nullable=False),
    Column("metric",     String(100), nullable=False),
    Column("score",      Float,       nullable=False),
    Column("org_id",     String(36),  nullable=True),
    Column("updated_at", String(32),  nullable=False),
    Index("idx_eb_model",  "model"),
    Index("idx_eb_suite",  "suite"),
    Index("idx_eb_org",    "org_id"),
)

webhook_configs = Table(
    "webhook_configs",
    metadata,
    Column("id",           String(36),  primary_key=True),
    Column("org_id",       String(36),  nullable=True),  # null = legacy/dev flat-key registration
    Column("url",          String(2048), nullable=False),
    Column("provider",     String(20),  nullable=False, default="generic"),
    Column("events",       Text,        nullable=False),   # JSON list of WebhookEvent values
    Column("secret",       EncryptedString(), nullable=True),  # HMAC signing secret — opt-in encrypted
    Column("description",  String(500), nullable=True),
    Column("enabled",      Integer,     nullable=False, default=1),
    Column("max_retries",  Integer,     nullable=False, default=3),
    Column("created_at",   String(32),  nullable=False),
    Index("idx_wc_org",     "org_id"),
    Index("idx_wc_enabled", "enabled"),
)

webhook_deliveries = Table(
    "webhook_deliveries",
    metadata,
    Column("id",            String(36),  primary_key=True),
    Column("webhook_id",    String(36),  nullable=False),
    Column("event",         String(64),  nullable=False),
    Column("payload",       Text,        nullable=False),   # JSON
    Column("status",        String(20),  nullable=False, default="pending"),
    Column("attempts",      Integer,     nullable=False, default=0),
    Column("max_retries",   Integer,     nullable=False, default=3),
    Column("status_code",   Integer,     nullable=True),
    Column("last_error",    Text,        nullable=True),
    Column("created_at",    String(32),  nullable=False),
    Column("next_retry_at", String(32),  nullable=True),
    Column("delivered_at",  String(32),  nullable=True),
    Index("idx_wd_webhook",  "webhook_id"),
    Index("idx_wd_status",   "status"),
    Index("idx_wd_retry",    "next_retry_at"),
)

incidents = Table(
    "incidents",
    metadata,
    Column("id",                    String(36),  primary_key=True),
    Column("created_at",            String(32),  nullable=False),
    Column("org_id",                String(36),  nullable=True),
    # "manual" (POST /api/incidents) | "alertmanager" (POST /api/alerts/webhook) | "mcp_tool" (informational only, never persisted from there directly)
    Column("source",                String(20),  nullable=False, default="manual"),
    Column("incident_type",         String(50),  nullable=False),
    Column("severity",              String(20),  nullable=False),
    Column("siem_event_type",       String(50),  nullable=False),
    Column("model_name",            String(100), nullable=True),
    Column("provider",              String(100), nullable=True),
    Column("description",           Text,        nullable=False),
    Column("evidence_hash",         String(16),  nullable=False),
    Column("evidence_keys",         Text,        nullable=True),   # JSON list
    Column("mitigated",             Integer,     nullable=False, default=0),
    Column("status",                String(20),  nullable=False, default="OPEN"),
    Column("sla_resolution_hours",  Integer,     nullable=False, default=24),
    Column("raw_payload",           Text,        nullable=True),   # JSON — original alert payload, for source=alertmanager
    Index("idx_inc_org",       "org_id"),
    Index("idx_inc_created",   "created_at"),
    Index("idx_inc_severity",  "severity"),
    Index("idx_inc_status",    "status"),
)

leaderboard_models = Table(
    "leaderboard_models",
    metadata,
    Column("id",           String(36),  primary_key=True),
    Column("model",        String(100), nullable=False),
    Column("provider",     String(50),  nullable=False),
    Column("display_name", String(150), nullable=True),
    Column("adapter",      String(20),  nullable=False, default="mock"),  # "openai"|"anthropic"|"google"|"mock"
    Column("active",       Integer,     nullable=False, default=1),
    Column("added_at",     String(32),  nullable=False),
    Index("idx_lbm_active",         "active"),
    Index("idx_lbm_model_provider", "model", "provider", unique=True),
)

leaderboard_runs = Table(
    "leaderboard_runs",
    metadata,
    Column("id",                     String(36),  primary_key=True),
    Column("model",                  String(100), nullable=False),
    Column("provider",               String(50),  nullable=False),
    Column("created_at",             String(32),  nullable=False),
    Column("methodology_version",    String(20),  nullable=False),
    Column("overall_score",          Float,       nullable=False),
    Column("grade",                  String(2),   nullable=False),
    Column("risk_level",             String(20),  nullable=False),
    Column("fairness",               Float,       nullable=False),
    Column("privacy",                Float,       nullable=False),
    Column("security",               Float,       nullable=False),
    Column("robustness",             Float,       nullable=False),
    Column("compliance",             Float,       nullable=False),
    Column("authenticity",           Float,       nullable=False),
    Column("dimensions_live",        Text,        nullable=False),  # JSON: {dim: bool}
    Column("truthfulqa_accuracy",    Float,       nullable=False),
    Column("bbq_bias_rate",          Float,       nullable=False),
    Column("hellaswag_accuracy",     Float,       nullable=False),
    Column("security_score",         Float,       nullable=False),
    Column("privacy_pii_leak_rate",  Float,       nullable=False),
    Column("avg_hallucination_risk", Float,       nullable=False),
    Column("sample_size",            Integer,     nullable=False),
    Column("findings",               Text,        nullable=False),  # JSON list — the paid diagnostic
    Index("idx_lbr_model_provider", "model", "provider"),
    Index("idx_lbr_created",        "created_at"),
)

trust_passports = Table(
    "trust_passports",
    metadata,
    Column("id",                      String(36),  primary_key=True),  # passport_id
    Column("org_id",                  String(36),  nullable=True),     # null for public self-assessments
    Column("source",                  String(20),  nullable=False),    # "evaluate" | "self_assessment"
    Column("spec_version",            String(20),  nullable=False),
    Column("model_name",              String(100), nullable=False),
    Column("provider",                String(100), nullable=False),
    Column("overall_score",           Float,       nullable=False),
    Column("grade",                   String(2),   nullable=False),
    Column("risk_level",              String(20),  nullable=False),
    Column("fairness",                Float,       nullable=False),
    Column("privacy",                 Float,       nullable=False),
    Column("security",                Float,       nullable=False),
    Column("robustness",              Float,       nullable=False),
    Column("compliance",              Float,       nullable=False),
    Column("authenticity",            Float,       nullable=False),
    Column("bias_summary",            Text,        nullable=True),   # JSON
    Column("hallucination_summary",   Text,        nullable=True),   # JSON
    Column("security_summary",        Text,        nullable=True),   # JSON
    Column("compliance_summary",      Text,        nullable=True),   # JSON
    Column("privacy_summary",         Text,        nullable=True),   # JSON
    Column("generated_at",            String(32),  nullable=False),
    Column("verification_hash",       String(64),  nullable=False),
    Column("certified",               Integer,     nullable=False, default=0),
    Column("certified_at",            String(32),  nullable=True),
    Column("certified_by",            String(200), nullable=True),
    Index("idx_tp_org",       "org_id"),
    Index("idx_tp_model",     "model_name", "provider"),
    Index("idx_tp_certified", "certified"),
    Index("idx_tp_generated", "generated_at"),
)

public_incident_reports = Table(
    "public_incident_reports",
    metadata,
    Column("id",                String(36),  primary_key=True),  # internal ID, always present
    Column("public_id",         String(20),  nullable=True, unique=True),  # "RAI-YYYY-NNNN", set on publish
    Column("status",            String(20),  nullable=False, default="PENDING_REVIEW"),
    Column("title",             String(300), nullable=False),
    Column("description",       Text,        nullable=False),
    Column("incident_type",     String(50),  nullable=False),
    Column("severity",          String(20),  nullable=False),
    Column("affected_model",    String(100), nullable=False),
    Column("affected_provider", String(100), nullable=False),
    Column("affected_version",  String(100), nullable=True),
    Column("reporter_name",     EncryptedString(), nullable=True),  # null = anonymous; PII — opt-in encrypted
    Column("reporter_contact",  EncryptedString(), nullable=True),  # PII — opt-in encrypted, never public
    Column("evidence",          Text,        nullable=True),  # JSON: {urls: [...], reproduction_steps: "..."}
    Column("tags",              Text,        nullable=True),  # JSON list
    Column("submitted_at",      String(32),  nullable=False),
    Column("reviewed_at",       String(32),  nullable=True),
    Column("reviewed_by",       String(200), nullable=True),
    Column("rejection_reason",  Text,        nullable=True),
    Column("published_at",      String(32),  nullable=True),
    Column("entry_hash",        String(64),  nullable=True),
    Column("prev_hash",         String(64),  nullable=True),
    Index("idx_pir_status",       "status"),
    Index("idx_pir_model",        "affected_model", "affected_provider"),
    Index("idx_pir_severity",     "severity"),
    Index("idx_pir_submitted",    "submitted_at"),
    Index("idx_pir_published_at", "published_at"),
)


class DatabaseEngine:
    """Async database engine wrapping SQLAlchemy — SQLite or PostgreSQL.

    What "no automated failover" still means, stated plainly: actually
    promoting a replica to primary (Patroni, RDS/Cloud SQL Multi-AZ,
    Postgres streaming replication) is infrastructure the deployer owns —
    no amount of application code can substitute for it. What this class
    *does* do is tolerate the transient connection failures that happen
    during that window — a container restarting into a DNS name that
    hasn't repointed yet, a managed database finishing a failover a few
    seconds after the app tries to connect — by retrying with backoff
    instead of crashing hard on the first attempt. That's a real, scoped
    improvement, not a claim of full HA.
    """

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def raw(self) -> AsyncEngine:
        return self._engine

    async def init(self, *, max_attempts: int = 5, base_delay_seconds: float = 1.0) -> None:
        """Create all tables if they don't exist.

        Retries transient connection failures (OperationalError/DBAPIError —
        covers "connection refused", "server closed the connection
        unexpectedly", DNS not yet repointed after a failover) with capped
        exponential backoff before giving up. SQLite's local file is never
        actually unavailable this way, so this loop is a same-attempt no-op
        there; it matters for Postgres against a managed/replicated backend.
        """
        attempt = 0
        while True:
            try:
                async with self._engine.begin() as conn:
                    if "sqlite" in str(self._engine.url):
                        await conn.execute(text("PRAGMA journal_mode=WAL"))
                        await conn.execute(text("PRAGMA synchronous=NORMAL"))
                    await conn.run_sync(metadata.create_all)
                return
            except (OperationalError, DBAPIError):
                attempt += 1
                if attempt >= max_attempts:
                    raise
                delay = base_delay_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "db_connect_retry",
                    extra={"attempt": attempt, "max_attempts": max_attempts, "delay_seconds": delay},
                )
                await asyncio.sleep(delay)

    async def connect(self) -> AsyncConnection:
        return await self._engine.connect()

    async def close(self) -> None:
        await self._engine.dispose()


def create_engine(db_url: str) -> DatabaseEngine:
    """
    Build the right async engine from a URL string.

    - ``":memory:"`` or SQLite path → ``sqlite+aiosqlite``
    - ``"postgresql://..."``         → ``postgresql+asyncpg``
    """
    if db_url.startswith("postgresql"):
        url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        engine = create_async_engine(
            url,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    elif db_url == ":memory:":
        engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            connect_args={"check_same_thread": False},
            echo=False,
        )
    else:
        engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_url}",
            connect_args={"check_same_thread": False},
            echo=False,
        )

    return DatabaseEngine(engine)
