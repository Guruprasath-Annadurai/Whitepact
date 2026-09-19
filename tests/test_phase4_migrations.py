# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL Migration Proof for Phase 4 Enterprise IAM & Privileged Control Plane.

Verifies:
1. One canonical alembic head (0044) with down-revision 0043.
2. Fresh schema upgrade -> 0044 on real PostgreSQL.
3. Canonical 0043 -> 0044 upgrade with existing trust fabric and tenant dataset preservation.
4. Downgrade 0044 -> 0043 and re-upgrade 0043 -> 0044.
5. Strict single head and migration integrity.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from tests.pg_test_url import isolated_pg_url

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import (
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
)

IAM_PHASE4_TABLES = {
    "iam_step_up_nonces",
    "iam_sessions",
    "iam_api_key_lineage",
    "iam_scim_users",
    "iam_scim_groups",
    "iam_jit_grants",
    "iam_four_eyes_requests",
    "iam_break_glass_sessions",
    "iam_recovery_policies",
    "iam_recovery_challenges",
    "iam_privileged_audit_log",
}


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    async for url in isolated_pg_url('wp_mig_p4'):
        yield url


def test_one_canonical_alembic_head():
    """Verify exactly 1 canonical alembic head and correct revision chain."""
    ini = _find_alembic_ini()
    assert ini is not None, "alembic.ini must exist"
    scripts = ScriptDirectory.from_config(Config(str(ini)))
    heads = scripts.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic head, got {len(heads)}: {heads}"
    assert heads == ["0055"]
    assert scripts.get_revision("0049").down_revision == "0048"
    assert scripts.get_revision("0048").down_revision == "0047"
    assert scripts.get_revision("0047").down_revision == "0046"
    assert scripts.get_revision("0046").down_revision == "0045"
    assert scripts.get_revision("0045").down_revision == "0044"
    assert scripts.get_revision("0044").down_revision == "0043"
    assert scripts.get_revision("0043").down_revision == "0042"


@pytest.mark.asyncio
async def test_fresh_schema_to_0044_postgres(pg_test_db: str):
    """Prove schema upgrades to 0044 on real PostgreSQL."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)
    await _run_alembic(ini, env, "upgrade", "0044")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0044"

            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert IAM_PHASE4_TABLES <= set(tables), (
                f"Missing Phase 4 tables: {IAM_PHASE4_TABLES - set(tables)}"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_canonical_0043_to_0044_preserves_tenant_data_postgres(pg_test_db: str):
    """Prove upgrade from 0043 to 0044 preserves existing Phase 3 data on PostgreSQL."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # Step 1: Migrate up to 0043
    await _run_alembic(ini, env, "upgrade", "0043")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0043"

            # Seed tenant
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at)
                    VALUES ('tenant-p4', 'Phase 4 Enterprise', 'p4-ent', 10000, '2026-09-12T00:00:00Z')
                """)
            )
            # Seed principal
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, lifecycle_state, created_at, updated_at)
                    VALUES ('prin-p4-root', 'tenant-p4', 'HUMAN', 'Root Admin', 'ACTIVE', '2026-09-12T00:00:00Z', '2026-09-12T00:00:00Z')
                """)
            )
            await conn.commit()
    finally:
        await engine.close()

    # Step 2: Migrate to 0044
    await _run_alembic(ini, env, "upgrade", "0044")

    engine2 = create_engine(pg_test_db)
    try:
        async with engine2.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0044"

            # Verify seeded data was preserved
            org_name = (await conn.execute(text("SELECT name FROM organizations WHERE id = 'tenant-p4'"))).scalar()
            assert org_name == "Phase 4 Enterprise"

            prin_name = (await conn.execute(text("SELECT display_name FROM trust_fabric_principals WHERE id = 'prin-p4-root'"))).scalar()
            assert prin_name == "Root Admin"
    finally:
        await engine2.close()


@pytest.mark.asyncio
async def test_downgrade_0044_to_0043_and_reupgrade_postgres(pg_test_db: str):
    """Prove reversible migration: 0044 -> 0043 downgrade and clean re-upgrade."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # Migrate to 0044
    await _run_alembic(ini, env, "upgrade", "0044")

    # Downgrade to 0043
    await _run_alembic(ini, env, "downgrade", "0043")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0043"

            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert not (IAM_PHASE4_TABLES & set(tables)), "Phase 4 tables should be dropped"
    finally:
        await engine.close()

    # Re-upgrade to 0044
    await _run_alembic(ini, env, "upgrade", "0044")

    engine2 = create_engine(pg_test_db)
    try:
        async with engine2.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0044"
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert IAM_PHASE4_TABLES <= set(tables)
    finally:
        await engine2.close()
