# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests for WP-PG-REV-01 & WP-PG-REV-04: Cross-tenant authority integrity.

Proves:
1. WP-PG-REV-01 & WP-PG-REV-04: Full Direct-SQL Cross-Tenant Matrix
   - The database rejects any cross-tenant relationship at the database constraint level
     (ForeignKeyViolation) across all six tenant-bound relationships:
     (1) Authority edge with wrong-tenant grantor
     (2) Authority edge with wrong-tenant grantee
     (3) Relationship with wrong-tenant subject
     (4) Relationship with wrong-tenant target
     (5) Identifier with wrong-tenant principal
     (6) Trust root with wrong-tenant root principal
   - Direct SQL cross-tenant successes: 0.

2. Same-Tenant Positive Controls:
   - Valid same-tenant operations across all corresponding categories succeed.

3. Migration Preflight Corruption Matrix:
   - Migration 0046 aborts and fails closed before altering constraints if 0045
     historical data contains corruption across any of the 6 corruption classes.
   - Corrupt historical DB accepted by 0046: 0.
   - Zero silent repair, zero silent deletion, zero tenant reassignment.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator

from tests.pg_test_url import isolated_pg_url
from typing import Any

import asyncpg
import pytest
from sqlalchemy import text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import (
    MigrationError,
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
    run_migrations_or_raise,
)


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    async for url in isolated_pg_url('wp_xtenant'):
        yield url


async def _seed_two_tenants_and_principals(conn: Any) -> tuple[str, str, str, str]:
    org_a = f"org-a-{uuid.uuid4().hex[:6]}"
    org_b = f"org-b-{uuid.uuid4().hex[:6]}"
    await conn.execute(
        text(
            "INSERT INTO organizations (id, slug, name, created_at) VALUES "
            "(:a, :a, 'Tenant A', '2026-01-01T00:00:00Z'), "
            "(:b, :b, 'Tenant B', '2026-01-01T00:00:00Z')"
        ),
        {"a": org_a, "b": org_b},
    )
    p_a = f"prin-a-{uuid.uuid4().hex[:8]}"
    p_b = f"prin-b-{uuid.uuid4().hex[:8]}"
    await conn.execute(
        text(
            "INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) VALUES "
            "(:pa, :oa, 'HUMAN_OPERATOR', 'User A', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
            "(:pb, :ob, 'HUMAN_OPERATOR', 'User B', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
        ),
        {"pa": p_a, "oa": org_a, "pb": p_b, "ob": org_b},
    )
    return org_a, org_b, p_a, p_b


@pytest.mark.asyncio
async def test_direct_sql_rejects_wrong_grantor(pg_test_db: str) -> None:
    """Category 1: Authority edge with wrong-tenant grantor is rejected by database constraint."""
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a, org_b, p_a, p_b = await _seed_two_tenants_and_principals(conn)
        with pytest.raises(Exception) as exc:
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_authority_edges "
                    "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                    "VALUES (:id, :grantor, :grantee, :org, 'mcp_exec', '2026-01-01T00:00:00Z', 'digest1')"
                ),
                {"id": f"edge-wg-{uuid.uuid4().hex[:6]}", "grantor": p_b, "grantee": p_a, "org": org_a},
            )
        err = str(exc.value).lower()
        assert "foreign key" in err or "violates" in err or "constraint" in err
    await engine.close()


@pytest.mark.asyncio
async def test_direct_sql_rejects_wrong_grantee(pg_test_db: str) -> None:
    """Category 2: Authority edge with wrong-tenant grantee is rejected by database constraint."""
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a, org_b, p_a, p_b = await _seed_two_tenants_and_principals(conn)
        with pytest.raises(Exception) as exc:
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_authority_edges "
                    "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                    "VALUES (:id, :grantor, :grantee, :org, 'mcp_exec', '2026-01-01T00:00:00Z', 'digest2')"
                ),
                {"id": f"edge-we-{uuid.uuid4().hex[:6]}", "grantor": p_a, "grantee": p_b, "org": org_a},
            )
        err = str(exc.value).lower()
        assert "foreign key" in err or "violates" in err or "constraint" in err
    await engine.close()


@pytest.mark.asyncio
async def test_direct_sql_rejects_wrong_relationship_subject(pg_test_db: str) -> None:
    """Category 3: Relationship with wrong-tenant subject is rejected by database constraint."""
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a, org_b, p_a, p_b = await _seed_two_tenants_and_principals(conn)
        with pytest.raises(Exception) as exc:
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_relationships "
                    "(id, subject_principal_id, target_principal_id, org_id, relationship_type, valid_from, source_id) "
                    "VALUES (:id, :subject, :target, :org, 'MEMBER_OF', '2026-01-01T00:00:00Z', 'src1')"
                ),
                {"id": f"rel-ws-{uuid.uuid4().hex[:6]}", "subject": p_b, "target": p_a, "org": org_a},
            )
        err = str(exc.value).lower()
        assert "foreign key" in err or "violates" in err or "constraint" in err
    await engine.close()


@pytest.mark.asyncio
async def test_direct_sql_rejects_wrong_relationship_target(pg_test_db: str) -> None:
    """Category 4: Relationship with wrong-tenant target is rejected by database constraint."""
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a, org_b, p_a, p_b = await _seed_two_tenants_and_principals(conn)
        with pytest.raises(Exception) as exc:
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_relationships "
                    "(id, subject_principal_id, target_principal_id, org_id, relationship_type, valid_from, source_id) "
                    "VALUES (:id, :subject, :target, :org, 'MEMBER_OF', '2026-01-01T00:00:00Z', 'src2')"
                ),
                {"id": f"rel-wt-{uuid.uuid4().hex[:6]}", "subject": p_a, "target": p_b, "org": org_a},
            )
        err = str(exc.value).lower()
        assert "foreign key" in err or "violates" in err or "constraint" in err
    await engine.close()


@pytest.mark.asyncio
async def test_direct_sql_rejects_wrong_identifier(pg_test_db: str) -> None:
    """Category 5: Identifier with wrong-tenant principal is rejected by database constraint."""
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a, org_b, p_a, p_b = await _seed_two_tenants_and_principals(conn)
        with pytest.raises(Exception) as exc:
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_identifiers "
                    "(id, principal_id, org_id, identifier_type, raw_value, normalized_value, created_at) "
                    "VALUES (:id, :prin, :org, 'EMAIL', 'b@example.com', 'b@example.com', '2026-01-01T00:00:00Z')"
                ),
                {"id": f"id-wp-{uuid.uuid4().hex[:6]}", "prin": p_b, "org": org_a},
            )
        err = str(exc.value).lower()
        assert "foreign key" in err or "violates" in err or "constraint" in err
    await engine.close()


@pytest.mark.asyncio
async def test_direct_sql_rejects_wrong_trust_root(pg_test_db: str) -> None:
    """Category 6: Trust root with wrong-tenant root principal is rejected by database constraint."""
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        org_a, org_b, p_a, p_b = await _seed_two_tenants_and_principals(conn)
        with pytest.raises(Exception) as exc:
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_trust_roots "
                    "(id, org_id, root_principal_id, root_public_key, established_at, canonical_digest) "
                    "VALUES (:id, :org, :root_prin, 'pubkey123', '2026-01-01T00:00:00Z', 'digest_root')"
                ),
                {"id": f"root-wr-{uuid.uuid4().hex[:6]}", "org": org_a, "root_prin": p_b},
            )
        err = str(exc.value).lower()
        assert "foreign key" in err or "violates" in err or "constraint" in err
    await engine.close()


@pytest.mark.asyncio
async def test_direct_sql_same_tenant_positive_controls(pg_test_db: str) -> None:
    """Positive controls: Valid same-tenant operations succeed across all categories."""
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)

    async with engine.raw.begin() as conn:
        org_id = f"org-pos-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text("INSERT INTO organizations (id, slug, name, created_at) VALUES (:o, :o, 'Positive Tenant', '2026-01-01T00:00:00Z')"),
            {"o": org_id},
        )
        p_operator = f"prin-op-{uuid.uuid4().hex[:8]}"
        p_agent = f"prin-ag-{uuid.uuid4().hex[:8]}"
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) VALUES "
                "(:p1, :org, 'HUMAN_OPERATOR', 'Operator', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                "(:p2, :org, 'AGENT', 'Agent', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            ),
            {"p1": p_operator, "p2": p_agent, "org": org_id},
        )

        # 1. Authority edge same tenant succeeds
        edge_id = f"edge-pos-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_authority_edges "
                "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                "VALUES (:id, :grantor, :grantee, :org, 'mcp_exec', '2026-01-01T00:00:00Z', 'digest_pos')"
            ),
            {"id": edge_id, "grantor": p_operator, "grantee": p_agent, "org": org_id},
        )
        c_edge = (await conn.execute(text("SELECT count(*) FROM trust_fabric_authority_edges WHERE id = :id"), {"id": edge_id})).scalar()
        assert c_edge == 1

        # 2. Relationship same tenant succeeds
        rel_id = f"rel-pos-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_relationships "
                "(id, subject_principal_id, target_principal_id, org_id, relationship_type, valid_from, source_id) "
                "VALUES (:id, :subject, :target, :org, 'DELEGATE_OF', '2026-01-01T00:00:00Z', 'src_pos')"
            ),
            {"id": rel_id, "subject": p_operator, "target": p_agent, "org": org_id},
        )
        c_rel = (await conn.execute(text("SELECT count(*) FROM trust_fabric_relationships WHERE id = :id"), {"id": rel_id})).scalar()
        assert c_rel == 1

        # 3. Identifier same tenant succeeds
        ident_id = f"ident-pos-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_identifiers "
                "(id, principal_id, org_id, identifier_type, raw_value, normalized_value, created_at) "
                "VALUES (:id, :prin, :org, 'EMAIL', 'op@test.com', 'op@test.com', '2026-01-01T00:00:00Z')"
            ),
            {"id": ident_id, "prin": p_operator, "org": org_id},
        )
        c_id = (await conn.execute(text("SELECT count(*) FROM trust_fabric_identifiers WHERE id = :id"), {"id": ident_id})).scalar()
        assert c_id == 1

        # 4. Trust root same tenant succeeds
        root_id = f"root-pos-{uuid.uuid4().hex[:6]}"
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_trust_roots "
                "(id, org_id, root_principal_id, root_public_key, established_at, canonical_digest) "
                "VALUES (:id, :org, :root_prin, 'pubkey_pos', '2026-01-01T00:00:00Z', 'digest_pos')"
            ),
            {"id": root_id, "org": org_id, "root_prin": p_operator},
        )
        c_root = (await conn.execute(text("SELECT count(*) FROM trust_fabric_trust_roots WHERE id = :id"), {"id": root_id})).scalar()
        assert c_root == 1

    await engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("corruption_class", "expected_err_substring"),
    [
        ("authority_grantor_mismatch", "cross-tenant authority edge"),
        ("authority_grantee_mismatch", "cross-tenant authority edge"),
        ("relationship_subject_mismatch", "cross-tenant relationship"),
        ("relationship_target_mismatch", "cross-tenant relationship"),
        ("identifier_principal_mismatch", "cross-tenant identifier"),
        ("trust_root_principal_mismatch", "cross-tenant trust root"),
    ],
)
async def test_migration_preflight_fails_closed_on_corrupt_historical_data(
    pg_test_db: str,
    corruption_class: str,
    expected_err_substring: str,
) -> None:
    """Codex Section 14: Migration 0046 must fail closed across all 6 corruption classes at 0045.

    Migration success on corrupt database: 0.
    Zero silent repair, zero silent deletion, zero tenant reassignment.
    """
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # 1. Upgrade to 0045
    await _run_alembic(ini, env, "upgrade", "0045")

    engine = create_engine(pg_test_db)
    org_a = f"org-a-{uuid.uuid4().hex[:6]}"
    org_b = f"org-b-{uuid.uuid4().hex[:6]}"
    p_a = f"prin-a-{uuid.uuid4().hex[:8]}"
    p_b = f"prin-b-{uuid.uuid4().hex[:8]}"
    corrupt_id = f"corrupt-{uuid.uuid4().hex[:8]}"

    async with engine.raw.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO organizations (id, slug, name, created_at) VALUES "
                "(:a, :a, 'Tenant A', '2026-01-01T00:00:00Z'), "
                "(:b, :b, 'Tenant B', '2026-01-01T00:00:00Z')"
            ),
            {"a": org_a, "b": org_b},
        )
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) VALUES "
                "(:pa, :oa, 'HUMAN', 'A', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                "(:pb, :ob, 'HUMAN', 'B', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            ),
            {"pa": p_a, "oa": org_a, "pb": p_b, "ob": org_b},
        )

        if corruption_class == "authority_grantor_mismatch":
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_authority_edges "
                    "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                    "VALUES (:id, :grantor, :grantee, :org, 'mcp_exec', '2026-01-01T00:00:00Z', 'dig')"
                ),
                {"id": corrupt_id, "grantor": p_b, "grantee": p_a, "org": org_a},
            )
        elif corruption_class == "authority_grantee_mismatch":
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_authority_edges "
                    "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, canonical_digest) "
                    "VALUES (:id, :grantor, :grantee, :org, 'mcp_exec', '2026-01-01T00:00:00Z', 'dig')"
                ),
                {"id": corrupt_id, "grantor": p_a, "grantee": p_b, "org": org_a},
            )
        elif corruption_class == "relationship_subject_mismatch":
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_relationships "
                    "(id, subject_principal_id, target_principal_id, org_id, relationship_type, valid_from, source_id) "
                    "VALUES (:id, :sub, :tar, :org, 'MEMBER', '2026-01-01T00:00:00Z', 'src')"
                ),
                {"id": corrupt_id, "sub": p_b, "tar": p_a, "org": org_a},
            )
        elif corruption_class == "relationship_target_mismatch":
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_relationships "
                    "(id, subject_principal_id, target_principal_id, org_id, relationship_type, valid_from, source_id) "
                    "VALUES (:id, :sub, :tar, :org, 'MEMBER', '2026-01-01T00:00:00Z', 'src')"
                ),
                {"id": corrupt_id, "sub": p_a, "tar": p_b, "org": org_a},
            )
        elif corruption_class == "identifier_principal_mismatch":
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_identifiers "
                    "(id, principal_id, org_id, identifier_type, raw_value, normalized_value, created_at) "
                    "VALUES (:id, :prin, :org, 'EMAIL', 'b@ex.com', 'b@ex.com', '2026-01-01T00:00:00Z')"
                ),
                {"id": corrupt_id, "prin": p_b, "org": org_a},
            )
        elif corruption_class == "trust_root_principal_mismatch":
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_trust_roots "
                    "(id, org_id, root_principal_id, root_public_key, established_at, canonical_digest) "
                    "VALUES (:id, :org, :prin, 'key', '2026-01-01T00:00:00Z', 'dig')"
                ),
                {"id": corrupt_id, "org": org_a, "prin": p_b},
            )

    await engine.close()

    # 2. Upgrade to 0046 must fail closed
    with pytest.raises(MigrationError) as exc_info:
        await _run_alembic(ini, env, "upgrade", "0046")

    err_msg = str(exc_info.value).lower()
    assert "fail closed" in err_msg
    assert expected_err_substring.lower() in err_msg

    # 3. Verify corrupt data was NOT silently deleted, modified, or repaired
    engine2 = create_engine(pg_test_db)
    async with engine2.raw.connect() as conn2:
        v = (await conn2.execute(text("SELECT version_num FROM alembic_version"))).scalar()
        assert v == "0045", "Migration version updated despite preflight failure!"

        if "authority" in corruption_class:
            c = (await conn2.execute(text("SELECT count(*) FROM trust_fabric_authority_edges WHERE id = :id"), {"id": corrupt_id})).scalar()
        elif "relationship" in corruption_class:
            c = (await conn2.execute(text("SELECT count(*) FROM trust_fabric_relationships WHERE id = :id"), {"id": corrupt_id})).scalar()
        elif "identifier" in corruption_class:
            c = (await conn2.execute(text("SELECT count(*) FROM trust_fabric_identifiers WHERE id = :id"), {"id": corrupt_id})).scalar()
        elif "trust_root" in corruption_class:
            c = (await conn2.execute(text("SELECT count(*) FROM trust_fabric_trust_roots WHERE id = :id"), {"id": corrupt_id})).scalar()
        else:
            c = 0
        assert c == 1, f"Corrupt row was silently deleted or repaired in {corruption_class}!"

    await engine2.close()
