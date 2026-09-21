# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable Phase 7A authority kernel.

PostgreSQL is authority. Redis, QueueTicket, worker lease alone, and
API keys are not. Final pre-effect CAS must succeed immediately before
any irreversible local or external effect.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from sqlalchemy import select, text, update
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.ext.asyncio import AsyncConnection

from responsibleai.db.engine import (
    DatabaseEngine,
    organizations,
)
from responsibleai.db.engine import (
    governance_execution_authorizations as auths,
)
from responsibleai.db.engine import (
    governance_execution_nonces as nonces,
)
from responsibleai.db.engine import (
    runtime_execution_attempts as attempts,
)
from responsibleai.db.engine import (
    runtime_execution_dispatch_outbox as outbox,
)
from responsibleai.db.engine import (
    runtime_execution_fences as fences,
)
from responsibleai.db.engine import (
    runtime_execution_requests as requests,
)
from responsibleai.db.engine import (
    runtime_worker_leases as leases,
)
from responsibleai.db.revocation_epoch_repository import lock_epoch
from responsibleai.rbac.models import GovernanceStatus
from responsibleai.runtime.errors import (
    AuthorityDatabaseError,
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
    LeaseStatus,
    OutboxStatus,
    PreEffectDecision,
    RequestLifecycle,
)

logger = logging.getLogger(__name__)

LEASE_TTL = timedelta(seconds=30)
AUTH_TTL = timedelta(seconds=60)
PUBLISHING_CLAIM_TTL = timedelta(seconds=15)
DEADLOCK_RETRY_LIMIT = 5
DEADLOCK_CODES = frozenset({"40001", "40P01"})


class RedisTransport(Protocol):
    def enqueue(self, ticket: QueueTicket) -> None: ...


@dataclass(frozen=True)
class QueueTicket:
    """Transport-only dequeue handle. Never execution authority."""

    ticket_id: str
    request_id: str
    attempt_id: str
    organization_id: str


@dataclass(frozen=True)
class IssuanceResult:
    request_id: str
    authorization_id: str
    attempt_id: str
    effect_id: str
    oneshot_authority_id: str
    observed_epoch: int
    reused: bool


@dataclass(frozen=True)
class BackendClaim:
    attempt_id: str
    request_id: str
    authorization_id: str
    effect_id: str
    lease_id: str
    lease_generation: int
    worker_id: str
    backend_start_token: str
    action_digest: str
    target_fingerprint: str | None
    organization_id: str


@dataclass(frozen=True)
class LocalEffectPermit:
    attempt_id: str
    effect_id: str
    lease_generation: int


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _is_deadlock(exc: BaseException) -> bool:
    orig = getattr(exc, "orig", None)
    sqlstate = getattr(orig, "sqlstate", None) or getattr(orig, "pgcode", None)
    if sqlstate in DEADLOCK_CODES:
        return True
    text_exc = str(exc).lower()
    return (
        "deadlock" in text_exc
        or "serialization failure" in text_exc
        or "could not serialize" in text_exc
    )


def _require_postgres(conn: AsyncConnection) -> None:
    if conn.dialect.name != "postgresql":
        raise AuthorityDatabaseError(
            "Phase 7A authority kernel requires PostgreSQL. "
            "SQLite cannot enforce SKIP LOCKED fencing or TIMESTAMPTZ CAS."
        )


async def retry_pre_effect(operation, *, retries: int = DEADLOCK_RETRY_LIMIT):
    """Bounded retry for deadlock/serialization. Never call after a physical effect."""
    last: BaseException | None = None
    for attempt in range(retries):
        try:
            return await operation()
        except OperationalError as exc:
            last = exc
            if not _is_deadlock(exc) or attempt == retries - 1:
                raise
            await asyncio.sleep(0.02 * (2**attempt))
    assert last is not None
    raise last


class Phase7AAuthorityKernel:
    """Issuance, lease/fence, outbox, admission, and final CAS."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def issue(
        self,
        *,
        organization_id: str,
        principal_id: str,
        agent_id: str,
        identity_id: str,
        intent: str,
        action_type: str,
        target: str,
        action_digest: str,
        canonical_action_payload: str,
        approved_arguments: dict[str, Any],
        idempotency_key: str,
        target_fingerprint: str | None = None,
        workspace_id: str | None = None,
        approval_id: str | None = None,
        server_id: str | None = None,
        caller_organization_id: str | None = None,
    ) -> IssuanceResult:
        if caller_organization_id and caller_organization_id != organization_id:
            raise CrossTenantAccessError("Cross-tenant issuance is forbidden")

        async def _once() -> IssuanceResult:
            async with self._engine.raw.begin() as conn:
                _require_postgres(conn)
                org = await self._lock_org(conn, organization_id)
                if org != GovernanceStatus.ACTIVE.value:
                    raise AuthorityKernelError("Organization is not ACTIVE")
                epoch = await lock_epoch(conn, organization_id)
                now = _now()
                request_id = _new_id()
                await conn.execute(
                    requests.insert().values(
                        request_id=request_id,
                        organization_id=organization_id,
                        workspace_id=workspace_id,
                        principal_id=principal_id,
                        agent_id=agent_id,
                        identity_id=identity_id,
                        intent=intent,
                        action_type=action_type,
                        target=target,
                        action_digest=action_digest,
                        target_fingerprint=target_fingerprint,
                        canonical_action_payload=canonical_action_payload,
                        approved_arguments=approved_arguments,
                        observed_governance_epoch=epoch,
                        idempotency_key=idempotency_key,
                        approval_id=approval_id,
                        server_id=server_id,
                        lifecycle=RequestLifecycle.RECORDED.value,
                        created_at=now,
                    )
                )
                authorization_id = _new_id()
                oneshot = _new_id()
                attempt_id = _new_id()
                effect_id = _new_id()
                await conn.execute(
                    auths.insert().values(
                        authorization_id=authorization_id,
                        organization_id=organization_id,
                        principal_id=principal_id,
                        agent_id=agent_id,
                        request_id=request_id,
                        action_digest=action_digest,
                        target_fingerprint=target_fingerprint,
                        issuer_epoch=epoch,
                        expires_at=now + AUTH_TTL,
                        oneshot_authority_id=oneshot,
                        approval_id=approval_id,
                        status=AuthorizationStatus.ISSUED.value,
                        issued_at=now,
                    )
                )
                await conn.execute(
                    attempts.insert().values(
                        attempt_id=attempt_id,
                        request_id=request_id,
                        authorization_id=authorization_id,
                        organization_id=organization_id,
                        attempt_number=1,
                        state=AttemptState.PENDING.value,
                        effect_id=effect_id,
                        effect_state=EffectState.NO_EFFECT.value,
                        evidence_status="PENDING",
                        created_at=now,
                        updated_at=now,
                    )
                )
                await conn.execute(
                    fences.insert().values(
                        request_id=request_id,
                        current_generation=0,
                        created_at=now,
                    )
                )
                await conn.execute(
                    outbox.insert().values(
                        outbox_id=_new_id(),
                        request_id=request_id,
                        attempt_id=attempt_id,
                        organization_id=organization_id,
                        status=OutboxStatus.PENDING.value,
                        created_at=now,
                        updated_at=now,
                    )
                )
                return IssuanceResult(
                    request_id=request_id,
                    authorization_id=authorization_id,
                    attempt_id=attempt_id,
                    effect_id=effect_id,
                    oneshot_authority_id=oneshot,
                    observed_epoch=epoch,
                    reused=False,
                )

        try:
            return await retry_pre_effect(_once)
        except IntegrityError as exc:
            return await self._existing_issuance(
                organization_id=organization_id,
                idempotency_key=idempotency_key,
                action_digest=action_digest,
                cause=exc,
            )

    async def acquire_lease(
        self, *, request_id: str, worker_id: str, organization_id: str
    ) -> dict[str, Any]:
        async def _once() -> dict[str, Any]:
            async with self._engine.raw.begin() as conn:
                _require_postgres(conn)
                now = _now()
                org = await self._lock_org(conn, organization_id)
                if org != GovernanceStatus.ACTIVE.value:
                    raise AuthorityKernelError("Organization is not ACTIVE")
                await lock_epoch(conn, organization_id)
                req = await self._lock_request(conn, request_id)
                self._assert_tenant(req["organization_id"], organization_id)
                att = await self._lock_attempt_by_request(conn, request_id)
                if att["effect_state"] != EffectState.NO_EFFECT.value:
                    raise AuthorityKernelError("Effect already claimed; cannot reacquire lease")
                if att["state"] in {
                    AttemptState.COMPLETED.value,
                    AttemptState.FAILED.value,
                    AttemptState.FAILED_PRE_EXECUTION.value,
                    AttemptState.UNCERTAIN.value,
                    AttemptState.RUNNING.value,
                }:
                    raise AuthorityKernelError("Attempt is not leasable")
                await conn.execute(
                    select(leases).where(leases.c.request_id == request_id).with_for_update()
                )
                await conn.execute(
                    update(leases)
                    .where(
                        leases.c.request_id == request_id,
                        leases.c.status == LeaseStatus.ACTIVE.value,
                    )
                    .values(status=LeaseStatus.EXPIRED.value, released_at=now)
                )
                gen = (
                    await conn.execute(
                        update(fences)
                        .where(fences.c.request_id == request_id)
                        .values(current_generation=fences.c.current_generation + 1)
                        .returning(fences.c.current_generation)
                    )
                ).scalar_one()
                lease_id = _new_id()
                await conn.execute(
                    leases.insert().values(
                        lease_id=lease_id,
                        request_id=request_id,
                        attempt_id=att["attempt_id"],
                        organization_id=organization_id,
                        worker_id=worker_id,
                        lease_generation=int(gen),
                        status=LeaseStatus.ACTIVE.value,
                        acquired_at=now,
                        heartbeat_at=now,
                        expires_at=now + LEASE_TTL,
                    )
                )
                next_state = (
                    AttemptState.LEASED.value
                    if att["state"] in {AttemptState.PENDING.value, AttemptState.LEASED.value}
                    else AttemptState.ADMITTED.value
                )
                await conn.execute(
                    update(attempts)
                    .where(attempts.c.attempt_id == att["attempt_id"])
                    .values(
                        state=next_state,
                        worker_id=worker_id,
                        lease_id=lease_id,
                        lease_generation=int(gen),
                        backend_start_token_hash=None,
                        updated_at=now,
                    )
                )
                return {
                    "lease_id": lease_id,
                    "lease_generation": int(gen),
                    "attempt_id": att["attempt_id"],
                    "worker_id": worker_id,
                }

        return await retry_pre_effect(_once)

    async def admit(self, *, request_id: str, worker_id: str, organization_id: str) -> None:
        async def _once() -> None:
            async with self._engine.raw.begin() as conn:
                _require_postgres(conn)
                now = _now()
                org = await self._lock_org(conn, organization_id)
                if org != GovernanceStatus.ACTIVE.value:
                    raise AuthorityKernelError("Organization is not ACTIVE")
                epoch = await lock_epoch(conn, organization_id)
                req = await self._lock_request(conn, request_id)
                self._assert_tenant(req["organization_id"], organization_id)
                auth = await self._lock_auth_by_request(conn, request_id)
                att = await self._lock_attempt_by_request(conn, request_id)
                lease = await self._lock_active_lease(conn, request_id)
                self._assert_lease_live(lease, worker_id, now)
                if epoch != int(auth["issuer_epoch"]):
                    await self._fail_pre(
                        conn, att, now, "EPOCH_MISMATCH", "Governance epoch mismatch at admission"
                    )
                    raise AuthorizationIneligibleError("Authorization epoch mismatch")
                if auth["status"] != AuthorizationStatus.ISSUED.value:
                    raise AuthorizationIneligibleError("Authorization is not ISSUED")
                if now >= auth["expires_at"]:
                    await self._fail_pre(conn, att, now, "AUTH_EXPIRED", "Authorization expired")
                    raise AuthorizationIneligibleError("Authorization expired")
                if att["state"] != AttemptState.LEASED.value:
                    raise AuthorityKernelError("Attempt is not LEASED")
                consumed = await conn.execute(
                    update(auths)
                    .where(
                        auths.c.authorization_id == auth["authorization_id"],
                        auths.c.status == AuthorizationStatus.ISSUED.value,
                    )
                    .values(status=AuthorizationStatus.CONSUMED.value, consumed_at=now)
                )
                if consumed.rowcount != 1:
                    raise AuthorizationIneligibleError("Authorization consume lost the race")
                try:
                    await conn.execute(
                        nonces.insert().values(
                            nonce=auth["oneshot_authority_id"],
                            authorization_id=auth["authorization_id"][:36],
                            organization_id=organization_id,
                            consumed_at=now.isoformat(),
                        )
                    )
                except IntegrityError as exc:
                    raise AuthorizationIneligibleError(
                        "Oneshot authority already consumed"
                    ) from exc
                result = await conn.execute(
                    update(attempts)
                    .where(
                        attempts.c.attempt_id == att["attempt_id"],
                        attempts.c.state == AttemptState.LEASED.value,
                    )
                    .values(state=AttemptState.ADMITTED.value, admitted_at=now, updated_at=now)
                )
                if result.rowcount != 1:
                    raise AuthorityKernelError("Admission CAS lost")

        return await retry_pre_effect(_once)

    async def claim_backend_start(
        self, *, request_id: str, worker_id: str, organization_id: str
    ) -> BackendClaim:
        async def _once() -> BackendClaim:
            async with self._engine.raw.begin() as conn:
                _require_postgres(conn)
                now = _now()
                org = await self._lock_org(conn, organization_id)
                if org != GovernanceStatus.ACTIVE.value:
                    raise AuthorityKernelError("Organization is not ACTIVE")
                epoch = await lock_epoch(conn, organization_id)
                req = await self._lock_request(conn, request_id)
                self._assert_tenant(req["organization_id"], organization_id)
                auth = await self._lock_auth_by_request(conn, request_id)
                att = await self._lock_attempt_by_request(conn, request_id)
                lease = await self._lock_active_lease(conn, request_id)
                self._assert_lease_live(lease, worker_id, now)
                if epoch != int(auth["issuer_epoch"]):
                    await self._fail_pre(
                        conn, att, now, "EPOCH_MISMATCH", "Epoch mismatch at backend start"
                    )
                    raise AuthorizationIneligibleError("Authorization epoch mismatch")
                if att["state"] != AttemptState.ADMITTED.value:
                    raise AuthorityKernelError("Attempt is not ADMITTED")
                raw_token = secrets.token_hex(32)
                token_hash = _hash_token(raw_token)
                result = await conn.execute(
                    update(attempts)
                    .where(
                        attempts.c.attempt_id == att["attempt_id"],
                        attempts.c.state == AttemptState.ADMITTED.value,
                    )
                    .values(
                        state=AttemptState.BACKEND_STARTING.value,
                        backend_start_token_hash=token_hash,
                        backend_started_at=now,
                        updated_at=now,
                    )
                )
                if result.rowcount != 1:
                    raise AuthorityKernelError("Backend-start CAS lost")
                return BackendClaim(
                    attempt_id=att["attempt_id"],
                    request_id=request_id,
                    authorization_id=auth["authorization_id"],
                    effect_id=att["effect_id"],
                    lease_id=lease["lease_id"],
                    lease_generation=int(lease["lease_generation"]),
                    worker_id=worker_id,
                    backend_start_token=raw_token,
                    action_digest=req["action_digest"],
                    target_fingerprint=req["target_fingerprint"],
                    organization_id=organization_id,
                )

        return await retry_pre_effect(_once)

    async def claim_local_effect_start(
        self,
        claim: BackendClaim,
        *,
        action_digest: str,
        target_fingerprint: str | None = None,
    ) -> LocalEffectPermit:
        return await self._final_cas(
            claim,
            action_digest=action_digest,
            target_fingerprint=target_fingerprint,
            transmitting=False,
        )

    async def claim_external_effect_transmission(
        self,
        claim: BackendClaim,
        *,
        action_digest: str,
        target_fingerprint: str | None,
    ) -> LocalEffectPermit:
        if target_fingerprint != claim.target_fingerprint:
            await self._terminalize_pre_effect(
                claim, "TARGET_FINGERPRINT_MISMATCH", "Target fingerprint mismatch"
            )
            raise PreEffectCasRejected("Target fingerprint mismatch")
        return await self._final_cas(
            claim,
            action_digest=action_digest,
            target_fingerprint=target_fingerprint,
            transmitting=True,
        )

    async def mark_external_uncertain(self, claim: BackendClaim, *, reason: str) -> None:
        """Sent but outcome unknown. Never automatically replay."""
        async with self._engine.raw.begin() as conn:
            _require_postgres(conn)
            now = _now()
            await self._lock_org(conn, claim.organization_id)
            await lock_epoch(conn, claim.organization_id)
            await self._lock_request(conn, claim.request_id)
            await self._lock_auth_by_request(conn, claim.request_id)
            att = await self._lock_attempt(conn, claim.attempt_id)
            if att["state"] == AttemptState.UNCERTAIN.value:
                return
            if att["effect_state"] not in {
                EffectState.EFFECT_TRANSMITTING.value,
                EffectState.EFFECT_STARTING.value,
            }:
                raise AuthorityKernelError("Cannot mark UNCERTAIN from this effect state")
            await conn.execute(
                update(attempts)
                .where(attempts.c.attempt_id == claim.attempt_id)
                .values(
                    state=AttemptState.UNCERTAIN.value,
                    effect_state=EffectState.EFFECT_UNCERTAIN.value,
                    reconciliation_state="REQUIRES_RECONCILIATION",
                    failure_code="EXTERNAL_TIMEOUT",
                    failure_reason=reason[:500],
                    completed_at=now,
                    updated_at=now,
                )
            )
        raise UncertainExternalEffectError(
            "External effect outcome is UNCERTAIN. Automatic replay is forbidden. "
            "effect_id is correlation identity, not an upstream idempotency key."
        )

    async def replay_uncertain(self, attempt_id: str) -> None:
        async with self._engine.raw.connect() as conn:
            att = (
                (await conn.execute(select(attempts).where(attempts.c.attempt_id == attempt_id)))
                .mappings()
                .one()
            )
        if att["state"] == AttemptState.UNCERTAIN.value:
            raise UncertainExternalEffectError(
                "UNCERTAIN attempts must not be automatically replayed"
            )
        raise AuthorityKernelError("Attempt is not UNCERTAIN")

    async def claim_outbox_row(self, *, publisher_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.begin() as conn:
            _require_postgres(conn)
            now = _now()
            await conn.execute(
                update(outbox)
                .where(
                    outbox.c.status == OutboxStatus.PUBLISHING.value,
                    outbox.c.claimed_at < now - PUBLISHING_CLAIM_TTL,
                )
                .values(
                    status=OutboxStatus.PENDING.value,
                    publisher_id=None,
                    claimed_at=None,
                    updated_at=now,
                    last_error="stale PUBLISHING returned to PENDING after crash-before-Redis window",
                )
            )
            row = (
                (
                    await conn.execute(
                        text(
                            """
                        SELECT outbox_id, request_id, attempt_id, organization_id
                        FROM runtime_execution_dispatch_outbox
                        WHERE status = 'PENDING'
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if row is None:
                return None
            await conn.execute(
                update(outbox)
                .where(
                    outbox.c.outbox_id == row["outbox_id"],
                    outbox.c.status == OutboxStatus.PENDING.value,
                )
                .values(
                    status=OutboxStatus.PUBLISHING.value,
                    publisher_id=publisher_id,
                    claimed_at=now,
                    updated_at=now,
                    attempt_count=outbox.c.attempt_count + 1,
                )
            )
            return dict(row)

    async def mark_outbox_published(self, *, outbox_id: str, queue_ticket_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            _require_postgres(conn)
            now = _now()
            result = await conn.execute(
                update(outbox)
                .where(
                    outbox.c.outbox_id == outbox_id,
                    outbox.c.status == OutboxStatus.PUBLISHING.value,
                )
                .values(
                    status=OutboxStatus.PUBLISHED.value,
                    published_at=now,
                    queue_ticket_id=queue_ticket_id,
                    updated_at=now,
                )
            )
            if result.rowcount != 1:
                raise AuthorityKernelError("Outbox PUBLISHED CAS lost")

    async def return_publishing_to_pending(self, *, outbox_id: str, reason: str) -> None:
        async with self._engine.raw.begin() as conn:
            _require_postgres(conn)
            now = _now()
            await conn.execute(
                update(outbox)
                .where(
                    outbox.c.outbox_id == outbox_id,
                    outbox.c.status == OutboxStatus.PUBLISHING.value,
                )
                .values(
                    status=OutboxStatus.PENDING.value,
                    publisher_id=None,
                    claimed_at=None,
                    updated_at=now,
                    last_error=reason[:500],
                )
            )

    async def publish_outbox(
        self,
        *,
        publisher_id: str,
        transport: RedisTransport,
        capacity_reserve=None,
    ) -> QueueTicket | None:
        """Claim PENDING, optionally reserve capacity, enqueue, then PUBLISHED.

        Crash before Redis: PUBLISHING returns to PENDING.
        Crash after Redis before PUBLISHED: duplicate QueueTicket is allowed;
        duplicate physical effect is not.
        Redis failure does not grant authority.
        """
        row = await self.claim_outbox_row(publisher_id=publisher_id)
        if row is None:
            return None
        ticket = QueueTicket(
            ticket_id=_new_id(),
            request_id=row["request_id"],
            attempt_id=row["attempt_id"],
            organization_id=row["organization_id"],
        )
        if capacity_reserve is not None:
            try:
                reserved = capacity_reserve.reserve(
                    execution_id=row["attempt_id"],
                    organization_id=row["organization_id"],
                    ttl_seconds=int(LEASE_TTL.total_seconds()) + 30,
                )
            except Exception as exc:
                await self.return_publishing_to_pending(
                    outbox_id=row["outbox_id"],
                    reason=f"capacity reserve failed: {type(exc).__name__}",
                )
                raise AuthorityKernelError(
                    "Redis capacity reservation unavailable; fail closed"
                ) from exc
            if not reserved.ok:
                await self.return_publishing_to_pending(
                    outbox_id=row["outbox_id"], reason="tenant capacity exhausted"
                )
                raise AuthorityKernelError("Tenant capacity exhausted")
        try:
            transport.enqueue(ticket)
        except Exception as exc:
            await self.return_publishing_to_pending(
                outbox_id=row["outbox_id"], reason=f"redis enqueue failed: {type(exc).__name__}"
            )
            raise AuthorityKernelError("Redis transport unavailable; fail closed") from exc
        try:
            await self.mark_outbox_published(
                outbox_id=row["outbox_id"], queue_ticket_id=ticket.ticket_id
            )
        except Exception:
            # Duplicate QueueTicket is possible. DB CAS remains uniqueness.
            logger.warning(
                "outbox published to Redis before durable PUBLISHED; duplicate tickets must not duplicate effects"
            )
            raise
        return ticket

    async def _existing_issuance(
        self,
        *,
        organization_id: str,
        idempotency_key: str,
        action_digest: str,
        cause: IntegrityError,
    ) -> IssuanceResult:
        async with self._engine.raw.connect() as conn:
            existing = (
                (
                    await conn.execute(
                        select(requests).where(
                            requests.c.organization_id == organization_id,
                            requests.c.idempotency_key == idempotency_key,
                        )
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is None:
                raise cause
            if existing["action_digest"] != action_digest:
                raise IdempotencyConflictError(
                    "Idempotency key reused with a different action digest"
                ) from cause
            auth_row = (
                (
                    await conn.execute(
                        select(auths).where(auths.c.request_id == existing["request_id"])
                    )
                )
                .mappings()
                .one()
            )
            att = (
                (
                    await conn.execute(
                        select(attempts).where(attempts.c.request_id == existing["request_id"])
                    )
                )
                .mappings()
                .one()
            )
        return IssuanceResult(
            request_id=existing["request_id"],
            authorization_id=auth_row["authorization_id"],
            attempt_id=att["attempt_id"],
            effect_id=att["effect_id"],
            oneshot_authority_id=auth_row["oneshot_authority_id"],
            observed_epoch=int(existing["observed_governance_epoch"]),
            reused=True,
        )

    async def load_request(self, request_id: str, *, organization_id: str) -> dict[str, Any]:
        async with self._engine.raw.connect() as conn:
            row = (
                (await conn.execute(select(requests).where(requests.c.request_id == request_id)))
                .mappings()
                .one_or_none()
            )
        if row is None:
            raise AuthorityKernelError("Unknown request")
        if row["organization_id"] != organization_id:
            raise CrossTenantAccessError("Cross-tenant request access is forbidden")
        return dict(row)

    async def _final_cas(
        self,
        claim: BackendClaim,
        *,
        action_digest: str,
        target_fingerprint: str | None,
        transmitting: bool,
    ) -> LocalEffectPermit:
        async def _once() -> LocalEffectPermit:
            async with self._engine.raw.begin() as conn:
                _require_postgres(conn)
                now = _now()
                org = await self._lock_org(conn, claim.organization_id)
                epoch = await lock_epoch(conn, claim.organization_id)
                req = await self._lock_request(conn, claim.request_id)
                auth = await self._lock_auth_by_request(conn, claim.request_id)
                att = await self._lock_attempt(conn, claim.attempt_id)
                lease = await self._lock_active_lease(conn, claim.request_id)
                fence_row = (
                    (
                        await conn.execute(
                            select(fences)
                            .where(fences.c.request_id == claim.request_id)
                            .with_for_update()
                        )
                    )
                    .mappings()
                    .one()
                )

                def reject(code: str, reason: str) -> None:
                    raise _CasFail(code, reason)

                if org != GovernanceStatus.ACTIVE.value:
                    reject("ORG_NOT_ACTIVE", "Organization is not ACTIVE")
                if int(auth["issuer_epoch"]) != int(epoch):
                    reject("EPOCH_MISMATCH", "Governance epoch mismatch at final CAS")
                if auth["status"] != AuthorizationStatus.CONSUMED.value:
                    reject("AUTH_NOT_CONSUMED", "Authorization is not eligible")
                if now >= auth["expires_at"]:
                    reject("AUTH_EXPIRED", "Authorization expired at final CAS")
                if req["action_digest"] != action_digest or auth["action_digest"] != action_digest:
                    reject("ACTION_DIGEST_MISMATCH", "Immutable action digest mismatch")
                if claim.action_digest != action_digest:
                    reject("ACTION_DIGEST_MISMATCH", "Claim action digest mismatch")
                expected_fp = req["target_fingerprint"]
                if expected_fp is not None and expected_fp != target_fingerprint:
                    reject("TARGET_FINGERPRINT_MISMATCH", "Target fingerprint mismatch")
                if att["state"] != AttemptState.BACKEND_STARTING.value:
                    reject("ATTEMPT_STATE", "Attempt is not BACKEND_STARTING")
                if att["effect_state"] != EffectState.NO_EFFECT.value:
                    raise DuplicateEffectClaimError("Effect already claimed")
                if att["effect_id"] != claim.effect_id:
                    reject("EFFECT_ID_MISMATCH", "effect_id mismatch")
                token_hash = _hash_token(claim.backend_start_token)
                if att["backend_start_token_hash"] != token_hash:
                    reject("TOKEN_INVALID", "One-shot backend token is invalid")
                try:
                    self._assert_lease_live(lease, claim.worker_id, now)
                except StaleWorkerError as exc:
                    reject("STALE_WORKER", str(exc))
                if int(lease["lease_generation"]) != int(claim.lease_generation):
                    reject("STALE_FENCE", "Fencing generation mismatch")
                if int(fence_row["current_generation"]) != int(claim.lease_generation):
                    reject("STALE_FENCE", "Fence counter does not match claim generation")
                next_effect = (
                    EffectState.EFFECT_TRANSMITTING.value
                    if transmitting
                    else EffectState.EFFECT_STARTING.value
                )
                result = await conn.execute(
                    update(attempts)
                    .where(
                        attempts.c.attempt_id == claim.attempt_id,
                        attempts.c.state == AttemptState.BACKEND_STARTING.value,
                        attempts.c.effect_state == EffectState.NO_EFFECT.value,
                        attempts.c.backend_start_token_hash == token_hash,
                    )
                    .values(
                        state=AttemptState.RUNNING.value,
                        effect_state=next_effect,
                        backend_start_token_hash=None,
                        pre_effect_decision=PreEffectDecision.ALLOW_EFFECT.value,
                        effect_claimed_at=now,
                        updated_at=now,
                    )
                )
                if result.rowcount != 1:
                    raise DuplicateEffectClaimError("Effect claim CAS lost")
                return LocalEffectPermit(
                    attempt_id=claim.attempt_id,
                    effect_id=claim.effect_id,
                    lease_generation=int(claim.lease_generation),
                )

        try:
            return await retry_pre_effect(_once)
        except _CasFail as fail:
            await self._terminalize_pre_effect(claim, fail.code, fail.reason)
            raise PreEffectCasRejected(fail.reason) from fail

    async def _terminalize_pre_effect(self, claim: BackendClaim, code: str, reason: str) -> None:
        async with self._engine.raw.begin() as conn:
            now = _now()
            await self._lock_org(conn, claim.organization_id)
            await lock_epoch(conn, claim.organization_id)
            await self._lock_request(conn, claim.request_id)
            await self._lock_auth_by_request(conn, claim.request_id)
            att = await self._lock_attempt(conn, claim.attempt_id)
            if att["effect_state"] != EffectState.NO_EFFECT.value:
                return
            if att["state"] in {
                AttemptState.FAILED_PRE_EXECUTION.value,
                AttemptState.UNCERTAIN.value,
                AttemptState.COMPLETED.value,
                AttemptState.FAILED.value,
            }:
                return
            await conn.execute(
                update(attempts)
                .where(
                    attempts.c.attempt_id == claim.attempt_id,
                    attempts.c.effect_state == EffectState.NO_EFFECT.value,
                )
                .values(
                    state=AttemptState.FAILED_PRE_EXECUTION.value,
                    backend_start_token_hash=None,
                    pre_effect_decision=PreEffectDecision.DENY_FAILED_PRE_EXECUTION.value,
                    failure_code=code,
                    failure_reason=reason[:500],
                    completed_at=now,
                    updated_at=now,
                )
            )

    async def _fail_pre(
        self, conn: AsyncConnection, att, now: datetime, code: str, reason: str
    ) -> None:
        values = {
            "state": AttemptState.FAILED_PRE_EXECUTION.value,
            "backend_start_token_hash": None,
            "pre_effect_decision": PreEffectDecision.DENY_FAILED_PRE_EXECUTION.value,
            "failure_code": code,
            "failure_reason": reason[:500],
            "completed_at": now,
            "updated_at": now,
        }
        if att["state"] == AttemptState.PENDING.value:
            values["worker_id"] = None
            values["lease_id"] = None
            values["lease_generation"] = None
        await conn.execute(
            update(attempts).where(attempts.c.attempt_id == att["attempt_id"]).values(**values)
        )

    async def _lock_org(self, conn: AsyncConnection, organization_id: str) -> str:
        stmt = select(organizations.c.governance_status).where(
            organizations.c.id == organization_id
        )
        stmt = stmt.with_for_update()
        status = (await conn.execute(stmt)).scalar_one_or_none()
        if status is None:
            raise AuthorityKernelError("Unknown organization")
        return str(status)

    async def _lock_request(self, conn: AsyncConnection, request_id: str):
        row = (
            (
                await conn.execute(
                    select(requests).where(requests.c.request_id == request_id).with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise AuthorityKernelError("Unknown request")
        return row

    async def _lock_auth_by_request(self, conn: AsyncConnection, request_id: str):
        row = (
            (
                await conn.execute(
                    select(auths).where(auths.c.request_id == request_id).with_for_update()
                )
            )
            .mappings()
            .one()
        )
        return row

    async def _lock_attempt(self, conn: AsyncConnection, attempt_id: str):
        return (
            (
                await conn.execute(
                    select(attempts).where(attempts.c.attempt_id == attempt_id).with_for_update()
                )
            )
            .mappings()
            .one()
        )

    async def _lock_attempt_by_request(self, conn: AsyncConnection, request_id: str):
        return (
            (
                await conn.execute(
                    select(attempts).where(attempts.c.request_id == request_id).with_for_update()
                )
            )
            .mappings()
            .one()
        )

    async def _lock_active_lease(self, conn: AsyncConnection, request_id: str):
        row = (
            (
                await conn.execute(
                    select(leases)
                    .where(
                        leases.c.request_id == request_id,
                        leases.c.status == LeaseStatus.ACTIVE.value,
                    )
                    .with_for_update()
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise StaleWorkerError("No active worker lease")
        return row

    def _assert_lease_live(self, lease, worker_id: str, now: datetime) -> None:
        expires = lease["expires_at"]
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires <= now:
            raise StaleWorkerError("Worker lease expired")
        if lease["worker_id"] != worker_id:
            raise StaleWorkerError("Worker id does not own the active lease")
        if lease["status"] != LeaseStatus.ACTIVE.value:
            raise StaleWorkerError("Lease is not ACTIVE")

    def _assert_tenant(self, row_org: str, caller_org: str) -> None:
        if row_org != caller_org:
            raise CrossTenantAccessError("Cross-tenant execution access is forbidden")


class _CasFail(Exception):  # noqa: N818 — internal CAS control-flow, not a public error type
    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason
