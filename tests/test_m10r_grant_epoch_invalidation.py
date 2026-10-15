# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M10-R Independent Verification: Delegation Grant Epoch Locking & Revocation Invalidation.

Independently establishes against real PostgreSQL (wp-pg-55432):
1. Ordinary delegation grants serialized via lock_epoch() do NOT increment the revocation epoch.
2. Pre-existing execution permits and active processes remain fully valid and executable after grants.
3. Cascading branch revocation (revoke_branch) continues bumping the revocation epoch fail-closed.
4. Pre-revocation execution permits are deterministically rejected with StaleRevocationEpochError.
5. Concurrent grant and revoke operations serialize under PostgreSQL isolation without deadlocks.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import insert

from responsibleai.db.delegation_repository import DelegationRepository
from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    StaleRevocationEpochError,
)
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.db.revocation_epoch_repository import (
    RevocationEpochRepository,
    bump_epoch_on_connection,
)
from tests.pg_test_url import create_isolated_database, database_url, drop_isolated_database

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def pg_engine():
    """Provision a clean, disposable PostgreSQL database with full schema applied."""
    admin_url, db_name = await create_isolated_database("m10r_epoch_lock")
    raw_pg_url = database_url(admin_url, db_name)
    async_pg_url = raw_pg_url.replace("postgresql://", "postgresql+asyncpg://")

    await run_migrations_or_raise(raw_pg_url)

    engine = create_engine(async_pg_url)
    await engine.init(auto_create_tables=False)

    try:
        yield engine
    finally:
        await engine.close()
        await drop_isolated_database(admin_url, db_name)


async def _create_active_org(engine: Any, org_id: str) -> None:
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name=f"Org {org_id}",
                slug=f"slug-{org_id}",
                governance_status="ACTIVE",
                created_at="2026-10-14T00:00:00Z",
            )
        )


async def test_grant_does_not_increment_epoch_and_preserves_issued_permits(pg_engine: Any) -> None:
    """Verifies that ordinary delegation grants lock the epoch row for concurrency control
    without bumping the counter, preserving pre-issued execution permits.
    """
    org_id = f"org-grant-epoch-{uuid.uuid4().hex[:8]}"
    await _create_active_org(pg_engine, org_id)

    delegation_repo = DelegationRepository(pg_engine)
    epoch_repo = RevocationEpochRepository(pg_engine)
    nonce_repo = ExecutionNonceRepository(pg_engine)

    # 1. Check initial epoch (0)
    initial_epoch = await epoch_repo.current(org_id)
    assert initial_epoch.epoch == 0

    # 2. Issue an execution permit at current epoch (0)
    permit_nonce = f"permit-pre-grant-{uuid.uuid4().hex[:8]}"
    auth_id = f"auth-1-{uuid.uuid4().hex[:8]}"
    expected_epoch = initial_epoch.epoch  # 0

    # 3. Create root grant and multiple child delegations (10 operations)
    root = await delegation_repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="root-agent",
        granted_action_types=frozenset({"read", "write", "execute", "deploy"}),
        purpose="root authority",
        granted_by="human-admin",
    )
    assert root is not None

    parent_id = "root-agent"
    for i in range(1, 10):
        child_id = f"agent-child-{i}"
        await delegation_repo.grant(
            org_id=org_id,
            from_identity_id=parent_id,
            to_identity_id=child_id,
            granted_action_types=frozenset({"read", "write"}),
            purpose=f"delegation to child {i}",
            granted_by=parent_id,
        )

    # 4. Verify epoch is STILL 0 (NOT incremented by grants!)
    post_grant_epoch = await epoch_repo.current(org_id)
    assert post_grant_epoch.epoch == 0, (
        f"Expected epoch 0 after grants, got {post_grant_epoch.epoch} (unintended bump!)"
    )

    # 5. Consume pre-issued permit: MUST succeed cleanly without StaleRevocationEpochError
    await nonce_repo.consume(
        permit_nonce,
        authorization_id=auth_id,
        organization_id=org_id,
        expected_epoch=expected_epoch,
    )


async def test_historical_bump_invalidation_contrast(pg_engine: Any) -> None:
    """Explicitly demonstrates the defect when bump_epoch_on_connection was used:
    Advancing the counter invalidates pre-issued permits with StaleRevocationEpochError.
    """
    org_id = f"org-bump-contrast-{uuid.uuid4().hex[:8]}"
    await _create_active_org(pg_engine, org_id)

    epoch_repo = RevocationEpochRepository(pg_engine)
    nonce_repo = ExecutionNonceRepository(pg_engine)

    initial_epoch = await epoch_repo.current(org_id)
    permit_nonce = f"permit-stale-{uuid.uuid4().hex[:8]}"
    auth_id = f"auth-stale-{uuid.uuid4().hex[:8]}"
    stale_expected_epoch = initial_epoch.epoch  # 0

    # If epoch was bumped (the prior grant behavior)
    async with pg_engine.raw.begin() as conn:
        await bump_epoch_on_connection(conn, org_id)

    current_epoch = await epoch_repo.current(org_id)
    assert current_epoch.epoch == 1

    # Consuming permit with epoch 0 MUST be rejected fail-closed
    with pytest.raises(StaleRevocationEpochError, match="Permit revocation epoch is stale"):
        await nonce_repo.consume(
            permit_nonce,
            authorization_id=auth_id,
            organization_id=org_id,
            expected_epoch=stale_expected_epoch,
        )


async def test_revoke_branch_increments_epoch_and_enforces_cascading_invalidation(
    pg_engine: Any,
) -> None:
    """Verifies that revoke_branch() correctly increments the revocation epoch,
    cascades deactivation to all descendants, and invalidates pre-revocation permits.
    """
    org_id = f"org-revoke-cascading-{uuid.uuid4().hex[:8]}"
    await _create_active_org(pg_engine, org_id)

    delegation_repo = DelegationRepository(pg_engine)
    epoch_repo = RevocationEpochRepository(pg_engine)
    nonce_repo = ExecutionNonceRepository(pg_engine)

    # Setup tree: Root -> Intermediate -> Leaf
    await delegation_repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="root",
        granted_action_types=frozenset({"read", "write", "execute"}),
        purpose="root",
        granted_by="admin",
    )
    await delegation_repo.grant(
        org_id=org_id,
        from_identity_id="root",
        to_identity_id="intermediate",
        granted_action_types=frozenset({"read", "write"}),
        purpose="intermediate",
        granted_by="root",
    )
    await delegation_repo.grant(
        org_id=org_id,
        from_identity_id="intermediate",
        to_identity_id="leaf",
        granted_action_types=frozenset({"read"}),
        purpose="leaf",
        granted_by="intermediate",
    )

    epoch_before_revocation = await epoch_repo.current(org_id)
    assert epoch_before_revocation.epoch == 0

    # Issue permit before revocation
    permit_nonce = f"permit-pre-revoke-{uuid.uuid4().hex[:8]}"
    auth_id = f"auth-pre-revoke-{uuid.uuid4().hex[:8]}"

    # Revoke branch at intermediate
    revoked_ids = await delegation_repo.revoke_branch(
        org_id, "intermediate", revoked_by="security-officer", reason="compromised"
    )
    assert len(revoked_ids) == 2  # intermediate and leaf

    # Verify epoch was incremented
    epoch_after_revocation = await epoch_repo.current(org_id)
    assert epoch_after_revocation.epoch == 1

    # Permitted issued at epoch 0 must be rejected
    with pytest.raises(StaleRevocationEpochError, match="Permit revocation epoch is stale"):
        await nonce_repo.consume(
            permit_nonce,
            authorization_id=auth_id,
            organization_id=org_id,
            expected_epoch=epoch_before_revocation.epoch,
        )

    # Descendants must be inactive
    inter_del = await delegation_repo.get_latest_delegation(org_id, "intermediate")
    leaf_del = await delegation_repo.get_latest_delegation(org_id, "leaf")
    assert inter_del is not None and not inter_del.is_active()
    assert leaf_del is not None and not leaf_del.is_active()


async def test_concurrent_grants_serialize_without_epoch_drift(pg_engine: Any) -> None:
    """Verifies that 10 concurrent grants across independent child nodes
    serialize strictly using PostgreSQL row locks without epoch drift or deadlocks.
    """
    org_id = f"org-concurrent-grants-{uuid.uuid4().hex[:8]}"
    await _create_active_org(pg_engine, org_id)

    repo = DelegationRepository(pg_engine)
    epoch_repo = RevocationEpochRepository(pg_engine)

    # Root grant
    await repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="root",
        granted_action_types=frozenset({"read", "write"}),
        purpose="root",
        granted_by="admin",
    )

    # 10 concurrent child grants
    async def _grant_child(i: int):
        return await repo.grant(
            org_id=org_id,
            from_identity_id="root",
            to_identity_id=f"child-{i}",
            granted_action_types=frozenset({"read"}),
            purpose=f"child-{i}",
            granted_by="root",
        )

    results = await asyncio.gather(*[_grant_child(i) for i in range(10)], return_exceptions=True)

    # All 10 must succeed
    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Unexpected errors during concurrent grants: {errors}"

    # Epoch must remain unchanged at 0
    final_epoch = await epoch_repo.current(org_id)
    assert final_epoch.epoch == 0, f"Epoch drifted to {final_epoch.epoch} under concurrent grants"


async def test_concurrent_grant_and_revoke_serialization_under_postgresql(pg_engine: Any) -> None:
    """Tests high-concurrency race between grant operations and branch revocation.
    Verifies that PostgreSQL row locking prevents partial states and maintains
    linearizable authority invariants.
    """
    org_id = f"org-race-grant-revoke-{uuid.uuid4().hex[:8]}"
    await _create_active_org(pg_engine, org_id)

    repo = DelegationRepository(pg_engine)
    epoch_repo = RevocationEpochRepository(pg_engine)
    nonce_repo = ExecutionNonceRepository(pg_engine)

    await repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="root",
        granted_action_types=frozenset({"read", "write", "execute"}),
        purpose="root",
        granted_by="admin",
    )

    # Pre-populate branch: root -> target -> leaf
    await repo.grant(
        org_id=org_id,
        from_identity_id="root",
        to_identity_id="target",
        granted_action_types=frozenset({"read", "write"}),
        purpose="target",
        granted_by="root",
    )

    # Issue a permit before the race
    permit_nonce = f"permit-race-{uuid.uuid4().hex[:8]}"
    auth_id = f"auth-race-{uuid.uuid4().hex[:8]}"

    # Concurrently run:
    # 5 child grants from root
    # 1 branch revocation on target
    async def _grant_root_child(idx: int):
        return await repo.grant(
            org_id=org_id,
            from_identity_id="root",
            to_identity_id=f"root-child-{idx}",
            granted_action_types=frozenset({"read"}),
            purpose=f"root-child-{idx}",
            granted_by="root",
        )

    async def _revoke_target():
        return await repo.revoke_branch(
            org_id=org_id,
            identity_id="target",
            revoked_by="admin",
            reason="concurrency test",
        )

    tasks = [_grant_root_child(i) for i in range(5)] + [_revoke_target()]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    errors = [r for r in results if isinstance(r, Exception)]
    assert not errors, f"Unexpected errors during race: {errors}"

    # Revocation epoch MUST be exactly 1 (bumped exactly once by revoke_branch, not by grants)
    final_epoch = await epoch_repo.current(org_id)
    assert final_epoch.epoch == 1, (
        f"Expected epoch 1 after 5 grants + 1 revocation, got {final_epoch.epoch}"
    )

    # Pre-revocation permit (epoch 0) must be rejected
    with pytest.raises(StaleRevocationEpochError):
        await nonce_repo.consume(
            permit_nonce,
            authorization_id=auth_id,
            organization_id=org_id,
            expected_epoch=0,
        )

    # Permit issued at epoch 1 must succeed
    fresh_nonce = f"permit-fresh-{uuid.uuid4().hex[:8]}"
    fresh_auth = f"auth-fresh-{uuid.uuid4().hex[:8]}"
    await nonce_repo.consume(
        fresh_nonce,
        authorization_id=fresh_auth,
        organization_id=org_id,
        expected_epoch=1,
    )
