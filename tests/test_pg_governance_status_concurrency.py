# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PostgreSQL concurrency proofs for current V1 authority guarantees.

Uses an isolated local PostgreSQL instance. Never production.
Skipped only when PostgreSQL / asyncpg are genuinely unavailable.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator

import pytest

from responsibleai.db import ApprovalRepository, OrgRepository, create_engine
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    OrganizationNotGovernableError,
    StaleRevocationEpochError,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import ApprovalStatus, build_approval_request
from responsibleai.rbac.models import GovernanceStatus, Plan
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_v1_c3"):
        engine = create_engine(url)
        try:
            await engine.init()
        finally:
            await engine.close()
        yield url


@pytest.mark.asyncio
async def test_postgres_governance_status_epoch_is_serialized(pg_url: str) -> None:
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    await engine_a.init()
    await engine_b.init()
    try:
        org_a = OrgRepository(engine_a)
        org = await org_a.create_org(
            "PG Gov", f"pg-gov-{uuid.uuid4().hex[:8]}", plan=Plan.ENTERPRISE
        )
        org_b = OrgRepository(engine_b)
        epochs = RevocationEpochRepository(engine_a)

        async def suspend() -> None:
            await org_a.set_governance_status(org.id, GovernanceStatus.SUSPENDED)

        async def disable() -> None:
            await org_b.set_governance_status(org.id, GovernanceStatus.DISABLED)

        await asyncio.gather(suspend(), disable())
        current = await epochs.current(org.id)
        assert current.epoch >= 2
        loaded = await org_a.get_org(org.id)
        assert loaded is not None
        assert loaded.governance_status in {
            GovernanceStatus.SUSPENDED.value,
            GovernanceStatus.DISABLED.value,
        }
    finally:
        await engine_a.close()
        await engine_b.close()


@pytest.mark.asyncio
async def test_postgres_status_and_epoch_commit_atomically(pg_url: str) -> None:
    engine = create_engine(pg_url)
    await engine.init()
    try:
        orgs = OrgRepository(engine)
        epochs = RevocationEpochRepository(engine)
        org = await orgs.create_org("Atom", f"atom-{uuid.uuid4().hex[:8]}", plan=Plan.ENTERPRISE)
        before = await epochs.current(org.id)

        import responsibleai.db.org_repository as org_mod

        original = org_mod.bump_epoch_on_connection

        async def crash(conn, organization_id, scope="governance"):
            await original(conn, organization_id, scope)
            raise RuntimeError("injected crash after epoch bump")

        org_mod.bump_epoch_on_connection = crash
        try:
            with pytest.raises(RuntimeError, match="injected crash"):
                await orgs.set_governance_status(org.id, GovernanceStatus.SUSPENDED)
        finally:
            org_mod.bump_epoch_on_connection = original

        loaded = await orgs.get_org(org.id)
        after = await epochs.current(org.id)
        assert loaded is not None
        assert loaded.governance_status == GovernanceStatus.ACTIVE.value
        assert after.epoch == before.epoch
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_postgres_admission_cannot_win_after_suspension(pg_url: str) -> None:
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    await engine_a.init()
    await engine_b.init()
    try:
        orgs = OrgRepository(engine_a)
        org = await orgs.create_org("Race", f"race-{uuid.uuid4().hex[:8]}", plan=Plan.ENTERPRISE)
        epochs = RevocationEpochRepository(engine_a)
        start = await epochs.current(org.id)
        nonce_b = ExecutionNonceRepository(engine_b)
        org_a = OrgRepository(engine_a)

        started = asyncio.Event()
        release = asyncio.Event()

        async def hold_suspension() -> None:
            from sqlalchemy import update

            from responsibleai.db.engine import organizations
            from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection

            async with engine_a.raw.begin() as conn:
                await conn.execute(
                    update(organizations)
                    .where(organizations.c.id == org.id)
                    .values(governance_status=GovernanceStatus.SUSPENDED.value)
                )
                await bump_epoch_on_connection(conn, org.id)
                started.set()
                await release.wait()

        async def consume_while_held() -> None:
            await started.wait()
            await nonce_b.consume(
                uuid.uuid4().hex,
                authorization_id="permit",
                organization_id=org.id,
                expected_epoch=start.epoch,
            )

        hold = asyncio.create_task(hold_suspension())
        consume = asyncio.create_task(consume_while_held())
        await started.wait()
        await asyncio.sleep(0.3)
        assert not consume.done()
        release.set()
        hold_exc = await asyncio.gather(hold, return_exceptions=True)
        assert hold_exc == [None]
        with pytest.raises((OrganizationNotGovernableError, StaleRevocationEpochError)):
            await consume
        loaded = await org_a.get_org(org.id)
        assert loaded is not None
        assert loaded.governance_status == GovernanceStatus.SUSPENDED.value
    finally:
        await engine_a.close()
        await engine_b.close()


@pytest.mark.asyncio
async def test_postgres_two_connections_consume_approval_once(pg_url: str) -> None:
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    await engine_a.init()
    await engine_b.init()
    try:
        repo_a = ApprovalRepository(engine_a)
        repo_b = ApprovalRepository(engine_b)
        gw = WhitePactRuntimeGateway()
        agent = AgentContext(
            identity=IdentityContext(identity_id="agent-key", kind="api_key", org_id="org-pg"),
            framework="mcp-client",
        )
        authority = AuthorityContext(
            delegated_by="owner",
            granted_action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset({"payment.execute"}),
        )
        action = ActionRequest(agent=agent, action_type="payment.execute", target="acct-1")
        decision = gw.evaluate(action, authority)
        assert decision.decision == GovernanceDecision.REQUIRE_APPROVAL
        approval = await repo_a.create(build_approval_request(action, decision))
        await repo_a.resolve(
            approval.approval_id, resolved_by="approver-1", outcome=ApprovalStatus.APPROVED
        )
        results = await asyncio.gather(
            repo_a.consume(approval.approval_id, action=action),
            repo_b.consume(approval.approval_id, action=action),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
    finally:
        await engine_a.close()
        await engine_b.close()
