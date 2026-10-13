# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""B3 — upgrade from prior supported revision on real PostgreSQL."""

from __future__ import annotations

import asyncpg
import pytest
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic

PRIOR_REVISION = "0058"


@pytest.mark.asyncio
async def test_upgrade_from_prior_revision_to_head_on_postgres() -> None:
    async for url in isolated_pg_url("b3_prior"):
        ini = _find_alembic_ini()
        env = _migration_env(url)
        await _run_alembic(ini, env, "upgrade", PRIOR_REVISION)
        conn = await asyncpg.connect(url)
        try:
            version = await conn.fetchval("SELECT version_num FROM alembic_version")
            assert version == PRIOR_REVISION
        finally:
            await conn.close()
        await _run_alembic(ini, env, "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            head = await conn.fetchval("SELECT version_num FROM alembic_version")
            assert head.startswith("006")
            org_cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns WHERE table_name = 'organizations'"
            )
            assert any(r["column_name"] == "slug" for r in org_cols)
        finally:
            await conn.close()
