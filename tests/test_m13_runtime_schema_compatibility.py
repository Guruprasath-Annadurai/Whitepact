# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual PostgreSQL revision compatibility; no historical-binary claim."""

from contextlib import aclosing

import pytest
from sqlalchemy import text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.runtime_compatibility import assert_runtime_schema_compatible
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
async def test_actual_postgres_startup_revision_and_restart_contract():
    async with aclosing(isolated_pg_url("wp_convergence_version")) as databases:
        async for database in databases:
            await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
            engine = create_engine(database)
            try:
                await assert_runtime_schema_compatible(engine)
                for version in ("0064", "0066"):
                    async with engine.raw.begin() as connection:
                        await connection.execute(
                            text("UPDATE alembic_version SET version_num=:version"),
                            {"version": version},
                        )
                    with pytest.raises(RuntimeError, match="incompatible"):
                        await assert_runtime_schema_compatible(engine)
                # A failed transaction cannot publish a compatible revision.
                with pytest.raises(ValueError):
                    async with engine.raw.begin() as connection:
                        await connection.execute(text("UPDATE alembic_version SET version_num='0065'"))
                        raise ValueError("controlled rollback")
                with pytest.raises(RuntimeError, match="incompatible"):
                    await assert_runtime_schema_compatible(engine)
                async with engine.raw.begin() as connection:
                    await connection.execute(text("UPDATE alembic_version SET version_num='0065'"))
                await engine.close()
                engine = create_engine(database)
                await assert_runtime_schema_compatible(engine)
                async with engine.raw.begin() as connection:
                    await connection.execute(text("DROP TABLE alembic_version"))
                with pytest.raises(RuntimeError, match="unverified"):
                    await assert_runtime_schema_compatible(engine)
            finally:
                await engine.close()
