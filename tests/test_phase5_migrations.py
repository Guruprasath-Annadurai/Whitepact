# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL Migration Proof for Phase 5 Enterprise Policy Lifecycle & Data Governance.

Verifies:
1. One canonical alembic head (0045) with down-revision 0044.
2. Fresh schema upgrade -> 0045 on real PostgreSQL.
3. Canonical 0044 -> 0045 upgrade with existing trust fabric, IAM, and tenant dataset preservation.
4. Downgrade 0045 -> 0044 and clean re-upgrade 0044 -> 0045.
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
    run_migrations_or_raise,
)

PHASE5_TABLES = {
    "governance_policy_revisions",
    "governance_policy_activations",
    "data_retention_policies",
    "data_lifecycle_requests",
    "data_holds",
    "tenant_tombstones",
    "restore_reconciliation_records",
}


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    async for url in isolated_pg_url('wp_mig_p5'):
        yield url


def test_one_canonical_alembic_head():
    """Verify exactly 1 canonical alembic head (0045) and correct revision chain."""
    ini = _find_alembic_ini()
    assert ini is not None, "alembic.ini must exist"
    scripts = ScriptDirectory.from_config(Config(str(ini)))
    heads = scripts.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic head, got {len(heads)}: {heads}"
    assert heads == ["0049"]
    assert scripts.get_revision("0049").down_revision == "0048"
    assert scripts.get_revision("0048").down_revision == "0047"
    assert scripts.get_revision("0047").down_revision == "0046"
    assert scripts.get_revision("0046").down_revision == "0045"
    assert scripts.get_revision("0045").down_revision == "0044"
    assert scripts.get_revision("0044").down_revision == "0043"
    assert scripts.get_revision("0043").down_revision == "0042"


@pytest.mark.asyncio
async def test_fresh_schema_to_0045_postgres(pg_test_db: str):
    """Prove fresh schema upgrades directly to 0045 on real PostgreSQL."""
    await run_migrations_or_raise(pg_test_db)

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0049"

            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert PHASE5_TABLES <= set(tables), (
                f"Missing Phase 5 tables: {PHASE5_TABLES - set(tables)}"
            )

            # Also verify policy_digest column exists on governance_evidence
            cols = await conn.run_sync(lambda c: inspect(c).get_columns("governance_evidence"))
            col_names = {c["name"] for c in cols}
            assert "policy_digest" in col_names, "governance_evidence missing policy_digest column"
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_canonical_0044_to_0045_preserves_tenant_data_postgres(pg_test_db: str):
    """Prove upgrade from 0044 to 0045 preserves existing Phase 4 data on PostgreSQL."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # Step 1: Migrate up to 0044
    await _run_alembic(ini, env, "upgrade", "0044")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0044"

            # Seed tenant
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at)
                    VALUES ('tenant-p5', 'Phase 5 Enterprise', 'p5-ent', 15000, '2026-09-12T00:00:00Z')
                """)
            )
            # Seed principal
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, lifecycle_state, created_at, updated_at)
                    VALUES ('prin-p5-root', 'tenant-p5', 'HUMAN', 'Gov Root Admin', 'ACTIVE', '2026-09-12T00:00:00Z', '2026-09-12T00:00:00Z')
                """)
            )
            await conn.commit()
    finally:
        await engine.close()

    # Step 2: Migrate to 0045
    await _run_alembic(ini, env, "upgrade", "0045")

    engine2 = create_engine(pg_test_db)
    try:
        async with engine2.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0045"

            # Verify seeded data was preserved
            org_name = (await conn.execute(text("SELECT name FROM organizations WHERE id = 'tenant-p5'"))).scalar()
            assert org_name == "Phase 5 Enterprise"

            prin_name = (await conn.execute(text("SELECT display_name FROM trust_fabric_principals WHERE id = 'prin-p5-root'"))).scalar()
            assert prin_name == "Gov Root Admin"
    finally:
        await engine2.close()


@pytest.mark.asyncio
async def test_downgrade_0045_to_0044_and_reupgrade_postgres(pg_test_db: str):
    """Prove reversible migration: 0045 -> 0044 downgrade and clean re-upgrade."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # Migrate to 0045
    await _run_alembic(ini, env, "upgrade", "0045")

    # Downgrade to 0044
    await _run_alembic(ini, env, "downgrade", "0044")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0044"

            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert not (PHASE5_TABLES & set(tables)), "Phase 5 tables should be dropped"
    finally:
        await engine.close()

    # Re-upgrade to 0045
    await _run_alembic(ini, env, "upgrade", "0045")

    engine2 = create_engine(pg_test_db)
    try:
        async with engine2.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0045"
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert PHASE5_TABLES <= set(tables)
    finally:
        await engine2.close()
