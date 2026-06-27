"""Alembic migration environment — async SQLAlchemy (SQLite + PostgreSQL)."""

from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure src/ is on sys.path so responsibleai can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from responsibleai.db.engine import metadata as target_metadata  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _resolve_url() -> str:
    """Resolve the DB URL from environment variables.

    Priority:
    1. RAI_DB_URL — full SQLAlchemy-style URL
    2. RAI_DB_PATH — file path (converted to sqlite+aiosqlite://)
    3. Falls back to ./governance.db
    """
    raw = (
        os.environ.get("RAI_DB_URL")
        or os.environ.get("RAI_DATABASE_URL")
        or ""
    )
    if raw:
        if raw.startswith("postgresql"):
            raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
            raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
        return raw

    path = os.environ.get("RAI_DB_PATH", "governance.db")
    if path == ":memory:":
        return "sqlite+aiosqlite:///:memory:"
    return f"sqlite+aiosqlite:///{path}"


def run_migrations_offline() -> None:
    """Run migrations using a URL string (no live connection)."""
    url = _resolve_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def _run_migrations_sync(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations with an async engine."""
    connectable = create_async_engine(_resolve_url(), echo=False)
    async with connectable.connect() as conn:
        await conn.run_sync(_run_migrations_sync)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
