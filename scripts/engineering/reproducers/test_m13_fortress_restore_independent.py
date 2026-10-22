# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL structural restore tests; fixture data is NOT a customer journey."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert
from tests.pg_test_url import isolated_pg_url

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleState,
    LifecycleStateRecord,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
)
from responsibleai.db.engine import (
    create_engine,
    governance_approvals,
    organizations,
    runtime_execution_requests,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
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
    databases = isolated_pg_url("wp_convergence_restore")
    database = await anext(databases)
    await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
    engine = create_engine(database)
    try:
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(organizations).values(
                    id="restored-tenant",
                    name="Restore test",
                    slug="restore-test",
                    created_at=datetime.now(UTC).isoformat(),
                    governance_status="ACTIVE",
                )
            )
        yield engine
    finally:
        await engine.close()
        await databases.aclose()


@pytest.mark.asyncio
async def test_store_b_floor_fences_canonical_governance_epoch(restored):
    epochs = RevocationEpochRepository(restored)
    await epochs.bump("restored-tenant")
    await epochs.bump("restored-tenant")
    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="restored-tenant",
            generation_id="generation",
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
    assert (await epochs.current("restored-tenant")).epoch >= 7


@pytest.mark.asyncio
async def test_tombstone_reconciliation_retains_uncertain_execution(restored):
    """Isolating fixtures must never turn genuine uncertainty into success."""
    registry = tracking.InFlightExecutionRegistry.get_instance()
    await registry.register(
        "uncertain-execution",
        "restored-tenant",
        "component-test",
        terminate_callback=lambda: False,
    )
    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="restored-tenant",
            generation_id="generation",
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
    assert registry.has_unresolved("restored-tenant")
    assert list(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))


@pytest.mark.asyncio
async def test_runtime_canonical_fence_ignores_other_scope(restored, tmp_path, monkeypatch):
    from responsibleai.db.engine import governance_revocation_epochs
    from responsibleai.isolation import in_flight as tracking

    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    registry = tracking.InFlightExecutionRegistry()
    await registry.register(
        "execution",
        "restored-tenant",
        "harmless-test",
        admission_epoch=5,
        terminate_callback=lambda: True,
    )
    epochs = RevocationEpochRepository(restored)
    for _ in range(7):
        await epochs.bump("restored-tenant")
    async with restored.raw.begin() as conn:
        await conn.execute(
            insert(governance_revocation_epochs).values(
                organization_id="restored-tenant",
                scope="tenant_global",
                epoch=2,
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
    assert await registry.reconcile_epochs(restored) == ["execution"]


@pytest.mark.asyncio
async def test_tombstone_reconciliation_handles_real_approval_request_fk(restored):
    now = datetime.now(UTC)
    async with restored.raw.begin() as conn:
        await conn.execute(
            insert(governance_approvals).values(
                id="approval",
                org_id="restored-tenant",
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
                organization_id="restored-tenant",
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
            tenant_id="restored-tenant",
            generation_id="generation",
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
