"""Automatic schema migration at startup.

`DatabaseEngine.init()` only calls `metadata.create_all()`, which is
create-only — it makes brand-new tables appear on a fresh install but never
issues an `ALTER TABLE` for a table that already exists. Any self-hosted
deployment created before a migration that adds a column (e.g. 0003's
`organizations.plan`, 0004's `audit_log.entry_hash`) silently keeps the old
schema: the app boots fine and then 500s the first time a request touches
the missing column. That's strictly worse than failing at startup.

This module runs `alembic upgrade head` as a subprocess (not in-process —
`migrations/env.py` calls `asyncio.run()` internally, which cannot be
nested inside the already-running FastAPI event loop) before the app
starts serving traffic. It is idempotent: a database already at head is a
fast no-op.

Bootstrapping onto a pre-existing, pre-Alembic database: every real
ResponsibleAI install that predates this migration system has tables from
`create_all()` but no `alembic_version` table — blind `alembic upgrade head`
on such a database fails immediately trying to CREATE TABLEs that already
exist. Migration 0001 ("Initial schema — all tables") is exactly what
`create_all()` would have produced before any of the later ALTER-adding
migrations existed, so a database with tables but no `alembic_version` is
stamped at 0001 first — marking it as already having the original schema —
before `upgrade head` runs the newer ALTERs on top.

Multi-replica deployments should set `RAI_AUTO_MIGRATE=false` and run this
once as an explicit deploy step instead (see DEPLOY_RUNBOOK.md) — nothing
here coordinates between concurrently-starting replicas.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from sqlalchemy import text

from responsibleai.db.engine import create_engine as _create_db_engine

logger = logging.getLogger(__name__)

_BASELINE_REVISION = "0001"
_PROBE_TABLES = ("alembic_version", "organizations")


class MigrationError(Exception):
    """Raised when `alembic upgrade head` fails or can't be located."""


def _find_alembic_ini() -> Path | None:
    """Look for alembic.ini in cwd, then walk up a few parents.

    Covers both the Docker image (WORKDIR /app, alembic.ini copied there)
    and local development (repo root, wherever the process happens to be
    invoked from).
    """
    candidates = [Path.cwd()] + list(Path.cwd().parents)[:4]
    for base in candidates:
        candidate = base / "alembic.ini"
        if candidate.is_file():
            return candidate
    return None


async def _needs_baseline_stamp(effective_db_url: str) -> bool:
    """True if the DB has pre-existing tables but no tracked alembic revision.

    Checks for an actual revision *row* in alembic_version, not just the
    table's existence — a previous run that failed partway (SQLite DDL is
    non-transactional; see "Will assume non-transactional DDL" in alembic's
    own log output) can leave the table created but empty, which is
    functionally identical to it not existing at all.
    """
    engine = _create_db_engine(effective_db_url)
    try:
        is_sqlite = "sqlite" in str(engine.raw.url)
        async with engine.raw.connect() as conn:
            if is_sqlite:
                rows = await conn.execute(text(
                    "SELECT name FROM sqlite_master WHERE type='table' "
                    "AND name IN ('alembic_version', 'organizations')"
                ))
            else:
                rows = await conn.execute(text(
                    "SELECT table_name AS name FROM information_schema.tables "
                    "WHERE table_schema = 'public' "
                    "AND table_name IN ('alembic_version', 'organizations')"
                ))
            present = {r.name for r in rows.fetchall()}

            has_version_row = False
            if "alembic_version" in present:
                version_rows = await conn.execute(
                    text("SELECT version_num FROM alembic_version LIMIT 1")
                )
                has_version_row = version_rows.first() is not None
    finally:
        await engine.raw.dispose()

    has_preexisting_schema = "organizations" in present
    return has_preexisting_schema and not has_version_row


def _migration_env(effective_db_url: str) -> dict[str, str]:
    env = os.environ.copy()
    env.pop("RAI_DB_URL", None)  # migrations/env.py checks this first — don't let a stale value win
    if effective_db_url.startswith("postgresql") or effective_db_url.startswith("postgres"):
        env["RAI_DATABASE_URL"] = effective_db_url
        env.pop("RAI_DB_PATH", None)
    else:
        env["RAI_DB_PATH"] = effective_db_url
        env.pop("RAI_DATABASE_URL", None)
    return env


async def _run_alembic(ini_path: Path, env: dict[str, str], *args: str) -> None:
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "-c", str(ini_path), *args,
        cwd=str(ini_path.parent),
        env=env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise MigrationError(
            f"alembic {' '.join(args)} failed (exit {proc.returncode}):\n"
            f"{stderr.decode(errors='replace')}\n{stdout.decode(errors='replace')}"
        )


async def run_migrations_or_raise(effective_db_url: str) -> None:
    """Run `alembic upgrade head` against *effective_db_url*.

    Raises MigrationError on any failure. Callers (app startup) should
    treat this as fatal — better to fail loudly before accepting traffic
    than to serve requests against a stale schema.

    *effective_db_url* must be the exact value the app itself resolved
    (`settings.effective_db_url`), passed explicitly rather than relying on
    the subprocess re-reading env vars: `Settings.db_path` has its own
    pydantic default_factory (`~/.responsibleai/data.db`) that only applies
    when `RAI_DB_PATH` is unset — copying `os.environ` blindly means the
    migration subprocess falls back to `migrations/env.py`'s *own*,
    different default and silently migrates the wrong database file.
    """
    ini_path = _find_alembic_ini()
    if ini_path is None:
        raise MigrationError(
            "Could not locate alembic.ini (looked in cwd and parent "
            "directories). Set RAI_AUTO_MIGRATE=false and run migrations "
            "manually, or run the app from a directory containing alembic.ini."
        )

    env = _migration_env(effective_db_url)

    if await _needs_baseline_stamp(effective_db_url):
        logger.info(
            "db_migration_baseline_stamp",
            extra={"revision": _BASELINE_REVISION},
        )
        await _run_alembic(ini_path, env, "stamp", _BASELINE_REVISION)

    await _run_alembic(ini_path, env, "upgrade", "head")
    logger.info("db_migrations_applied", extra={"alembic_ini": str(ini_path)})
