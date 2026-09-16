# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL Migration Proof for Phase 3 Global Trust Fabric.

Verifies:
1. One canonical alembic head (0043) with down-revision 0042.
2. Fresh schema upgrade -> 0043 on real PostgreSQL.
3. Canonical 0042 -> 0043 upgrade with existing tenant dataset preservation.
4. Downgrade 0043 -> 0042 and re-upgrade 0042 -> 0043.
5. Strict prevention of false version stamping on unversioned/pre-existing databases.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import (
    MigrationError,
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
    run_migrations_or_raise,
)

PG_ADMIN_URL = "postgresql://ag@localhost/postgres?host=/tmp"
PG_BASE_URL = "postgresql://ag@localhost/{db_name}?host=/tmp"

TRUST_FABRIC_TABLES = {
    "trust_fabric_principals",
    "trust_fabric_identifiers",
    "trust_fabric_sources",
    "trust_fabric_assertions",
    "trust_fabric_relationships",
    "trust_fabric_authority_edges",
    "trust_fabric_trust_roots",
    "trust_fabric_bootstrap_records",
    "trust_fabric_passports",
    "trust_fabric_conflicts",
    "trust_fabric_challenges",
    "trust_fabric_federated_assertions",
}


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    db_name = f"wp_mig_test_{uuid.uuid4().hex[:12]}"
    admin_conn = await asyncpg.connect(PG_ADMIN_URL)
    await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    await admin_conn.close()

    db_url = PG_BASE_URL.format(db_name=db_name)
    try:
        yield db_url
    finally:
        # Force terminate active connections to allow drop
        admin_conn = await asyncpg.connect(PG_ADMIN_URL)
        await admin_conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
        """)
        await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await admin_conn.close()


def test_one_canonical_alembic_head():
    """Verify exactly 1 canonical alembic head and correct revision chain."""
    ini = _find_alembic_ini()
    assert ini is not None, "alembic.ini must exist"
    scripts = ScriptDirectory.from_config(Config(str(ini)))
    heads = scripts.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic head, got {len(heads)}: {heads}"
    assert heads == ["0048"]
    assert scripts.get_revision("0048").down_revision == "0047"
    assert scripts.get_revision("0047").down_revision == "0046"
    assert scripts.get_revision("0046").down_revision == "0045"
    assert scripts.get_revision("0045").down_revision == "0044"
    assert scripts.get_revision("0044").down_revision == "0043"
    assert scripts.get_revision("0043").down_revision == "0042"


@pytest.mark.asyncio
async def test_fresh_schema_to_0043_postgres(pg_test_db: str):
    """Prove fresh schema upgrades directly to 0043 on real PostgreSQL."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)
    await _run_alembic(ini, env, "upgrade", "0043")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0043"

            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert TRUST_FABRIC_TABLES <= set(tables), (
                f"Missing tables: {TRUST_FABRIC_TABLES - set(tables)}"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_canonical_0042_to_0043_preserves_tenant_data_postgres(pg_test_db: str):
    """Prove upgrade from 0042 to 0043 preserves existing tenant datasets."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # Step 1: Migrate up to canonical 0042
    await _run_alembic(ini, env, "upgrade", "0042")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0042"

            # Step 2: Seed canonical pre-0043 tenant data
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at)
                    VALUES
                        ('tenant-corp-a', 'Corp Alpha', 'corp-alpha', 5000, '2026-01-01T00:00:00Z'),
                        ('tenant-corp-b', 'Corp Beta', 'corp-beta', 10000, '2026-01-01T00:00:00Z')
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO governance_root_authority_records
                        (root_id, subject_id, root_type, organization_id, issuer, verification_method, evidence_refs, issued_at, canonical_digest)
                    VALUES
                        ('root-1', 'subject-1', 'HUMAN', 'tenant-corp-a', 'cust-issuer', 'explicit', '[]', '2026-01-01T00:00:00Z', 'digest-root-1'),
                        ('root-2', 'subject-2', 'ORGANIZATION', 'tenant-corp-b', 'cust-issuer', 'explicit', '[]', '2026-01-01T00:00:00Z', 'digest-root-2')
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO governance_evidence
                        (id, org_id, action_id, agent_id, identity_id, action_type, target, authority_delegated_by, decision, reason_codes, evaluated_at, recorded_at, entry_hash)
                    VALUES
                        ('ev-1', 'tenant-corp-a', 'act-1', 'ag-1', 'id-1', 'EXECUTE', 'res-1', 'root-1', 'ALLOW', '[]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'hash-1'),
                        ('ev-2', 'tenant-corp-b', 'act-2', 'ag-2', 'id-2', 'READ', 'res-2', 'root-2', 'ALLOW', '[]', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'hash-2')
                """)
            )
            await conn.commit()
    finally:
        await engine.close()

    # Step 3: Run migration to 0043
    await _run_alembic(ini, env, "upgrade", "0043")

    # Step 4: Verify migration succeeded and tenant data is preserved
    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0043"

            # Check pre-existing tenant records are intact
            org_rows = (await conn.execute(text("SELECT id, name, slug FROM organizations ORDER BY id"))).fetchall()
            assert len(org_rows) == 2
            assert org_rows[0] == ("tenant-corp-a", "Corp Alpha", "corp-alpha")
            assert org_rows[1] == ("tenant-corp-b", "Corp Beta", "corp-beta")

            root_rows = (await conn.execute(text("SELECT root_id, organization_id FROM governance_root_authority_records ORDER BY root_id"))).fetchall()
            assert len(root_rows) == 2
            assert root_rows[0] == ("root-1", "tenant-corp-a")
            assert root_rows[1] == ("root-2", "tenant-corp-b")

            ev_rows = (await conn.execute(text("SELECT id, org_id FROM governance_evidence ORDER BY id"))).fetchall()
            assert len(ev_rows) == 2
            assert ev_rows[0] == ("ev-1", "tenant-corp-a")
            assert ev_rows[1] == ("ev-2", "tenant-corp-b")

            # Check trust fabric tables exist and operate
            tables = await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert TRUST_FABRIC_TABLES <= set(tables)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_downgrade_0043_to_0042_and_reupgrade_postgres(pg_test_db: str):
    """Prove clean downgrade from 0043 -> 0042 and re-upgrade back to 0043."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # Step 1: Upgrade to 0043
    await _run_alembic(ini, env, "upgrade", "0043")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at)
                    VALUES ('tenant-preserve', 'Preserve Org', 'preserve', 1000, '2026-01-01T00:00:00Z')
                """)
            )
            await conn.commit()
    finally:
        await engine.close()

    # Step 2: Downgrade to 0042
    await _run_alembic(ini, env, "downgrade", "0042")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0042"

            tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
            # Trust fabric tables must be dropped
            assert not (TRUST_FABRIC_TABLES & tables), f"Tables not dropped: {TRUST_FABRIC_TABLES & tables}"

            # Pre-existing tenant data must still be intact
            org = (await conn.execute(text("SELECT id, name FROM organizations WHERE id='tenant-preserve'"))).fetchone()
            assert org == ("tenant-preserve", "Preserve Org")
    finally:
        await engine.close()

    # Step 3: Re-upgrade to 0043
    await _run_alembic(ini, env, "upgrade", "0043")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0043"

            tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
            assert TRUST_FABRIC_TABLES <= tables

            org = (await conn.execute(text("SELECT id, name FROM organizations WHERE id='tenant-preserve'"))).fetchone()
            assert org == ("tenant-preserve", "Preserve Org")
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_no_false_version_stamping_on_unversioned_db_postgres(pg_test_db: str):
    """Prove unversioned pre-existing database is never stamped without review."""
    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            # Create pre-existing customer data without alembic_version
            await conn.execute(
                text("""
                    CREATE TABLE organizations (
                        id VARCHAR(36) PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        slug VARCHAR(255) NOT NULL,
                        monthly_budget_usd INTEGER NOT NULL DEFAULT 0,
                        created_at VARCHAR(32) NOT NULL
                    )
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, created_at)
                    VALUES ('unversioned-tenant', 'Unversioned Corp', 'unversioned', '2026-01-01T00:00:00Z')
                """)
            )
            await conn.commit()
    finally:
        await engine.close()

    # Attempting automated migration on unversioned database MUST fail
    with pytest.raises(MigrationError, match="unversioned"):
        await run_migrations_or_raise(pg_test_db)

    # Confirm alembic_version was NOT stamped and data remains safe
    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            tables = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
            assert "alembic_version" not in tables, "False version stamping detected!"
            org = (await conn.execute(text("SELECT id FROM organizations"))).scalar()
            assert org == "unversioned-tenant"
    finally:
        await engine.close()
