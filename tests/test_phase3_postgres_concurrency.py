# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL Concurrency & Transactional Rollback Tests for Trust Fabric."""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import select

from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_assertions,
    trust_fabric_authority_edges,
    trust_fabric_bootstrap_records,
    trust_fabric_challenges,
    trust_fabric_conflicts,
    trust_fabric_federated_assertions,
    trust_fabric_identifiers,
    trust_fabric_passports,
    trust_fabric_principals,
    trust_fabric_relationships,
    trust_fabric_sources,
    trust_fabric_trust_roots,
)
from responsibleai.trust_fabric.bootstrap import TrustBootstrapManager
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    IdentifierType,
    IdentifierVerificationState,
    PrincipalType,
)
from responsibleai.trust_fabric.errors import (
    BootstrapRaceError,
    BootstrapTokenReplayError,
    IdentifierCollisionError,
    OrganizationAlreadyBootstrappedError,
)

PG_TEST_URL = "postgresql://ag@/wp_phase3_test?host=/tmp"


@pytest.fixture
async def pg_engine():
    engine = create_engine(PG_TEST_URL)
    await engine.init()
    async with engine.raw.begin() as conn:
        # Clean test tables in child-to-parent order
        await conn.execute(trust_fabric_federated_assertions.delete())
        await conn.execute(trust_fabric_challenges.delete())
        await conn.execute(trust_fabric_conflicts.delete())
        await conn.execute(trust_fabric_passports.delete())
        await conn.execute(trust_fabric_bootstrap_records.delete())
        await conn.execute(trust_fabric_authority_edges.delete())
        await conn.execute(trust_fabric_relationships.delete())
        await conn.execute(trust_fabric_assertions.delete())
        await conn.execute(trust_fabric_sources.delete())
        await conn.execute(trust_fabric_identifiers.delete())
        await conn.execute(trust_fabric_trust_roots.delete())
        await conn.execute(trust_fabric_principals.delete())
        await conn.execute(organizations.delete())
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_pg_race", "name": "PG Race Org", "slug": "pgrace", "created_at": "now"},
                {"id": "org_pg_ident", "name": "PG Ident Org", "slug": "pgident", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_postgres_concurrent_bootstrap_50_way_race(pg_engine):
    """Under 50-way concurrent execution race on PostgreSQL, exactly ONE root winner succeeds."""
    boot_mgr = TrustBootstrapManager(pg_engine)
    dir_svc = PrincipalDirectory(pg_engine)

    alice = await dir_svc.create_principal(
        org_id="org_pg_race",
        principal_type=PrincipalType.HUMAN,
        display_name="Alice Founder",
    )
    token, nonce = await boot_mgr.issue_bootstrap_ceremony(org_id="org_pg_race")

    async def _attempt_bootstrap(idx: int) -> str:
        try:
            await boot_mgr.claim_trust_root(
                org_id="org_pg_race",
                token=token,
                nonce=nonce,
                root_principal_id=alice.id,
                root_public_key=f"pk_postgres_race_{idx}",
            )
            return "WINNER"
        except (OrganizationAlreadyBootstrappedError, BootstrapRaceError, BootstrapTokenReplayError):
            return "LOST_RACE"

    results = await asyncio.gather(*[_attempt_bootstrap(i) for i in range(50)])

    winners = [r for r in results if r == "WINNER"]
    losers = [r for r in results if r == "LOST_RACE"]

    assert len(winners) == 1, f"Expected exactly 1 winner, got {len(winners)}"
    assert len(losers) == 49, f"Expected 49 losers, got {len(losers)}"

    # Confirm only 1 trust root row in PostgreSQL
    async with pg_engine.raw.connect() as conn:
        stmt = select(trust_fabric_trust_roots).where(
            trust_fabric_trust_roots.c.org_id == "org_pg_race"
        )
        rows = (await conn.execute(stmt)).fetchall()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_postgres_concurrent_identifier_collision_defense(pg_engine):
    """50 concurrent attachment attempts for the same email on PostgreSQL yield exactly 1 success."""
    dir_svc = PrincipalDirectory(pg_engine)

    principals = []
    for i in range(50):
        p = await dir_svc.create_principal(
            org_id="org_pg_ident",
            principal_type=PrincipalType.HUMAN,
            display_name=f"User {i}",
        )
        principals.append(p)

    target_email = "ceo@pgcorp.com"

    async def _attempt_attach(principal_id: str) -> str:
        try:
            await dir_svc.attach_identifier(
                principal_id=principal_id,
                org_id="org_pg_ident",
                identifier_type=IdentifierType.EMAIL,
                value=target_email,
                verification_state=IdentifierVerificationState.VERIFIED,
            )
            return "ATTACHED"
        except IdentifierCollisionError:
            return "COLLISION_BLOCKED"

    results = await asyncio.gather(*[_attempt_attach(p.id) for p in principals])

    attached = [r for r in results if r == "ATTACHED"]
    blocked = [r for r in results if r == "COLLISION_BLOCKED"]

    assert len(attached) == 1, f"Expected exactly 1 attachment, got {len(attached)}"
    assert len(blocked) == 49, f"Expected 49 collisions blocked, got {len(blocked)}"

    # Confirm exactly 1 identifier in PostgreSQL
    async with pg_engine.raw.connect() as conn:
        stmt = select(trust_fabric_identifiers).where(
            trust_fabric_identifiers.c.normalized_value == target_email
        )
        rows = (await conn.execute(stmt)).fetchall()
        assert len(rows) == 1


@pytest.mark.asyncio
async def test_postgres_transactional_rollback_cleanliness(pg_engine):
    """Failed attachment cleanly rolls back without orphaned partial rows."""
    dir_svc = PrincipalDirectory(pg_engine)

    p1 = await dir_svc.create_principal(
        org_id="org_pg_ident",
        principal_type=PrincipalType.HUMAN,
        display_name="First Owner",
    )
    p2 = await dir_svc.create_principal(
        org_id="org_pg_ident",
        principal_type=PrincipalType.HUMAN,
        display_name="Second Owner",
    )

    await dir_svc.attach_identifier(
        principal_id=p1.id,
        org_id="org_pg_ident",
        identifier_type=IdentifierType.EMAIL,
        value="unique-owner@pgcorp.com",
        verification_state=IdentifierVerificationState.VERIFIED,
    )

    # Attempting to attach to p2 fails
    with pytest.raises(IdentifierCollisionError):
        await dir_svc.attach_identifier(
            principal_id=p2.id,
            org_id="org_pg_ident",
            identifier_type=IdentifierType.EMAIL,
            value="unique-owner@pgcorp.com",
            verification_state=IdentifierVerificationState.VERIFIED,
        )

    # Verify p2 has no attached identifiers
    async with pg_engine.raw.connect() as conn:
        stmt = select(trust_fabric_identifiers).where(
            trust_fabric_identifiers.c.principal_id == p2.id
        )
        rows = (await conn.execute(stmt)).fetchall()
        assert len(rows) == 0
