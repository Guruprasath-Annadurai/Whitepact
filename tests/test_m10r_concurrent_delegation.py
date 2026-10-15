# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M10-R Concurrent PostgreSQL Delegation Cycle & Authority Attenuation Verification.

Proves against real isolated PostgreSQL:
1. Strict transaction serialization on delegation mutations via exclusive org epoch locks.
2. Concurrent mutual delegation races cannot form cycles (A -> B and B -> A).
3. Transitive cycles under concurrent load (A -> B -> C -> D -> E, concurrent E -> A) are blocked.
4. Concurrent attenuation escalation attempts are 100% rejected; only valid monotonic attenuations succeed.
5. Concurrent cascading revocation during active delegation tree expansion stops or invalidates descendant paths.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import Any

import pytest
from sqlalchemy import insert

from responsibleai.db.delegation_repository import DelegationEscalationError, DelegationRepository
from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.migrate import run_migrations_or_raise
from tests.pg_test_url import create_isolated_database, database_url, drop_isolated_database

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def pg_engine():
    """Provision a clean, disposable PostgreSQL database with full schema applied."""
    admin_url, db_name = await create_isolated_database("m10r_delegation")
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


async def _create_org(engine: Any, org_id: str) -> None:
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name=f"Org {org_id}",
                slug=f"slug-{org_id}",
                created_at="2026-10-14T00:00:00Z",
            )
        )


async def test_concurrent_mutual_delegation_cycle_race_rejected(pg_engine: Any) -> None:
    """Two concurrent operations attempt to create mutual delegations:
    Task 1: A -> B
    Task 2: B -> A
    Under PostgreSQL concurrency, at most one can ever succeed, or both fail if neither has an active root grant.
    If A starts as root, Task 1 (A -> B) may succeed, but Task 2 (B -> A) MUST be rejected as a cycle.
    Under NO circumstances can both A -> B and B -> A become active simultaneously.
    """
    repo = DelegationRepository(pg_engine)
    org_id = f"org-race-{uuid.uuid4().hex[:8]}"
    await _create_org(pg_engine, org_id)

    # Grant root delegation to agent-A
    await repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="agent-A",
        granted_action_types=frozenset({"read", "write", "execute"}),
        constraints={"max_value": 1000},
        purpose="m10r-test",
        granted_by="admin",
    )

    # Concurrently attempt:
    # 1. A delegates to B
    # 2. B delegates to A (which would create cycle A -> B -> A)
    results = await asyncio.gather(
        repo.grant(
            org_id=org_id,
            from_identity_id="agent-A",
            to_identity_id="agent-B",
            granted_action_types=frozenset({"read", "write"}),
            constraints={"max_value": 500},
            purpose="m10r-test",
            granted_by="agent-A",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="agent-B",
            to_identity_id="agent-A",
            granted_action_types=frozenset({"read"}),
            constraints={"max_value": 200},
            purpose="m10r-test",
            granted_by="agent-B",
        ),
        return_exceptions=True,
    )

    successes = [r for r in results if not isinstance(r, Exception)]
    failures = [r for r in results if isinstance(r, Exception)]

    assert len(successes) == 1, f"Expected exactly 1 success, got {len(successes)}: {results}"
    assert len(failures) == 1, f"Expected exactly 1 failure, got {len(failures)}: {results}"
    assert isinstance(failures[0], DelegationEscalationError)

    # Verify active delegations in DB
    del_a = await repo.get_active_delegation(org_id, "agent-A")
    del_b = await repo.get_active_delegation(org_id, "agent-B")
    assert del_a is not None
    assert del_a.from_identity_id is None  # A is root

    assert del_b is not None
    assert del_b.from_identity_id == "agent-A"

    # Verify authority chain for B: [A, B]
    chain_b = await repo.get_authority_chain(org_id, "agent-B")
    assert [d.to_identity_id for d in chain_b] == ["agent-A", "agent-B"]


async def test_concurrent_transitive_cycle_attempts_rejected(pg_engine: Any) -> None:
    """Setup a 5-hop chain: Root -> A -> B -> C -> D -> E.
    Launch 10 concurrent tasks attempting to close cycles:
    - E -> A
    - E -> B
    - E -> C
    - E -> D
    - D -> A
    - C -> A
    - E -> E (self-delegation)
    - D -> D
    Plus 2 valid leaf delegations:
    - E -> F1
    - E -> F2
    Verify all cycle attempts raise DelegationEscalationError, valid leaf delegations succeed,
    and no cycles exist in the resulting graph.
    """
    repo = DelegationRepository(pg_engine)
    org_id = f"org-chain-{uuid.uuid4().hex[:8]}"
    await _create_org(pg_engine, org_id)

    # Build initial chain: Root -> A -> B -> C -> D -> E
    actions = frozenset({"read", "write", "delegate", "report"})
    await repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="A",
        granted_action_types=actions,
        purpose="m10r-test",
        granted_by="admin",
    )
    await repo.grant(
        org_id=org_id,
        from_identity_id="A",
        to_identity_id="B",
        granted_action_types=actions,
        purpose="m10r-test",
        granted_by="A",
    )
    await repo.grant(
        org_id=org_id,
        from_identity_id="B",
        to_identity_id="C",
        granted_action_types=actions,
        purpose="m10r-test",
        granted_by="B",
    )
    await repo.grant(
        org_id=org_id,
        from_identity_id="C",
        to_identity_id="D",
        granted_action_types=actions,
        purpose="m10r-test",
        granted_by="C",
    )
    await repo.grant(
        org_id=org_id,
        from_identity_id="D",
        to_identity_id="E",
        granted_action_types=actions,
        purpose="m10r-test",
        granted_by="D",
    )

    # Verify initial chain depth
    chain_e = await repo.get_authority_chain(org_id, "E")
    assert [d.to_identity_id for d in chain_e] == ["A", "B", "C", "D", "E"]

    # Concurrent cycle attempts and valid leaf attempts
    cycle_calls = [
        repo.grant(
            org_id=org_id,
            from_identity_id="E",
            to_identity_id="A",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="E",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="E",
            to_identity_id="B",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="E",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="E",
            to_identity_id="C",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="E",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="E",
            to_identity_id="D",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="E",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="D",
            to_identity_id="A",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="D",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="C",
            to_identity_id="A",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="C",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="E",
            to_identity_id="E",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="E",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="D",
            to_identity_id="D",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="D",
        ),
    ]

    valid_calls = [
        repo.grant(
            org_id=org_id,
            from_identity_id="E",
            to_identity_id="F1",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="E",
        ),
        repo.grant(
            org_id=org_id,
            from_identity_id="E",
            to_identity_id="F2",
            granted_action_types=frozenset({"read"}),
            purpose="m10r-test",
            granted_by="E",
        ),
    ]

    all_tasks = cycle_calls + valid_calls
    results = await asyncio.gather(*all_tasks, return_exceptions=True)

    # First 8 were cycle calls: ALL 8 MUST BE DelegationEscalationError
    for i, res in enumerate(results[:8]):
        assert isinstance(res, DelegationEscalationError), (
            f"Cycle attempt #{i} expected DelegationEscalationError, got: {res}"
        )

    # Last 2 were valid calls: BOTH MUST SUCCEED
    for i, res in enumerate(results[8:], start=8):
        assert not isinstance(res, Exception), f"Valid delegation #{i} failed: {res}"

    # Verify F1 and F2 are valid descendants of E
    chain_f1 = await repo.get_authority_chain(org_id, "F1")
    assert [d.to_identity_id for d in chain_f1] == ["A", "B", "C", "D", "E", "F1"]

    chain_f2 = await repo.get_authority_chain(org_id, "F2")
    assert [d.to_identity_id for d in chain_f2] == ["A", "B", "C", "D", "E", "F2"]


async def test_concurrent_authority_attenuation_race(pg_engine: Any) -> None:
    """Root agent has constrained authority (actions={"read", "query"}, max_value_usd=100.0).
    Concurrently launch 20 requests:
    - 10 valid attenuations: actions={"read"}, max_value_usd <= 100.0
    - 10 invalid escalations:
        - 5 exceeding max_value_usd (> 100.0)
        - 5 expanding action set (adding "delete", "write", "admin")
    Proves that 100% of escalations are rejected and all valid attenuations succeed concurrently.
    """
    repo = DelegationRepository(pg_engine)
    org_id = f"org-atten-{uuid.uuid4().hex[:8]}"
    await _create_org(pg_engine, org_id)

    # Root grant
    await repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="root-agent",
        granted_action_types=frozenset({"read", "query"}),
        constraints={"max_value_usd": 100.0},
        purpose="m10r-test",
        granted_by="admin",
    )

    tasks = []
    expected_outcomes = []  # True for success, False for escalation

    # 10 valid attenuations
    for i in range(10):
        tasks.append(
            repo.grant(
                org_id=org_id,
                from_identity_id="root-agent",
                to_identity_id=f"valid-child-{i}",
                granted_action_types=frozenset({"read"}),
                constraints={"max_value_usd": 10.0 + i * 5.0},
                purpose="m10r-test",
                granted_by="root-agent",
            )
        )
        expected_outcomes.append(True)

    # 5 value escalations (max_value_usd > 100.0)
    for i in range(5):
        tasks.append(
            repo.grant(
                org_id=org_id,
                from_identity_id="root-agent",
                to_identity_id=f"escalate-val-{i}",
                granted_action_types=frozenset({"read"}),
                constraints={"max_value_usd": 150.0 + i * 10.0},
                purpose="m10r-test",
                granted_by="root-agent",
            )
        )
        expected_outcomes.append(False)

    # 5 action set escalations (adding unauthorized actions)
    for i, bad_action in enumerate(["delete", "write", "admin", "drop_db", "reboot"]):
        tasks.append(
            repo.grant(
                org_id=org_id,
                from_identity_id="root-agent",
                to_identity_id=f"escalate-act-{i}",
                granted_action_types=frozenset({"read", bad_action}),
                constraints={"max_value_usd": 50.0},
                purpose="m10r-test",
                granted_by="root-agent",
            )
        )
        expected_outcomes.append(False)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, (res, should_succeed) in enumerate(zip(results, expected_outcomes, strict=False)):
        if should_succeed:
            assert not isinstance(res, Exception), (
                f"Task {i} was expected to succeed but raised {res}"
            )
        else:
            assert isinstance(res, DelegationEscalationError), (
                f"Task {i} was expected to raise DelegationEscalationError but got {res}"
            )

    # Verify that exactly 10 valid children were created in PostgreSQL
    for i in range(10):
        rec = await repo.get_active_delegation(org_id, f"valid-child-{i}")
        assert rec is not None
        assert rec.from_identity_id == "root-agent"
        assert rec.granted_action_types == frozenset({"read"})

    # Verify that NONE of the escalation agents exist
    for i in range(5):
        assert await repo.get_active_delegation(org_id, f"escalate-val-{i}") is None
        assert await repo.get_active_delegation(org_id, f"escalate-act-{i}") is None


async def test_concurrent_cascading_revocation_during_expansion(pg_engine: Any) -> None:
    """Verifies that if an ancestor is revoked concurrently while child delegations
    are being granted underneath it, the cascading revocation guarantees hold:
    - Any grant committed after the revocation is either rejected (because parent is revoked)
      or, if granted right before, is immediately inactivated by the cascade.
    - Subsequent authority chain queries for any descendant return empty or stop at the revoked ancestor.
    """
    repo = DelegationRepository(pg_engine)
    org_id = f"org-cascade-{uuid.uuid4().hex[:8]}"
    await _create_org(pg_engine, org_id)

    # Root -> Supervisor
    await repo.grant(
        org_id=org_id,
        from_identity_id=None,
        to_identity_id="supervisor",
        granted_action_types=frozenset({"manage", "delegate", "work"}),
        purpose="m10r-test",
        granted_by="admin",
    )

    # Concurrently:
    # 1. 10 workers try to be delegated under supervisor
    # 2. Revoke supervisor concurrently via revoke_branch
    worker_tasks = [
        repo.grant(
            org_id=org_id,
            from_identity_id="supervisor",
            to_identity_id=f"sub-worker-{i}",
            granted_action_types=frozenset({"work"}),
            purpose="m10r-test",
            granted_by="supervisor",
        )
        for i in range(10)
    ]
    revoke_task = repo.revoke_branch(
        org_id=org_id,
        identity_id="supervisor",
        revoked_by="security-admin",
        reason="Security breach containment",
    )

    all_results = await asyncio.gather(*worker_tasks, revoke_task, return_exceptions=True)

    # Revoke task MUST have succeeded
    revoke_result = all_results[-1]
    assert not isinstance(revoke_result, Exception), f"Revoke failed: {revoke_result}"

    # Now verify: is supervisor active? MUST BE FALSE
    sup_active = await repo.get_active_delegation(org_id, "supervisor")
    assert sup_active is None, "Supervisor must not have active delegation after revocation"

    # Now verify: for every single sub-worker, none of them can have a valid authority chain!
    for i in range(10):
        chain = await repo.get_authority_chain(org_id, f"sub-worker-{i}")
        # Chain must be empty because the ancestor supervisor is revoked!
        assert len(chain) == 0, (
            f"sub-worker-{i} must have empty authority chain, but had {len(chain)}"
        )
