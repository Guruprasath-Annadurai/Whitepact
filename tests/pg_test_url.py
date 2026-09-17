# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Resolve an isolated PostgreSQL admin URL for tests.

Never points at production defaults. Candidates, in order:

1. ``WHITEPACT_TEST_PG_ADMIN_URL`` (explicit disposable instance)
2. TCP ``127.0.0.1:55432`` user ``wp`` (verified isolated test instance)
3. Unix socket ``/tmp/pg-run`` user ``wp``
4. Legacy unix socket ``/tmp`` user ``ag`` (older local layouts)

Production ``RAI_DATABASE_URL`` / ``Settings.database_url`` are not consulted.
"""

from __future__ import annotations

import atexit
import os
from collections.abc import AsyncGenerator
from urllib.parse import urlparse, urlunparse

_CANDIDATES: tuple[str, ...] = (
    os.environ.get("WHITEPACT_TEST_PG_ADMIN_URL", ""),
    "postgresql://wp:wp@127.0.0.1:55432/postgres",
    "postgresql://wp:wp@/postgres?host=/tmp/pg-run",
    "postgresql://ag@localhost/postgres?host=/tmp",
    "postgresql://ag@/postgres?host=/tmp",
)

_NAMED_ENV = (
    "WHITEPACT_TEST_POSTGRES_BASE",
    "WHITEPACT_TEST_POSTGRES_0029",
    "WHITEPACT_TEST_POSTGRES_0032",
    "WHITEPACT_TEST_POSTGRES_EXECUTION",
    "WHITEPACT_TEST_POSTGRES_PHASE5",
    "WHITEPACT_TEST_POSTGRES_CONCURRENCY",
)

_cached_admin: str | None = None
_session_databases: list[str] = []


def database_url(admin_url: str, db_name: str) -> str:
    parsed = urlparse(admin_url)
    return urlunparse(parsed._replace(path=f"/{db_name}"))


async def resolve_admin_url() -> str:
    global _cached_admin
    if _cached_admin:
        return _cached_admin
    import asyncpg

    errors: list[str] = []
    seen: set[str] = set()
    for url in _CANDIDATES:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            conn = await asyncpg.connect(url, timeout=2)
            await conn.close()
            _cached_admin = url
            os.environ["WHITEPACT_TEST_PG_ADMIN_URL"] = url
            return url
        except Exception as exc:
            errors.append(f"{_redact(url)}: {type(exc).__name__}")
    raise RuntimeError(
        "Isolated PostgreSQL test instance is not reachable. Tried: " + "; ".join(errors)
    )


def resolve_admin_url_sync() -> str:
    global _cached_admin
    if _cached_admin:
        return _cached_admin
    import asyncio

    return asyncio.run(resolve_admin_url())


def pg_admin_url() -> str:
    return resolve_admin_url_sync() if _cached_admin is None else _cached_admin


def _redact(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    query = f"?{parsed.query}" if parsed.query else ""
    return f"{parsed.scheme}://{parsed.username or ''}@{host}{port}{parsed.path}{query}"


async def create_isolated_database(prefix: str) -> tuple[str, str]:
    import asyncpg

    admin = await resolve_admin_url()
    db_name = f"{prefix}_{os.urandom(6).hex()}"
    conn = await asyncpg.connect(admin)
    try:
        await conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await conn.close()
    return admin, db_name


async def isolated_pg_url(prefix: str) -> AsyncGenerator[str, None]:
    admin, db_name = await create_isolated_database(prefix)
    try:
        yield database_url(admin, db_name)
    finally:
        await drop_isolated_database(admin, db_name)


async def drop_isolated_database(admin_url: str, db_name: str) -> None:
    import asyncpg

    conn = await asyncpg.connect(admin_url)
    try:
        await conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = $1 AND pid <> pg_backend_pid()
            """,
            db_name,
        )
        await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
    finally:
        await conn.close()


def configure_session_pg_env() -> None:
    """Create disposable named databases for env-gated security-critical PG tests."""
    import asyncio

    asyncio.run(_configure_session_pg_env())


async def _configure_session_pg_env() -> None:
    import asyncpg

    admin = await resolve_admin_url()
    conn = await asyncpg.connect(admin)
    try:
        for key in _NAMED_ENV:
            if os.environ.get(key):
                continue
            db_name = f"wp_gate_{key.split('_')[-1].lower()}_{os.urandom(4).hex()}"
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            os.environ[key] = database_url(admin, db_name)
            _session_databases.append(db_name)
    finally:
        await conn.close()
    atexit.register(_drop_session_databases)


def _drop_session_databases() -> None:
    if not _session_databases or not _cached_admin:
        return
    import asyncio

    async def _drop() -> None:
        import asyncpg

        conn = await asyncpg.connect(_cached_admin)
        try:
            for db_name in list(_session_databases):
                try:
                    await conn.execute(
                        """
                        SELECT pg_terminate_backend(pid)
                        FROM pg_stat_activity
                        WHERE datname = $1 AND pid <> pg_backend_pid()
                        """,
                        db_name,
                    )
                    await conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
                except Exception:
                    pass
        finally:
            await conn.close()

    try:
        asyncio.run(_drop())
    except Exception:
        pass
