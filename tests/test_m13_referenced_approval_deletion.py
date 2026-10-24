# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PostgreSQL tenant deletion when immutable execution requests reference approvals.

The failure mode is a restrictive foreign key: deleting governance_approvals
while runtime_execution_requests.approval_id still points at them aborts the
erasure transaction. These tests keep that foreign key and the immutable
request rows, and check revocation, isolation, restart, and tombstones.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select, text
from sqlalchemy.exc import DBAPIError

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreReadinessGate,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionError,
    TenantDeletionOrchestrator,
)
from responsibleai.data_governance.legal_hold import LegalHoldActiveError, LegalHoldManager
from responsibleai.db.engine import (
    governance_approval_votes,
    governance_approvals,
    governance_execution_authorizations,
    organizations,
    runtime_execution_attempts,
    runtime_execution_dispatch_outbox,
    runtime_execution_requests,
    runtime_worker_leases,
    tenant_tombstones,
)
from responsibleai.runtime.authority_kernel import Phase7AAuthorityKernel
from responsibleai.runtime.errors import AuthorityKernelError
from tests.test_stage3_controller_postgres import isolated_controller_context


class _CrashBeforeErasure(TenantDeletionOrchestrator):
    def __init__(self, engine, provider) -> None:
        super().__init__(engine, provider)
        self.crashes_remaining = 1

    async def _erase_operational_rows(self, org_id: str, purged_counts: dict[str, int]) -> None:
        if self.crashes_remaining:
            self.crashes_remaining -= 1
            raise TenantDeletionError("simulated crash before operational erasure")
        await super()._erase_operational_rows(org_id, purged_counts)


@pytest.fixture
async def deletion_ready(tmp_path, monkeypatch):
    async with isolated_controller_context(tmp_path, monkeypatch, "wp_m13_approval_del") as value:
        service, _identity, _user, token, csrf = value
        previous = get_restore_readiness_gate()
        set_restore_readiness_gate(
            RestoreReadinessGate(provider=service.provider, db_engine=service.engine)
        )
        try:
            yield service, token, csrf
        finally:
            set_restore_readiness_gate(previous)


async def _provision(service, token, csrf, slug: str) -> tuple[str, str]:
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id=f"del-{slug}",
        name=f"Tenant {slug}",
        slug=slug,
    )
    established = service.provider.get_state(tenant)
    assert established is not None
    assert established.state == LifecycleState.ACTIVE
    return tenant, established.generation_id


async def _seed_execution(conn, org_id: str, prefix: str, *, referenced: bool) -> dict[str, str]:
    now = datetime.now(UTC)
    approval_id = f"{prefix}-approval"
    request_id = f"{prefix}-request"
    await conn.execute(
        insert(governance_approvals).values(
            id=approval_id,
            org_id=org_id,
            action_id=f"{prefix}-action",
            action_type="test",
            target="harmless",
            action_digest="ab" * 32,
            reason_codes="[]",
            status="APPROVED",
            requested_at=now.isoformat(),
            resolved_by="approver",
            resolved_at=now.isoformat(),
        )
    )
    await conn.execute(
        insert(governance_approval_votes).values(
            id=f"{prefix}-vote",
            approval_id=approval_id,
            resolver_identity_id=f"{prefix}-resolver",
            outcome="APPROVED",
            resolved_at=now.isoformat(),
        )
    )
    if not referenced:
        return {"approval_id": approval_id, "vote_id": f"{prefix}-vote"}

    await conn.execute(
        insert(runtime_execution_requests).values(
            request_id=request_id,
            organization_id=org_id,
            principal_id=f"{prefix}-principal",
            agent_id=f"{prefix}-agent",
            identity_id=f"{prefix}-identity",
            intent="test",
            action_type="test",
            target="harmless",
            action_digest="cd" * 32,
            canonical_action_payload="{}",
            approved_arguments={},
            observed_governance_epoch=1,
            idempotency_key=request_id,
            approval_id=approval_id,
            lifecycle="RECORDED",
            created_at=now,
        )
    )
    authorization_id = f"{prefix}-auth"
    attempt_id = f"{prefix}-attempt"
    lease_id = f"{prefix}-lease"
    await conn.execute(
        insert(governance_execution_authorizations).values(
            authorization_id=authorization_id,
            organization_id=org_id,
            principal_id=f"{prefix}-principal",
            agent_id=f"{prefix}-agent",
            request_id=request_id,
            action_digest="cd" * 32,
            issuer_epoch=1,
            expires_at=now + timedelta(hours=1),
            oneshot_authority_id=f"{prefix}-oneshot",
            approval_id=approval_id,
            status="ISSUED",
            issued_at=now,
        )
    )
    await conn.execute(
        insert(runtime_execution_attempts).values(
            attempt_id=attempt_id,
            request_id=request_id,
            authorization_id=authorization_id,
            organization_id=org_id,
            attempt_number=1,
            worker_id=f"{prefix}-worker",
            lease_id=lease_id,
            lease_generation=1,
            state="LEASED",
            effect_id=f"{prefix}-effect",
            effect_state="NO_EFFECT",
            evidence_status="PENDING",
            created_at=now,
            updated_at=now,
        )
    )
    await conn.execute(
        insert(runtime_worker_leases).values(
            lease_id=lease_id,
            request_id=request_id,
            attempt_id=attempt_id,
            organization_id=org_id,
            worker_id=f"{prefix}-worker",
            lease_generation=1,
            status="ACTIVE",
            acquired_at=now,
            heartbeat_at=now,
            expires_at=now + timedelta(hours=1),
        )
    )
    await conn.execute(
        insert(runtime_execution_dispatch_outbox).values(
            outbox_id=f"{prefix}-outbox",
            request_id=request_id,
            attempt_id=attempt_id,
            organization_id=org_id,
            status="PENDING",
            attempt_count=0,
            created_at=now,
            updated_at=now,
        )
    )
    return {
        "approval_id": approval_id,
        "vote_id": f"{prefix}-vote",
        "request_id": request_id,
        "authorization_id": authorization_id,
        "attempt_id": attempt_id,
        "lease_id": lease_id,
    }


async def _request_row(conn, request_id: str) -> dict:
    row = (
        (
            await conn.execute(
                select(runtime_execution_requests).where(
                    runtime_execution_requests.c.request_id == request_id
                )
            )
        )
        .mappings()
        .one()
    )
    return dict(row)


@pytest.mark.asyncio
async def test_referenced_approval_deletion_preserves_requests_and_isolates_tenants(
    deletion_ready,
):
    service, token, csrf = deletion_ready
    engine = service.engine
    victim, victim_generation = await _provision(
        service, token, csrf, f"victim-{uuid.uuid4().hex[:8]}"
    )
    other, _other_generation = await _provision(
        service, token, csrf, f"other-{uuid.uuid4().hex[:8]}"
    )

    async with engine.raw.begin() as conn:
        victim_ref = await _seed_execution(conn, victim, "victim-ref", referenced=True)
        victim_free = await _seed_execution(conn, victim, "victim-free", referenced=False)
        other_ref = await _seed_execution(conn, other, "other-ref", referenced=True)
        before_request = await _request_row(conn, victim_ref["request_id"])

    orchestrator = TenantDeletionOrchestrator(engine, lifecycle_provider=service.provider)
    result = await orchestrator.delete_tenant(victim, "deleter-1", "customer erasure")

    assert result.verification_passed is True
    assert result.generation_id == victim_generation
    assert result.purged_tables["governance_approvals"] == 1
    assert result.purged_tables["governance_approvals_revoked"] == 1
    assert service.provider.get_state(victim).state == LifecycleState.TOMBSTONED
    assert service.provider.get_state(victim).generation_id == victim_generation
    assert service.provider.get_state(other).state == LifecycleState.ACTIVE

    async with engine.raw.connect() as conn:
        victim_approval = (
            await conn.execute(
                select(governance_approvals).where(
                    governance_approvals.c.id == victim_ref["approval_id"]
                )
            )
        ).one()
        assert victim_approval.status == "REVOKED"
        assert victim_approval.resolved_by == "deleter-1"
        assert (
            await conn.execute(
                select(governance_approvals.c.id).where(
                    governance_approvals.c.id == victim_free["approval_id"]
                )
            )
        ).fetchone() is None
        assert (
            await conn.execute(
                select(governance_approval_votes.c.id).where(
                    governance_approval_votes.c.id == victim_free["vote_id"]
                )
            )
        ).fetchone() is None
        assert (
            await conn.execute(
                select(governance_approval_votes.c.id).where(
                    governance_approval_votes.c.id == victim_ref["vote_id"]
                )
            )
        ).fetchone() is not None
        assert await _request_row(conn, victim_ref["request_id"]) == before_request
        auth = (
            await conn.execute(
                select(governance_execution_authorizations).where(
                    governance_execution_authorizations.c.authorization_id
                    == victim_ref["authorization_id"]
                )
            )
        ).one()
        assert auth.status == "CONSUMED"
        attempt = (
            await conn.execute(
                select(runtime_execution_attempts).where(
                    runtime_execution_attempts.c.attempt_id == victim_ref["attempt_id"]
                )
            )
        ).one()
        assert attempt.state == "FAILED_PRE_EXECUTION"
        lease = (
            await conn.execute(
                select(runtime_worker_leases).where(
                    runtime_worker_leases.c.lease_id == victim_ref["lease_id"]
                )
            )
        ).one()
        assert lease.status == "REVOKED"
        outbox = (
            await conn.execute(
                select(runtime_execution_dispatch_outbox.c.status).where(
                    runtime_execution_dispatch_outbox.c.outbox_id == "victim-ref-outbox"
                )
            )
        ).scalar_one()
        assert outbox == "CANCELLED"
        assert (
            await conn.execute(
                select(organizations.c.governance_status).where(organizations.c.id == victim)
            )
        ).scalar_one() == "DISABLED"
        other_approval = (
            await conn.execute(
                select(governance_approvals.c.status).where(
                    governance_approvals.c.id == other_ref["approval_id"]
                )
            )
        ).scalar_one()
        assert other_approval == "APPROVED"
        assert await _request_row(conn, other_ref["request_id"])
        assert (
            await conn.execute(
                select(organizations.c.governance_status).where(organizations.c.id == other)
            )
        ).scalar_one() == "ACTIVE"
        other_auth = (
            await conn.execute(
                select(governance_execution_authorizations.c.status).where(
                    governance_execution_authorizations.c.authorization_id
                    == other_ref["authorization_id"]
                )
            )
        ).scalar_one()
        assert other_auth == "ISSUED"
        fk = (
            await conn.execute(
                text(
                    """
                    SELECT pg_get_constraintdef(con.oid)
                    FROM pg_constraint con
                    JOIN pg_class rel ON rel.oid = con.conrelid
                    JOIN pg_attribute att
                      ON att.attrelid = rel.oid AND att.attnum = ANY (con.conkey)
                    WHERE rel.relname = 'runtime_execution_requests'
                      AND att.attname = 'approval_id'
                      AND con.contype = 'f'
                    """
                )
            )
        ).scalar_one()
        assert "ON DELETE RESTRICT" in fk
        tombstone = (
            await conn.execute(
                select(tenant_tombstones).where(tenant_tombstones.c.org_id == victim)
            )
        ).one()
        assert tombstone.generation_id == victim_generation
        assert tombstone.tombstoned_by == "deleter-1"

    async with engine.raw.connect() as conn:
        txn = await conn.begin()
        with pytest.raises(DBAPIError, match="immutable"):
            await conn.execute(
                text("DELETE FROM runtime_execution_requests WHERE request_id = :request_id"),
                {"request_id": victim_ref["request_id"]},
            )
        await txn.rollback()

    with pytest.raises(AuthorityKernelError, match="not ACTIVE"):
        await Phase7AAuthorityKernel(engine).admit(
            request_id=victim_ref["request_id"],
            worker_id="victim-ref-worker",
            organization_id=victim,
        )
    with pytest.raises(TenantDeletionError, match="already tombstoned"):
        await orchestrator.delete_tenant(victim, "deleter-2", "retry after tombstone")

    async with engine.raw.connect() as conn:
        assert (
            await conn.execute(
                select(governance_approvals.c.status).where(
                    governance_approvals.c.id == victim_ref["approval_id"]
                )
            )
        ).scalar_one() == "REVOKED"
        assert (
            await conn.execute(
                select(tenant_tombstones.c.id).where(tenant_tombstones.c.org_id == victim)
            )
        ).fetchall().__len__() == 1
        assert (
            await conn.execute(
                select(organizations.c.governance_status).where(organizations.c.id == victim)
            )
        ).scalar_one() == "DISABLED"


@pytest.mark.asyncio
async def test_interrupted_deletion_retries_without_restoring_authority(deletion_ready):
    service, token, csrf = deletion_ready
    engine = service.engine
    victim, generation = await _provision(service, token, csrf, f"crash-{uuid.uuid4().hex[:8]}")
    async with engine.raw.begin() as conn:
        seeded = await _seed_execution(conn, victim, "crash-ref", referenced=True)
        free = await _seed_execution(conn, victim, "crash-free", referenced=False)

    orchestrator = _CrashBeforeErasure(engine, service.provider)
    with pytest.raises(TenantDeletionError, match="simulated crash"):
        await orchestrator.delete_tenant(victim, "deleter-1", "crash once")

    assert service.provider.get_state(victim).state == LifecycleState.DELETION_IN_PROGRESS
    assert service.provider.get_state(victim).generation_id == generation
    async with engine.raw.connect() as conn:
        approval = (
            await conn.execute(
                select(
                    governance_approvals.c.status,
                    governance_approvals.c.resolved_by,
                ).where(governance_approvals.c.id == seeded["approval_id"])
            )
        ).one()
        assert approval.status == "REVOKED"
        assert approval.resolved_by == "deleter-1"
        assert (
            await conn.execute(
                select(governance_approvals.c.id).where(
                    governance_approvals.c.id == free["approval_id"]
                )
            )
        ).fetchone() is not None
        assert (
            await conn.execute(
                select(organizations.c.governance_status).where(organizations.c.id == victim)
            )
        ).scalar_one() == "DISABLED"
        assert (
            await conn.execute(
                select(tenant_tombstones.c.id).where(tenant_tombstones.c.org_id == victim)
            )
        ).fetchone() is None
        assert (
            await conn.execute(
                select(runtime_execution_requests.c.request_id).where(
                    runtime_execution_requests.c.request_id == seeded["request_id"]
                )
            )
        ).fetchone() is not None
    with pytest.raises(AuthorityKernelError, match="not ACTIVE"):
        await Phase7AAuthorityKernel(engine).admit(
            request_id=seeded["request_id"],
            worker_id="crash-ref-worker",
            organization_id=victim,
        )

    result = await orchestrator.delete_tenant(victim, "deleter-2", "restart")
    assert result.generation_id == generation
    assert result.verification_passed is True
    assert service.provider.get_state(victim).state == LifecycleState.TOMBSTONED
    assert service.provider.get_state(victim).generation_id == generation

    async with engine.raw.connect() as conn:
        approval = (
            await conn.execute(
                select(
                    governance_approvals.c.status,
                    governance_approvals.c.resolved_by,
                ).where(governance_approvals.c.id == seeded["approval_id"])
            )
        ).one()
        assert approval.status == "REVOKED"
        assert approval.resolved_by == "deleter-1"
        assert (
            await conn.execute(
                select(governance_approvals.c.id).where(
                    governance_approvals.c.id == free["approval_id"]
                )
            )
        ).fetchone() is None
        rows = (
            await conn.execute(
                select(tenant_tombstones).where(tenant_tombstones.c.org_id == victim)
            )
        ).fetchall()
        assert len(rows) == 1
        assert rows[0].generation_id == generation
        assert (
            await conn.execute(
                select(organizations.c.governance_status).where(organizations.c.id == victim)
            )
        ).scalar_one() == "DISABLED"


@pytest.mark.asyncio
async def test_legal_hold_still_blocks_before_revocation(deletion_ready):
    service, token, csrf = deletion_ready
    engine = service.engine
    victim, generation = await _provision(service, token, csrf, f"hold-{uuid.uuid4().hex[:8]}")
    async with engine.raw.begin() as conn:
        seeded = await _seed_execution(conn, victim, "hold-ref", referenced=True)
    await LegalHoldManager(engine).create_hold(victim, "ALL", "Court order", "counsel")
    orchestrator = TenantDeletionOrchestrator(engine, lifecycle_provider=service.provider)
    with pytest.raises(LegalHoldActiveError):
        await orchestrator.delete_tenant(victim, "deleter", "blocked")

    assert service.provider.get_state(victim).state == LifecycleState.ACTIVE
    assert service.provider.get_state(victim).generation_id == generation
    async with engine.raw.connect() as conn:
        assert (
            await conn.execute(
                select(governance_approvals.c.status).where(
                    governance_approvals.c.id == seeded["approval_id"]
                )
            )
        ).scalar_one() == "APPROVED"
        assert (
            await conn.execute(
                select(organizations.c.governance_status).where(organizations.c.id == victim)
            )
        ).scalar_one() == "ACTIVE"
