# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Current journal runtime acceptance on disposable real PostgreSQL."""

from contextlib import aclosing

import pytest
from sqlalchemy import text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.runtime_compatibility import assert_runtime_schema_compatible
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
async def test_0065_upgrade_restart_and_aborted_revision_change():
    async with aclosing(isolated_pg_url("wp_convergence3_schema")) as databases:
        async for database in databases:
            ini, env = _find_alembic_ini(), _migration_env(database)
            await _run_alembic(ini, env, "upgrade", "0065")
            engine = create_engine(database)
            try:
                with pytest.raises(RuntimeError, match="incompatible"):
                    await assert_runtime_schema_compatible(engine)
                await _run_alembic(ini, env, "upgrade", "0066")
                await assert_runtime_schema_compatible(engine)
                async with engine.raw.connect() as conn:
                    assert int(await conn.scalar(text("SHOW server_version_num"))) // 10000 == 16
                    assert await conn.scalar(
                        text("SELECT to_regclass('runtime_containment_records') IS NOT NULL")
                    )
                # Transaction rollback must not publish an incompatible revision.
                with pytest.raises(ValueError, match="controlled rollback"):
                    async with engine.raw.begin() as conn:
                        await conn.execute(text("UPDATE alembic_version SET version_num='0065'"))
                        raise ValueError("controlled rollback")
                await assert_runtime_schema_compatible(engine)
                await engine.close()
                engine = create_engine(database)
                await assert_runtime_schema_compatible(engine)
                for version in ("0064", "0065", "0067"):
                    async with engine.raw.begin() as conn:
                        await conn.execute(
                            text("UPDATE alembic_version SET version_num=:version"),
                            {"version": version},
                        )
                    with pytest.raises(RuntimeError, match="incompatible"):
                        await assert_runtime_schema_compatible(engine)
                async with engine.raw.begin() as conn:
                    await conn.execute(text("DROP TABLE alembic_version"))
                with pytest.raises(RuntimeError, match="unverified"):
                    await assert_runtime_schema_compatible(engine)
            finally:
                await engine.close()
