# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL structural restore tests; fixture data is NOT a customer journey."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, text
from tests.test_stage3_controller_postgres import isolated_controller_context

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleState,
    LifecycleStateRecord,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
)
from responsibleai.db.engine import (
    governance_approvals,
    runtime_execution_requests,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.isolation import in_flight as tracking


@pytest.fixture
async def restored(tmp_path, monkeypatch):
    # Only this disposable database's component fixtures belong in its registry.
    # Preserve the outer registry and all pre-existing tracking evidence intact.
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "restore-tracking")
    monkeypatch.setattr(
        tracking.InFlightExecutionRegistry, "_instance", tracking.InFlightExecutionRegistry()
    )
    # Genuine provisioning; the shared component READY baseline is not an
    # offline bootstrap receipt. Structural in-memory attacks below remain
    # distinct from durable Store B / signed R1 recovery qualification.
    async with isolated_controller_context(tmp_path, monkeypatch, "wp_convergence_restore") as (
        service,
        identity,
        user,
        token,
        csrf,
    ):
        tenant = await service.create(
            session_token=token,
            csrf=csrf,
            request_id="fortress-restored-fixture",
            name="Restore test",
            slug="restore-test",
            attach_session=True,
        )
        lifecycle = service.provider.get_state(tenant)
        complete = service.ledger.completion(tenant)
        assert lifecycle.state == LifecycleState.ACTIVE
        assert complete.generation_id == lifecycle.generation_id
        assert (await identity.get_principal(token)).org_id == tenant
        async with service.engine.raw.connect() as conn:
            row = (
                (
                    await conn.execute(
                        text(
                            "SELECT p.generation_id,p.state,p.completion_digest,o.owner_user_id "
                            "FROM tenant_provisioning_records p JOIN organizations o "
                            "ON o.id=p.tenant_id WHERE p.tenant_id=:tenant"
                        ),
                        {"tenant": tenant},
                    )
                )
                .mappings()
                .one()
            )
            assert row["generation_id"] == lifecycle.generation_id
            assert row["completion_digest"] == complete.completion_digest
            assert row["state"] == "COMPLETE"
            assert row["owner_user_id"] == user
        assert (await RevocationEpochRepository(service.engine).current(tenant)).epoch == 1
        yield service.engine, tenant, lifecycle.generation_id


@pytest.mark.asyncio
async def test_store_b_floor_fences_canonical_governance_epoch(restored):
    restored, tenant, generation = restored
    epochs = RevocationEpochRepository(restored)
    await epochs.bump(tenant)
    await epochs.bump(tenant)
    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id=tenant,
            generation_id=generation,
            state=LifecycleState.ACTIVE,
            effective_at=datetime.now(UTC).isoformat(),
            security_epoch=7,
            revocation_floor=7,
        )
    )
    report = await RestoreReconciliationEngine(
        restored, lifecycle_provider=provider
    ).reconcile_post_restore("independent-development-test")
    assert report.status == "RECONCILED"
    assert (await epochs.current(tenant)).epoch >= 7


@pytest.mark.asyncio
async def test_tombstone_reconciliation_retains_uncertain_execution(restored):
    """Isolating fixtures must never turn genuine uncertainty into success."""
    restored, tenant, generation = restored
    registry = tracking.InFlightExecutionRegistry.get_instance()
    await registry.register(
        "uncertain-execution",
        tenant,
        "component-test",
        terminate_callback=lambda: False,
    )
    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id=tenant,
            generation_id=generation,
            state=LifecycleState.TOMBSTONED,
            effective_at=datetime.now(UTC).isoformat(),
            security_epoch=7,
            revocation_floor=7,
        )
    )
    with pytest.raises(RestoreReconciliationError, match="Containment unconfirmed"):
        await RestoreReconciliationEngine(
            restored, lifecycle_provider=provider
        ).reconcile_post_restore("independent-development-test")
    assert registry.has_unresolved(tenant)
    assert list(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))


@pytest.mark.asyncio
async def test_runtime_canonical_fence_ignores_other_scope(restored, tmp_path, monkeypatch):
    restored, tenant, generation = restored
    from responsibleai.db.engine import governance_revocation_epochs
    from responsibleai.isolation import in_flight as tracking

    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    registry = tracking.InFlightExecutionRegistry()
    await registry.register(
        "execution",
        tenant,
        "harmless-test",
        admission_epoch=5,
        terminate_callback=lambda: True,
    )
    epochs = RevocationEpochRepository(restored)
    for _ in range(7):
        await epochs.bump(tenant)
    async with restored.raw.begin() as conn:
        await conn.execute(
            insert(governance_revocation_epochs).values(
                organization_id=tenant,
                scope="tenant_global",
                epoch=2,
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
    assert await registry.reconcile_epochs(restored) == ["execution"]


@pytest.mark.asyncio
async def test_tombstone_reconciliation_handles_real_approval_request_fk(restored):
    restored, tenant, generation = restored
    now = datetime.now(UTC)
    async with restored.raw.begin() as conn:
        await conn.execute(
            insert(governance_approvals).values(
                id="approval",
                org_id=tenant,
                action_id="action",
                action_type="test",
                target="harmless",
                reason_codes="[]",
                status="PENDING",
                requested_at=now.isoformat(),
            )
        )
        await conn.execute(
            insert(runtime_execution_requests).values(
                request_id="request",
                organization_id=tenant,
                principal_id="principal",
                agent_id="agent",
                identity_id="identity",
                intent="test",
                action_type="test",
                target="harmless",
                action_digest="0" * 64,
                canonical_action_payload="{}",
                approved_arguments={},
                observed_governance_epoch=0,
                idempotency_key="request",
                approval_id="approval",
                created_at=now,
            )
        )
    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id=tenant,
            generation_id=generation,
            state=LifecycleState.TOMBSTONED,
            effective_at=now.isoformat(),
            security_epoch=7,
            revocation_floor=7,
        )
    )
    report = await RestoreReconciliationEngine(
        restored, lifecycle_provider=provider
    ).reconcile_post_restore("independent-development-test")
    assert report.status == "RECONCILED"
