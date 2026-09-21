# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A authority kernel against real PostgreSQL.

Redis, QueueTicket, and leases are never authority. Final CAS is.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text, update

from responsibleai.db.engine import create_engine
from responsibleai.db.engine import runtime_execution_attempts as attempts
from responsibleai.db.engine import runtime_execution_dispatch_outbox as outbox
from responsibleai.db.engine import runtime_worker_leases as leases
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.rbac.models import GovernanceStatus, Plan
from responsibleai.runtime.authority_kernel import (
    Phase7AAuthorityKernel,
    QueueTicket,
    retry_pre_effect,
)
from responsibleai.runtime.capacity_reservation import AtomicCapacityReservation, InMemoryRedisEval
from responsibleai.runtime.errors import (
    AuthorityKernelError,
    CrossTenantAccessError,
    DuplicateEffectClaimError,
    IdempotencyConflictError,
    PreEffectCasRejected,
    StaleWorkerError,
    UncertainExternalEffectError,
)
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_p7a_kern"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        yield url


async def _org(engine, name: str = "P7A"):
    repo = OrgRepository(engine)
    return await repo.create_org(name, f"p7a-{uuid.uuid4().hex[:10]}", plan=Plan.ENTERPRISE)


def _issue_kwargs(org_id: str, digest: str = "a" * 64, key: str | None = None, **extra):
    payload = '{"action_type":"tool"}'
    kw = dict(
        organization_id=org_id,
        principal_id="principal-1",
        agent_id="agent-1",
        identity_id="identity-1",
        intent="declared purpose",
        action_type="rai_trust_score",
        target="rai_trust_score",
        action_digest=digest,
        canonical_action_payload=payload,
        approved_arguments={"text": "redacted"},
        idempotency_key=key or uuid.uuid4().hex,
        target_fingerprint="fp-1",
        caller_organization_id=org_id,
    )
    kw.update(extra)
    return kw


async def _ready_claim(kernel, org_id, worker="worker-a"):
    issued = await kernel.issue(**_issue_kwargs(org_id))
    await kernel.acquire_lease(
        request_id=issued.request_id, worker_id=worker, organization_id=org_id
    )
    await kernel.admit(request_id=issued.request_id, worker_id=worker, organization_id=org_id)
    claim = await kernel.claim_backend_start(
        request_id=issued.request_id, worker_id=worker, organization_id=org_id
    )
    return issued, claim


class MemoryTransport:
    def __init__(self) -> None:
        self.tickets: list[QueueTicket] = []
        self.fail = False

    def enqueue(self, ticket: QueueTicket) -> None:
        if self.fail:
            raise ConnectionError("redis down")
        self.tickets.append(ticket)


@pytest.mark.asyncio
async def test_happy_local_cas(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued, claim = await _ready_claim(kernel, org.id)
        permit = await kernel.claim_local_effect_start(
            claim,
            action_digest=issued.request_id and claim.action_digest,
            target_fingerprint="fp-1",
        )
        assert permit.effect_id == issued.effect_id
        req = await kernel.load_request(issued.request_id, organization_id=org.id)
        assert req["lifecycle"] == "RECORDED"
        assert req["observed_governance_epoch"] == issued.observed_epoch
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_concurrent_idempotent_issuance(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        key = "same-key"
        digest = "b" * 64
        results = await asyncio.gather(
            kernel.issue(**_issue_kwargs(org.id, digest=digest, key=key)),
            kernel.issue(**_issue_kwargs(org.id, digest=digest, key=key)),
        )
        ids = {r.request_id for r in results}
        assert len(ids) == 1
        with pytest.raises(IdempotencyConflictError):
            await kernel.issue(**_issue_kwargs(org.id, digest="c" * 64, key=key))
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_concurrent_authorization_consume(pg_url: str) -> None:
    engine_a = create_engine(pg_url)
    engine_b = create_engine(pg_url)
    try:
        org = await _org(engine_a)
        ka = Phase7AAuthorityKernel(engine_a)
        kb = Phase7AAuthorityKernel(engine_b)
        issued = await ka.issue(**_issue_kwargs(org.id))
        await ka.acquire_lease(request_id=issued.request_id, worker_id="w1", organization_id=org.id)

        async def admit_a():
            await ka.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)

        async def admit_b():
            await kb.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)

        results = await asyncio.gather(admit_a(), admit_b(), return_exceptions=True)
        wins = [r for r in results if r is None]
        losses = [r for r in results if isinstance(r, Exception)]
        assert len(wins) == 1
        assert len(losses) == 1
    finally:
        await engine_a.close()
        await engine_b.close()


@pytest.mark.asyncio
async def test_duplicate_queue_tickets_do_not_duplicate_effects(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        transport = MemoryTransport()
        t1 = await kernel.publish_outbox(publisher_id="pub-1", transport=transport)
        assert t1 is not None
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(outbox)
                .where(outbox.c.request_id == issued.request_id)
                .values(status="PUBLISHING", published_at=None)
            )
        t2 = await kernel.publish_outbox(publisher_id="pub-1", transport=transport)
        # Either no row (already publishing handled) or a duplicate ticket.
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
        claim = await kernel.claim_backend_start(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        await kernel.claim_local_effect_start(
            claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
        )
        with pytest.raises((DuplicateEffectClaimError, PreEffectCasRejected)):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
        _ = t2
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_stale_worker_and_fence(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued, claim_w1 = await _ready_claim(kernel, org.id, worker="w1")
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w2", organization_id=org.id
        )
        with pytest.raises((PreEffectCasRejected, StaleWorkerError)):
            await kernel.claim_local_effect_start(
                claim_w1, action_digest=claim_w1.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_expired_lease_fails_cas(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(leases)
                .where(leases.c.lease_id == claim.lease_id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=5))
            )
        with pytest.raises((PreEffectCasRejected, StaleWorkerError)):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
        async with engine.raw.connect() as conn:
            state = (
                await conn.execute(
                    select(attempts.c.state).where(attempts.c.attempt_id == claim.attempt_id)
                )
            ).scalar_one()
        assert state == "FAILED_PRE_EXECUTION"
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_suspension_and_epoch_bump_before_effect(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued, claim = await _ready_claim(kernel, org.id)
        orgs = OrgRepository(engine)
        await orgs.set_governance_status(org.id, GovernanceStatus.SUSPENDED)
        with pytest.raises(PreEffectCasRejected):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
        await orgs.set_governance_status(org.id, GovernanceStatus.ACTIVE)
        issued2, claim2 = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await bump_epoch_on_connection(conn, org.id)
        with pytest.raises(PreEffectCasRejected, match="epoch"):
            await kernel.claim_local_effect_start(
                claim2, action_digest=claim2.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_wrong_digest_and_fingerprint(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        with pytest.raises(PreEffectCasRejected, match="digest"):
            await kernel.claim_local_effect_start(
                claim, action_digest="0" * 64, target_fingerprint="fp-1"
            )
        _, claim2 = await _ready_claim(kernel, org.id)
        with pytest.raises(PreEffectCasRejected, match="fingerprint"):
            await kernel.claim_external_effect_transmission(
                claim2, action_digest=claim2.action_digest, target_fingerprint="other"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_duplicate_attempt_rejected(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        async with engine.raw.begin() as conn:
            from sqlalchemy.exc import IntegrityError

            with pytest.raises(IntegrityError):
                await conn.execute(
                    attempts.insert().values(
                        attempt_id=uuid.uuid4().hex,
                        request_id=issued.request_id,
                        authorization_id=issued.authorization_id,
                        organization_id=org.id,
                        attempt_number=1,
                        state="PENDING",
                        effect_id=uuid.uuid4().hex,
                        effect_state="NO_EFFECT",
                        evidence_status="PENDING",
                        created_at=datetime.now(UTC),
                        updated_at=datetime.now(UTC),
                    )
                )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_crash_before_and_after_redis(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        row = await kernel.claim_outbox_row(publisher_id="pub")
        assert row is not None
        await kernel.return_publishing_to_pending(
            outbox_id=row["outbox_id"], reason="crash before redis"
        )
        transport = MemoryTransport()
        ticket = await kernel.publish_outbox(publisher_id="pub", transport=transport)
        assert ticket is not None
        assert len(transport.tickets) == 1
        transport.fail = True
        issued2 = await kernel.issue(**_issue_kwargs(org.id))
        with pytest.raises(AuthorityKernelError, match="Redis"):
            await kernel.publish_outbox(publisher_id="pub", transport=transport)
        async with engine.raw.connect() as conn:
            status = (
                await conn.execute(
                    select(outbox.c.status).where(outbox.c.request_id == issued2.request_id)
                )
            ).scalar_one()
        assert status == "PENDING"
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_uncertain_never_replayed(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        await kernel.claim_external_effect_transmission(
            claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
        )
        with pytest.raises(UncertainExternalEffectError):
            await kernel.mark_external_uncertain(claim, reason="timeout after send")
        with pytest.raises(UncertainExternalEffectError):
            await kernel.replay_uncertain(claim.attempt_id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_cross_tenant_forbidden(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org_a = await _org(engine, "A")
        org_b = await _org(engine, "B")
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org_a.id))
        with pytest.raises(CrossTenantAccessError):
            await kernel.load_request(issued.request_id, organization_id=org_b.id)
        with pytest.raises(CrossTenantAccessError):
            await kernel.issue(**_issue_kwargs(org_a.id, caller_organization_id=org_b.id))
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_deadlock_retry_helper() -> None:
    from sqlalchemy.exc import OperationalError

    class Orig:
        sqlstate = "40P01"

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            err = OperationalError("deadlock", None, Orig())
            raise err
        return "ok"

    assert await retry_pre_effect(flaky) == "ok"
    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_transaction_rollback_does_not_grant_authority(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        try:
            async with engine.raw.begin() as conn:
                await conn.execute(text("SELECT 1"))
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_redis_capacity_is_not_authority(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        cap = AtomicCapacityReservation(InMemoryRedisEval())
        transport = MemoryTransport()
        ticket = await kernel.publish_outbox(
            publisher_id="pub", transport=transport, capacity_reserve=cap
        )
        assert ticket is not None

        # Losing Redis accounting must not create a second physical effect path.
        class DeadRedis:
            def eval(self, *a, **k):
                raise ConnectionError("redis gone")

        await kernel.issue(**_issue_kwargs(org.id))
        with pytest.raises(AuthorityKernelError):
            await kernel.publish_outbox(
                publisher_id="pub",
                transport=transport,
                capacity_reserve=AtomicCapacityReservation(DeadRedis()),
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_lease_reacquisition_advances_generation(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        first = await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        second = await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w2", organization_id=org.id
        )
        assert second["lease_generation"] == first["lease_generation"] + 1
        assert second["lease_id"] != first["lease_id"]
    finally:
        await engine.close()
