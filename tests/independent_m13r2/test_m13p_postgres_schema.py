# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fresh real PostgreSQL migration acceptance; never creates authority rows."""

import asyncpg
import pytest
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic


@pytest.mark.asyncio
async def test_fresh_migrations_supply_security_contract_tables():
    async for url in isolated_pg_url("wp_m13p_schema"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            tables = set(
                await conn.fetchval(
                    "SELECT array_agg(tablename) FROM pg_tables WHERE schemaname = 'public'"
                )
            )
            required = {
                "authority_step_up_challenges",
                "authority_containment_records",
                "authority_recovery_requests",
                "authority_recovery_votes",
            }
            assert required <= tables, f"P0: migrated schema missing {sorted(required - tables)}"
        finally:
            await conn.close()
