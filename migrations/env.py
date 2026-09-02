"""Alembic migration environment — async SQLAlchemy (SQLite + PostgreSQL)."""

from __future__ import annotations

import asyncio
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Ensure src/ is on sys.path so responsibleai can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from responsibleai.db.engine import metadata as target_metadata  # noqa: E402
from responsibleai.db.url_resolution import resolve_migration_db_url as _resolve_url  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


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
    url = _resolve_url()
    # Same transaction-pooler fix as db/engine.py's create_engine() — this
    # is a separate engine construction path (Alembic's own), so it needs
    # the fix independently, not automatically inherited from there.
    connect_args = {"statement_cache_size": 0} if url.startswith("postgresql") else {}
    connectable = create_async_engine(url, echo=False, connect_args=connect_args)
    async with connectable.connect() as conn:
        await conn.run_sync(_run_migrations_sync)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
