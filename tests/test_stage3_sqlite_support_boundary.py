# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unsupported hosted provisioning migration must refuse before schema mutation."""

import pytest
from sqlalchemy import text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import MigrationError, _find_alembic_ini, _migration_env, _run_alembic


@pytest.mark.asyncio
async def test_sqlite_0067_refuses_without_partial_schema_or_version_publication(tmp_path):
    path = str(tmp_path / "unsupported.sqlite3")
    ini = _find_alembic_ini()
    await _run_alembic(ini, _migration_env(path), "upgrade", "0066")
    engine = create_engine(path)
    try:
        async with engine.raw.connect() as connection:
            before = (
                await connection.execute(text("SELECT name,sql FROM sqlite_master ORDER BY name"))
            ).all()
        with pytest.raises(MigrationError, match="Cross-store provisioning requires PostgreSQL"):
            await _run_alembic(ini, _migration_env(path), "upgrade", "0067")
        async with engine.raw.connect() as connection:
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0066"
            )
            after = (
                await connection.execute(text("SELECT name,sql FROM sqlite_master ORDER BY name"))
            ).all()
            assert after == before
    finally:
        await engine.close()
