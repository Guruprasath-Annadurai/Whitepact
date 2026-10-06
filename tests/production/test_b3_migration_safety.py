# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — PostgreSQL migration safety (B3)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import asyncpg
import pytest
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.migrate import (
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
    run_migrations_or_raise,
)

REPO = Path(__file__).resolve().parents[2]


def _alembic_heads() -> list[str]:
    ini = _find_alembic_ini()
    result = subprocess.run(
        ["alembic", "-c", str(ini), "heads"],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO,
    )
    assert result.returncode == 0, result.stderr
    heads = [line.strip().split()[0] for line in result.stdout.splitlines() if line.strip()]
    return heads


@pytest.mark.asyncio
async def test_single_alembic_head() -> None:
    heads = _alembic_heads()
    assert len(heads) == 1, f"expected single migration head, got {heads}"


@pytest.mark.asyncio
async def test_empty_postgres_upgrades_to_head() -> None:
    async for url in isolated_pg_url("b3_empty"):
        ini = _find_alembic_ini()
        env = _migration_env(url)
        await _run_alembic(ini, env, "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            version = await conn.fetchval("SELECT version_num FROM alembic_version")
        finally:
            await conn.close()
        assert version == _alembic_heads()[0]


@pytest.mark.asyncio
async def test_application_migration_helper_matches_head() -> None:
    async for url in isolated_pg_url("b3_empty"):
        await run_migrations_or_raise(url)
        conn = await asyncpg.connect(url)
        try:
            tables = {
                row[0]
                for row in await conn.fetch(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            }
        finally:
            await conn.close()
        assert "organizations" in tables
        assert "alembic_version" in tables
