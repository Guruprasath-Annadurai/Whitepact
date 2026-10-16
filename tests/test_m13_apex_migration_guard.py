# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PostgreSQL rollback compatibility without dropping mandatory authentication."""

import asyncio
from contextlib import aclosing

import asyncpg
import pytest
from scripts.engineering.reproducers.test_m13_corrective_authority import (
    test_mandatory_passkey_requirement_prevents_intermediate_0064_schema as assert_mandatory_guard,
)

from responsibleai.db.migrate import MigrationError, _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
async def test_mandatory_passkey_downgrade_is_rejected_atomically() -> None:
    await assert_mandatory_guard()


@pytest.mark.asyncio
async def test_nonmandatory_historical_row_survives_supported_roundtrip() -> None:
    async with aclosing(isolated_pg_url("wp_apex_optional_roundtrip")) as databases:
        async for database in databases:
            ini = _find_alembic_ini()
            assert ini is not None
            env = _migration_env(database)
            await _run_alembic(ini, env, "upgrade", "0064")
            connection = await asyncpg.connect(database)
            try:
                await connection.execute(
                    "INSERT INTO organizations(id,name,slug,created_at) VALUES('optional','optional','optional','2026-01-01')"
                )
                await connection.execute(
                    "INSERT INTO trust_fabric_bootstrap_records(id,org_id,token_hash,expires_at,nonce,created_at) VALUES('optional','optional','hash','2099-01-01','nonce','2026-01-01')"
                )
                for _ in range(2):
                    await _run_alembic(ini, env, "upgrade", "0065")
                    assert (
                        await connection.fetchval(
                            "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records WHERE id='optional'"
                        )
                        == 0
                    )
                    await _run_alembic(ini, env, "downgrade", "0064")
                    assert (
                        await connection.fetchval("SELECT version_num FROM alembic_version")
                        == "0064"
                    )
                    assert (
                        await connection.fetchval(
                            "SELECT count(*) FROM trust_fabric_bootstrap_records WHERE id='optional'"
                        )
                        == 1
                    )
            finally:
                await connection.close()


@pytest.mark.asyncio
async def test_concurrent_mandatory_writer_is_seen_before_downgrade() -> None:
    async with aclosing(isolated_pg_url("wp_apex_downgrade_writer")) as databases:
        async for database in databases:
            ini = _find_alembic_ini()
            assert ini is not None
            env = _migration_env(database)
            await _run_alembic(ini, env, "upgrade", "head")
            connection = await asyncpg.connect(database)
            task = None
            transaction = None
            try:
                await connection.execute(
                    "INSERT INTO organizations(id,name,slug,created_at) VALUES('race','race','race','2026-01-01')"
                )
                await connection.execute(
                    "INSERT INTO trust_fabric_bootstrap_records(id,org_id,token_hash,expires_at,nonce,created_at,require_passkey_stepup) VALUES('race','race','hash','2099-01-01','nonce','2026-01-01',0)"
                )
                transaction = connection.transaction()
                await transaction.start()
                await connection.execute(
                    "UPDATE trust_fabric_bootstrap_records SET require_passkey_stepup=1 WHERE id='race'"
                )
                task = asyncio.create_task(_run_alembic(ini, env, "downgrade", "0064"))
                deadline = asyncio.get_running_loop().time() + 15
                waiting = False
                while asyncio.get_running_loop().time() < deadline:
                    waiting = await connection.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM pg_locks WHERE relation='trust_fabric_bootstrap_records'::regclass AND mode='AccessExclusiveLock' AND NOT granted)"
                    )
                    if waiting or task.done():
                        break
                    await asyncio.sleep(0.05)
                assert waiting, "Downgrade must serialize its security check with the writer"
                await transaction.commit()
                transaction = None
                with pytest.raises(MigrationError, match="mandatory passkey requirements exist"):
                    await task
                assert (
                    await connection.fetchval("SELECT version_num FROM alembic_version") == "0065"
                )
                assert (
                    await connection.fetchval(
                        "SELECT require_passkey_stepup FROM trust_fabric_bootstrap_records WHERE id='race'"
                    )
                    == 1
                )
            finally:
                if transaction is not None:
                    await transaction.rollback()
                if task is not None:
                    await asyncio.gather(task, return_exceptions=True)
                await connection.close()
