# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail-closed branch coverage for Phase 7A authority kernel (real PostgreSQL)."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from responsibleai.db.engine import create_engine
from responsibleai.db.engine import governance_execution_authorizations as auths
from responsibleai.db.engine import runtime_execution_attempts as attempts
from responsibleai.db.engine import runtime_execution_dispatch_outbox as outbox
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.rbac.models import GovernanceStatus, Plan
from responsibleai.runtime.authority_kernel import (
    AUTH_TTL,
    Phase7AAuthorityKernel,
    QueueTicket,
    retry_pre_effect,
)
from responsibleai.runtime.capacity_reservation import AtomicCapacityReservation, InMemoryRedisEval
from responsibleai.runtime.errors import (
    AuthorityKernelError,
    AuthorizationIneligibleError,
    CrossTenantAccessError,
    DuplicateEffectClaimError,
    IdempotencyConflictError,
    PreEffectCasRejected,
    StaleWorkerError,
    UncertainExternalEffectError,
)
from responsibleai.runtime.models import (
    AttemptState,
    AuthorizationStatus,
    EffectState,
    OutboxStatus,
)
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_kern_branch"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        yield url


async def _org(engine, name: str = "BR"):
    repo = OrgRepository(engine)
    return await repo.create_org(name, f"br-{uuid.uuid4().hex[:10]}", plan=Plan.ENTERPRISE)


def _issue_kwargs(org_id: str, digest: str = "d" * 64, key: str | None = None, **extra):
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


async def _ready_claim(kernel, org_id, worker: str = "worker-a"):
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
    def enqueue(self, ticket: QueueTicket) -> None:
        _ = ticket


class LimitedCapacity(AtomicCapacityReservation):
    def reserve(self, **kwargs):
        kwargs["tenant_limit"] = 1
        return super().reserve(**kwargs)


@pytest.mark.asyncio
async def test_issue_rejects_inactive_organization(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await OrgRepository(engine).set_governance_status(org.id, GovernanceStatus.SUSPENDED)
        with pytest.raises(AuthorityKernelError, match="ACTIVE"):
            await kernel.issue(**_issue_kwargs(org.id))
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_issue_idempotency_reuse_marks_reused(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        key = "reuse-key"
        digest = "e" * 64
        first = await kernel.issue(**_issue_kwargs(org.id, digest=digest, key=key))
        second = await kernel.issue(**_issue_kwargs(org.id, digest=digest, key=key))
        assert first.request_id == second.request_id
        assert second.reused is True
        assert first.reused is False
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_issue_idempotency_digest_conflict(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        key = "conflict-key"
        await kernel.issue(**_issue_kwargs(org.id, digest="f" * 64, key=key))
        with pytest.raises(IdempotencyConflictError):
            await kernel.issue(**_issue_kwargs(org.id, digest="0" * 64, key=key))
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_load_request_unknown_and_cross_tenant(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org_a = await _org(engine, "A")
        org_b = await _org(engine, "B")
        kernel = Phase7AAuthorityKernel(engine)
        with pytest.raises(AuthorityKernelError, match="Unknown request"):
            await kernel.load_request(uuid.uuid4().hex, organization_id=org_a.id)
        issued = await kernel.issue(**_issue_kwargs(org_a.id))
        with pytest.raises(CrossTenantAccessError):
            await kernel.load_request(issued.request_id, organization_id=org_b.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_acquire_lease_cross_tenant_forbidden(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org_a = await _org(engine, "A")
        org_b = await _org(engine, "B")
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org_a.id))
        with pytest.raises(CrossTenantAccessError):
            await kernel.acquire_lease(
                request_id=issued.request_id, worker_id="w1", organization_id=org_b.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_acquire_lease_after_effect_claimed(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        await kernel.claim_local_effect_start(
            claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
        )
        with pytest.raises(AuthorityKernelError, match="Effect already claimed"):
            await kernel.acquire_lease(
                request_id=claim.request_id, worker_id="w2", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_acquire_lease_rejects_terminal_attempt(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        async with engine.raw.begin() as conn:
            att = (
                (
                    await conn.execute(
                        select(attempts).where(attempts.c.request_id == issued.request_id)
                    )
                )
                .mappings()
                .one()
            )
            await conn.execute(
                update(attempts)
                .where(attempts.c.request_id == issued.request_id)
                .values(
                    state=AttemptState.RUNNING.value,
                    worker_id=att["worker_id"],
                    lease_id=att["lease_id"],
                    lease_generation=att["lease_generation"],
                    updated_at=datetime.now(UTC),
                )
            )
        with pytest.raises(AuthorityKernelError, match="not leasable"):
            await kernel.acquire_lease(
                request_id=issued.request_id, worker_id="w1", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_admit_epoch_mismatch_fails_closed(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        async with engine.raw.begin() as conn:
            await bump_epoch_on_connection(conn, org.id)
        with pytest.raises(AuthorizationIneligibleError, match="epoch"):
            await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_admit_expired_authorization_fails_pre(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(auths)
                .where(auths.c.request_id == issued.request_id)
                .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
            )
        with pytest.raises(AuthorizationIneligibleError, match="expired"):
            await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_admit_wrong_worker_stale(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="owner", organization_id=org.id
        )
        with pytest.raises(StaleWorkerError):
            await kernel.admit(
                request_id=issued.request_id, worker_id="intruder", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_admit_double_consume_ineligible(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
        with pytest.raises(AuthorizationIneligibleError):
            await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_claim_backend_start_requires_admitted(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        with pytest.raises(AuthorityKernelError, match="ADMITTED"):
            await kernel.claim_backend_start(
                request_id=issued.request_id, worker_id="w1", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_final_cas_rejects_unconsumed_authorization(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(auths)
                .where(auths.c.request_id == issued.request_id)
                .values(status=AuthorizationStatus.ISSUED.value, consumed_at=None)
            )
        with pytest.raises(PreEffectCasRejected, match="eligible"):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_final_cas_invalid_backend_token(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        bad = replace(claim, backend_start_token="not-the-real-token")
        with pytest.raises(PreEffectCasRejected, match="token"):
            await kernel.claim_local_effect_start(
                bad, action_digest=bad.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_final_cas_effect_id_mismatch(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        bad = replace(claim, effect_id=uuid.uuid4().hex)
        with pytest.raises(PreEffectCasRejected, match="effect_id"):
            await kernel.claim_local_effect_start(
                bad, action_digest=bad.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_final_cas_stale_fence_generation_mismatch(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id, worker="w1")
        stale = replace(claim, lease_generation=claim.lease_generation - 1)
        with pytest.raises(PreEffectCasRejected, match="generation"):
            await kernel.claim_local_effect_start(
                stale, action_digest=stale.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_duplicate_local_effect_claim_cas_lost(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(attempts)
                .where(attempts.c.attempt_id == claim.attempt_id)
                .values(
                    state=AttemptState.BACKEND_STARTING.value,
                    effect_state=EffectState.EFFECT_STARTING.value,
                )
            )
        with pytest.raises(DuplicateEffectClaimError, match="already claimed"):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_mark_external_uncertain_idempotent_second_call(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        await kernel.claim_external_effect_transmission(
            claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
        )
        with pytest.raises(UncertainExternalEffectError):
            await kernel.mark_external_uncertain(claim, reason="timeout")
        await kernel.mark_external_uncertain(claim, reason="timeout again")
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_mark_external_uncertain_rejects_local_effect_state(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        _, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(attempts)
                .where(attempts.c.attempt_id == claim.attempt_id)
                .values(
                    state=AttemptState.RUNNING.value,
                    effect_state=EffectState.NO_EFFECT.value,
                )
            )
        with pytest.raises(AuthorityKernelError, match="Cannot mark UNCERTAIN"):
            await kernel.mark_external_uncertain(claim, reason="wrong path")
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_replay_uncertain_only_for_uncertain_state(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        att = await engine.raw.connect()
        try:
            conn = att
            row = (
                await conn.execute(
                    select(attempts.c.attempt_id).where(attempts.c.request_id == issued.request_id)
                )
            ).scalar_one()
        finally:
            await att.close()
        with pytest.raises(AuthorityKernelError, match="not UNCERTAIN"):
            await kernel.replay_uncertain(row)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_publish_outbox_capacity_exhausted_fail_closed(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        redis = InMemoryRedisEval()
        cap = LimitedCapacity(redis)
        cap.reserve(
            execution_id="prefill",
            organization_id=org.id,
            ttl_seconds=120,
            tenant_limit=1,
        )
        with pytest.raises(AuthorityKernelError, match="capacity"):
            await kernel.publish_outbox(
                publisher_id="pub",
                transport=MemoryTransport(),
                capacity_reserve=cap,
            )
        async with engine.raw.connect() as conn:
            status = (
                await conn.execute(
                    select(outbox.c.status).where(outbox.c.organization_id == org.id)
                )
            ).scalar_one()
        assert status == OutboxStatus.PENDING.value
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_mark_outbox_published_cas_lost(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        row = await kernel.claim_outbox_row(publisher_id="pub")
        assert row is not None
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(outbox)
                .where(outbox.c.outbox_id == row["outbox_id"])
                .values(status=OutboxStatus.PUBLISHED.value)
            )
        with pytest.raises(AuthorityKernelError, match="PUBLISHED CAS"):
            await kernel.mark_outbox_published(
                outbox_id=row["outbox_id"], queue_ticket_id=uuid.uuid4().hex
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_claim_outbox_row_none_when_no_pending(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        kernel = Phase7AAuthorityKernel(engine)
        assert await kernel.claim_outbox_row(publisher_id="pub") is None
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_final_cas_auth_expired_at_effect_boundary(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued, claim = await _ready_claim(kernel, org.id)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(auths)
                .where(auths.c.request_id == issued.request_id)
                .values(expires_at=datetime.now(UTC) - AUTH_TTL)
            )
        with pytest.raises(PreEffectCasRejected, match="expired"):
            await kernel.claim_local_effect_start(
                claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_retry_pre_effect_raises_non_deadlock_immediately() -> None:
    from sqlalchemy.exc import OperationalError

    class Orig:
        sqlstate = "08006"

    async def broken():
        raise OperationalError("connection lost", None, Orig())

    with pytest.raises(OperationalError):
        await retry_pre_effect(broken, retries=3)
