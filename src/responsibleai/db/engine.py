"""Async SQLAlchemy engine factory — SQLite for dev/test, PostgreSQL for production."""

from __future__ import annotations

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
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

metadata = MetaData()

token_usage = Table(
    "token_usage",
    metadata,
    Column("id",            Integer, primary_key=True, autoincrement=True),
    Column("request_id",    String(64),  nullable=False, unique=True),
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
    Index("idx_tu_provider",   "provider"),
    Index("idx_tu_model",      "model"),
    Index("idx_tu_team",       "team"),
    Index("idx_tu_recorded",   "recorded_at"),
)

trust_scores = Table(
    "trust_scores",
    metadata,
    Column("id",           Integer, primary_key=True, autoincrement=True),
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
    Index("idx_ts_model",    "model_name"),
    Index("idx_ts_provider", "provider"),
    Index("idx_ts_recorded", "recorded_at"),
)

organizations = Table(
    "organizations",
    metadata,
    Column("id",                 String(36),  primary_key=True),
    Column("name",               String(200), nullable=False),
    Column("slug",               String(100), nullable=False, unique=True),
    Column("monthly_budget_usd", Float,       nullable=False, default=10_000.0),
    Column("created_at",         String(32),  nullable=False),
    Index("idx_org_slug", "slug"),
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
    Column("ip_address",  String(64),  nullable=True),
    Column("request_id",  String(64),  nullable=True),
    Column("duration_ms", Float,       nullable=True),
    Column("user_agent",  String(512), nullable=True),
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


class DatabaseEngine:
    """Async database engine wrapping SQLAlchemy — SQLite or PostgreSQL."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @property
    def raw(self) -> AsyncEngine:
        return self._engine

    async def init(self) -> None:
        """Create all tables if they don't exist."""
        async with self._engine.begin() as conn:
            if "sqlite" in str(self._engine.url):
                await conn.execute(text("PRAGMA journal_mode=WAL"))
                await conn.execute(text("PRAGMA synchronous=NORMAL"))
            await conn.run_sync(metadata.create_all)

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
