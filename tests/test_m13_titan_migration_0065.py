# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PostgreSQL migration 0064 -> 0065 forward upgrade, data preservation, and safe downgrade.

Separated from immutable historical M13-R3 reproducer suite to preserve independent baselines.
"""

from __future__ import annotations

import asyncpg
import pytest

from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
async def test_migration_0064_to_0065_upgrade_data_retention_and_downgrade():
    """Verify upgrade from published 0064 to 0065 preserves data and downgrades safely."""
    async for url in isolated_pg_url("wp_m13_titan_0065"):
        ini = _find_alembic_ini()
        assert ini is not None
        env = _migration_env(url)

        # 1. Migrate to 0064 (historical baseline)
        await _run_alembic(ini, env, "upgrade", "0064")
        conn = await asyncpg.connect(url)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0064"
            # Verify require_passkey_stepup does NOT exist in 0064
            has_col_0064 = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='trust_fabric_bootstrap_records' "
                "AND column_name='require_passkey_stepup')"
            )
            assert not has_col_0064

            # Insert organization parent row
            await conn.execute(
                "INSERT INTO organizations (id, name, slug, created_at) "
                "VALUES ('org_test', 'Test Org', 'test-org', '2026-01-01T00:00:00Z')"
            )

            # Insert a baseline bootstrap record under revision 0064
            await conn.execute(
                "INSERT INTO trust_fabric_bootstrap_records "
                "(id, org_id, token_hash, nonce, expires_at, created_at) "
                "VALUES ('wp_brec_test', 'org_test', 'thash_test', 'nonce_test', "
                "'2099-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            )
        finally:
            await conn.close()

        # 2. Upgrade to 0065 (forward migration)
        await _run_alembic(ini, env, "upgrade", "0065")
        conn = await asyncpg.connect(url)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0065"
            has_col_0065 = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='trust_fabric_bootstrap_records' "
                "AND column_name='require_passkey_stepup')"
            )
            assert has_col_0065

            # Verify existing record data is preserved with default require_passkey_stepup=0
            row = await conn.fetchrow(
                "SELECT id, org_id, require_passkey_stepup "
                "FROM trust_fabric_bootstrap_records WHERE id='wp_brec_test'"
            )
            assert row is not None
            assert row["id"] == "wp_brec_test"
            assert row["org_id"] == "org_test"
            assert row["require_passkey_stepup"] == 0

            # Insert a second organization for unique constraint on org_id
            await conn.execute(
                "INSERT INTO organizations (id, name, slug, created_at) "
                "VALUES ('org_stepup', 'Stepup Org', 'stepup-org', '2026-01-01T00:00:00Z')"
            )

            # Insert a record with explicit require_passkey_stepup=1
            await conn.execute(
                "INSERT INTO trust_fabric_bootstrap_records "
                "(id, org_id, token_hash, nonce, expires_at, created_at, require_passkey_stepup) "
                "VALUES ('wp_brec_stepup', 'org_stepup', 'thash_stepup', 'nonce_stepup', "
                "'2099-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 1)"
            )
            val = await conn.fetchval(
                "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records WHERE id='wp_brec_stepup'"
            )
            assert val == 1
        finally:
            await conn.close()

        # 3. Clean downgrade from 0065 to 0064
        await _run_alembic(ini, env, "downgrade", "0064")
        conn = await asyncpg.connect(url)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0064"
            has_col_after_down = await conn.fetchval(
                "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                "WHERE table_schema='public' AND table_name='trust_fabric_bootstrap_records' "
                "AND column_name='require_passkey_stepup')"
            )
            assert not has_col_after_down

            # Base records still preserved in 0064 schema
            count = await conn.fetchval("SELECT COUNT(*) FROM trust_fabric_bootstrap_records")
            assert count == 2
        finally:
            await conn.close()

        # 4. Re-upgrade to head (0065)
        await _run_alembic(ini, env, "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            assert await conn.fetchval("SELECT version_num FROM alembic_version") == "0065"
        finally:
            await conn.close()
