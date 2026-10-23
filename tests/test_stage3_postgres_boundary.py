# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable PostgreSQL 16 checks for untrusted SQL activation denial."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
async def test_migration_preserves_history_and_denies_application_sql_activation():
    async for url in isolated_pg_url("wp_stage3_roles"):
        await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "0066")
        engine = create_engine(url)
        role = "wp_untrusted_" + uuid.uuid4().hex
        try:
            async with engine.raw.begin() as connection:
                version = int(await connection.scalar(text("SHOW server_version_num")))
                assert 160000 <= version < 170000
                await connection.execute(
                    text(
                        "INSERT INTO organizations(id,name,slug,created_at,governance_status) "
                        "VALUES('historical','Historical','historical','2026-10-23','ACTIVE')"
                    )
                )
            await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "0067")
            async with engine.raw.begin() as connection:
                assert (
                    await connection.scalar(text("SELECT version_num FROM alembic_version"))
                    == "0067"
                )
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM tenant_provisioning_records")
                    )
                    == 0
                )
                assert (
                    await connection.scalar(
                        text("SELECT governance_status FROM organizations WHERE id='historical'")
                    )
                    == "ACTIVE"
                )
                await connection.execute(
                    text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEROLE')
                )
                await connection.execute(
                    text(f'GRANT SELECT,INSERT,UPDATE ON organizations TO "{role}"')
                )
                # Even an application role with explicit broad organization write
                # grants cannot manufacture the protected lifecycle projection.
            for statement in (
                "INSERT INTO organizations(id,name,slug,created_at,governance_status) "
                "VALUES('forged','Forged','forged','2026-10-23','ACTIVE')",
                "INSERT INTO tenant_provisioning_records(tenant_id) VALUES('historical')",
            ):
                with pytest.raises(DBAPIError):
                    async with engine.raw.begin() as connection:
                        await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                        await connection.execute(text(statement))
            async with engine.raw.begin() as connection:
                await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                await connection.execute(
                    text(
                        "INSERT INTO organizations(id,name,slug,created_at) "
                        "VALUES('pending','Pending','pending','2026-10-23')"
                    )
                )
                assert (
                    await connection.scalar(
                        text("SELECT governance_status FROM organizations WHERE id='pending'")
                    )
                    == "DISABLED"
                )
            with pytest.raises(DBAPIError):
                async with engine.raw.begin() as connection:
                    await connection.execute(text(f'SET LOCAL ROLE "{role}"'))
                    await connection.execute(
                        text(
                            "UPDATE organizations SET governance_status='ACTIVE' WHERE id='pending'"
                        )
                    )
            # No controller principal is automatically enrolled by migration.
            async with engine.raw.connect() as connection:
                assert not await connection.scalar(
                    text("SELECT pg_has_role(:role,'whitepact_tenant_controller','MEMBER')"),
                    {"role": role},
                )
        finally:
            async with engine.raw.begin() as connection:
                await connection.execute(text(f'REVOKE ALL ON organizations FROM "{role}"'))
                await connection.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
            await engine.close()
