# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests for WP-PG-REV-01: Cross-tenant authority integrity defect.

Proves that the database must reject any cross-tenant authority edge at the
database constraint level (e.g. grantor belonging to tenant B referenced by
an authority edge belonging to tenant A).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
from sqlalchemy import text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import run_migrations_or_raise

PG_ADMIN_URL = "postgresql://ag@localhost/postgres?host=/tmp"
PG_BASE_URL = "postgresql://ag@localhost/{db_name}?host=/tmp"


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    db_name = f"wp_cross_test_{uuid.uuid4().hex[:12]}"
    admin_conn = await asyncpg.connect(PG_ADMIN_URL)
    await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    await admin_conn.close()

    db_url = PG_BASE_URL.format(db_name=db_name)
    try:
        yield db_url
    finally:
        admin_conn = await asyncpg.connect(PG_ADMIN_URL)
        await admin_conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
        """)
        await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await admin_conn.close()


@pytest.mark.asyncio
async def test_cross_tenant_authority_edge_rejected_by_database(pg_test_db: str) -> None:
    """Database must reject an authority edge whose grantor belongs to a different tenant."""
    # Upgrade to current HEAD
    await run_migrations_or_raise(pg_test_db)

    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        # Create two distinct organizations
        org_a = f"org-a-{uuid.uuid4().hex[:6]}"
        org_b = f"org-b-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text("INSERT INTO organizations (id, slug, name, created_at) VALUES (:a, :a, 'Tenant A', '2026-01-01T00:00:00Z'), (:b, :b, 'Tenant B', '2026-01-01T00:00:00Z')"),
            {"a": org_a, "b": org_b},
        )

        # Create Principal A in Org A
        p_a = f"prin-a-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            text("INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) "
                 "VALUES (:p, :org, 'HUMAN_OPERATOR', 'User A', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"),
            {"p": p_a, "org": org_a},
        )

        # Create Principal B in Org B (the cross-tenant grantor)
        p_b = f"prin-b-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            text("INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) "
                 "VALUES (:p, :org, 'HUMAN_OPERATOR', 'User B', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"),
            {"p": p_b, "org": org_b},
        )

        # Now attempt to insert a cross-tenant authority edge:
        # edge belongs to org_a, grantee is p_a (org_a), but grantor is p_b (org_b)!
        edge_id = f"edge-{uuid.uuid4().hex[:8]}"
        
        # REQUIRED DATABASE INVARIANT: This cross-tenant authority relationship MUST fail at the database level!
        # On vulnerable schema 0045, this succeeds (violating the invariant).
        # On fixed schema 0046, this raises IntegrityError / ForeignKeyViolation.
        with pytest.raises(Exception) as exc_info:
            await conn.execute(
                text("INSERT INTO trust_fabric_authority_edges "
                     "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                     "VALUES (:id, :grantor, :grantee, :org, 'tool_call', '2026-01-01T00:00:00Z', 'digest123')"),
                {
                    "id": edge_id,
                    "grantor": p_b,  # org_b!
                    "grantee": p_a,  # org_a
                    "org": org_a,    # org_a
                },
            )
        # Verify that the failure was a relational integrity constraint violation
        err_msg = str(exc_info.value).lower()
        assert "foreign key" in err_msg or "violates" in err_msg or "constraint" in err_msg


@pytest.mark.asyncio
async def test_same_tenant_authority_edge_accepted_by_database(pg_test_db: str) -> None:
    """Database must accept a valid same-tenant authority edge."""
    await run_migrations_or_raise(pg_test_db)

    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a = f"org-same-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text("INSERT INTO organizations (id, slug, name, created_at) VALUES (:a, :a, 'Tenant Same', '2026-01-01T00:00:00Z')"),
            {"a": org_a},
        )
        p_grantor = f"prin-g1-{uuid.uuid4().hex[:8]}"
        p_grantee = f"prin-g2-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            text("INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) "
                 "VALUES (:p1, :org, 'HUMAN_OPERATOR', 'Grantor', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                 "(:p2, :org, 'AGENT', 'Grantee', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"),
            {"p1": p_grantor, "p2": p_grantee, "org": org_a},
        )
        edge_id = f"edge-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            text("INSERT INTO trust_fabric_authority_edges "
                 "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                 "VALUES (:id, :grantor, :grantee, :org, 'tool_call', '2026-01-01T00:00:00Z', 'digest123')"),
            {
                "id": edge_id,
                "grantor": p_grantor,
                "grantee": p_grantee,
                "org": org_a,
            },
        )

        res = await conn.execute(
            text("SELECT count(*) FROM trust_fabric_authority_edges WHERE id = :id"),
            {"id": edge_id},
        )
        assert res.scalar() == 1


@pytest.mark.asyncio
async def test_migration_fails_closed_when_corrupt_data_exists(pg_test_db: str) -> None:
    """Migration 0046 must abort with clear diagnostic (fail closed) if historical corrupt cross-tenant rows exist."""
    from responsibleai.db.migrate import (
        MigrationError,
        _find_alembic_ini,
        _migration_env,
        _run_alembic,
    )

    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # 1. Upgrade to 0045
    await _run_alembic(ini, env, "upgrade", "0045")

    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a = f"org-a-{uuid.uuid4().hex[:6]}"
        org_b = f"org-b-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text("INSERT INTO organizations (id, slug, name, created_at) VALUES (:a, :a, 'Tenant A', '2026-01-01T00:00:00Z'), (:b, :b, 'Tenant B', '2026-01-01T00:00:00Z')"),
            {"a": org_a, "b": org_b},
        )
        p_a = f"prin-a-{uuid.uuid4().hex[:8]}"
        p_b = f"prin-b-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            text("INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) "
                 "VALUES (:pa, :oa, 'HUMAN', 'A', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                 "(:pb, :ob, 'HUMAN', 'B', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"),
            {"pa": p_a, "oa": org_a, "pb": p_b, "ob": org_b},
        )
        # Corrupt cross-tenant row: org_a edge pointing to org_b grantor
        corrupt_id = f"corrupt-edge-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            text("INSERT INTO trust_fabric_authority_edges "
                 "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                 "VALUES (:id, :grantor, :grantee, :org, 'tool_call', '2026-01-01T00:00:00Z', 'digest123')"),
            {"id": corrupt_id, "grantor": p_b, "grantee": p_a, "org": org_a},
        )
    await engine.close()

    # 2. Upgrading to 0046 must fail closed!
    with pytest.raises(MigrationError) as exc_info:
        await _run_alembic(ini, env, "upgrade", "0046")

    err = str(exc_info.value).lower()
    assert "fail closed" in err or "cross-tenant" in err

