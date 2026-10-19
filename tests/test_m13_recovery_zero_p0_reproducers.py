# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression reproducers for P0 recovery containment, Store B completeness, and verifiers."""

from datetime import UTC, datetime, timedelta
import json
import os
import subprocess
import time
import uuid
import pytest
from sqlalchemy import insert, select, update

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleState,
    LifecycleStateRecord,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
)
from responsibleai.db.engine import (
    create_engine,
    governance_approvals,
    governance_execution_authorizations,
    governance_revocation_epochs,
    organizations,
    runtime_execution_attempts,
    runtime_execution_requests,
    runtime_worker_leases,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.isolation import in_flight as tracking
from responsibleai.runtime.authority_kernel import (
    AuthorizationIneligibleError,
    AuthorityKernelError,
    Phase7AAuthorityKernel,
)
from responsibleai.runtime.models import (
    AttemptState,
    AuthorizationStatus,
    EffectState,
    LeaseStatus,
)
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_engine():
    databases = isolated_pg_url("wp_p0_restore")
    database = await anext(databases)
    await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
    engine = create_engine(database)
    try:
        yield engine
    finally:
        await engine.close()
        await databases.aclose()


@pytest.mark.asyncio
async def test_reproducer_containment_terminate_in_flight_raises_blocks_ready(pg_engine, tmp_path, monkeypatch):
    """Proves that when terminate_in_flight raises, recovery must NOT advance to READY."""
    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-fail-contain",
                name="Contain Fail Org",
                slug="contain-fail",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-fail-contain",
            generation_id="gen-1",
            state=LifecycleState.TOMBSTONED,
            effective_at=now.isoformat(),
            security_epoch=5,
            revocation_floor=5,
        )
    )

    registry = tracking.InFlightExecutionRegistry.get_instance()

    async def _failing_terminate(*args, **kwargs):
        raise RuntimeError("Simulated low-level container termination failure")

    monkeypatch.setattr(registry, "terminate_in_flight", _failing_terminate)

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="containment|failure|aborted"):
        await reconciler.reconcile_post_restore("p0-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED


@pytest.mark.asyncio
async def test_reproducer_unconfirmed_container_termination_blocks_ready(pg_engine, tmp_path, monkeypatch):
    """Proves that when container callback returns False (unconfirmed), recovery must NOT enter READY."""
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-unconfirmed",
                name="Unconfirmed Org",
                slug="unconfirmed-org",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    registry = tracking.InFlightExecutionRegistry.get_instance()
    # Register an execution whose callback fails to confirm termination
    await registry.register(
        execution_id="exec-unconfirmed",
        organization_id="tenant-unconfirmed",
        action_id="action-test",
        admission_epoch=1,
        terminate_callback=lambda: False,  # Does not confirm termination!
    )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-unconfirmed",
            generation_id="gen-1",
            state=LifecycleState.TOMBSTONED,
            effective_at=now.isoformat(),
            security_epoch=5,
            revocation_floor=5,
        )
    )

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="[Uu]nconfirmed|[Uu]nresolved"):
        await reconciler.reconcile_post_restore("p0-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED
    assert registry.count_unresolved("tenant-unconfirmed") > 0


@pytest.mark.asyncio
async def test_reproducer_store_a_active_org_missing_from_store_b_fails_closed(pg_engine):
    """Proves that when Store A has an ACTIVE org with NO Store B record, admission must not be READY."""
    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-orphaned-in-a",
                name="Orphaned Org",
                slug="orphaned-org",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="valid-tenant-in-b",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=1,
            revocation_floor=1,
        )
    )
    # Store B has NO record for 'tenant-orphaned-in-a'
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="authoritative Store B lifecycle"):
        await reconciler.reconcile_post_restore("p0-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED

    # Organization must also be quarantined in Store A
    async with pg_engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(organizations).where(organizations.c.id == "tenant-orphaned-in-a")
            )
        ).fetchone()
        assert row.governance_status == "DISABLED"


@pytest.mark.asyncio
async def test_reproducer_reconcile_epochs_raises_blocks_ready(pg_engine, monkeypatch):
    """Proves that when reconcile_epochs raises, recovery must NOT enter READY."""
    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-epoch-fail",
                name="Epoch Fail Org",
                slug="epoch-fail-org",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-epoch-fail",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=1,
            revocation_floor=1,
        )
    )

    registry = tracking.InFlightExecutionRegistry.get_instance()

    async def _failing_reconcile(*args, **kwargs):
        raise RuntimeError("Simulated DB connectivity failure during epoch reconciliation")

    monkeypatch.setattr(registry, "reconcile_epochs", _failing_reconcile)

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="epoch reconciliation failed"):
        await reconciler.reconcile_post_restore("p0-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED


@pytest.mark.asyncio
async def test_reproducer_detached_alive_container_blocks_ready(pg_engine, tmp_path, monkeypatch):
    """Proves that when a detached alive worker container is detected, recovery fails closed."""
    tracking_dir = tmp_path / "tracking_detached"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-detached",
                name="Detached Org",
                slug="detached-org",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-detached",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=1,
            revocation_floor=1,
        )
    )

    proc = subprocess.Popen(["sleep", "30"])
    try:
        trk_file = tracking_dir / "trk_detached_proc.json"
        trk_file.write_text(
            json.dumps({
                "execution_id": "exec-detached-1",
                "organization_id": "tenant-detached",
                "action_id": "act-detached",
                "pid": proc.pid,
                "containment_status": "active",
                "created_at": time.time(),
            }),
            encoding="utf-8",
        )

        gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
        reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

        with pytest.raises(RestoreReconciliationError, match="unresolved containment"):
            await reconciler.reconcile_post_restore("p0-test")

        assert gate.state != RestoreReadinessState.READY
        assert gate.state == RestoreReadinessState.FAILED
    finally:
        proc.kill()
        proc.wait()
        tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_reproducer_corrupted_registry_directory_blocks_ready(pg_engine, tmp_path, monkeypatch):
    """Proves that corrupted or inaccessible registry files cause fail-closed rejection."""
    tracking_dir = tmp_path / "tracking_corrupt"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-corrupt-trk",
                name="Corrupt Tracking Org",
                slug="corrupt-trk-org",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-corrupt-trk",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=1,
            revocation_floor=1,
        )
    )

    corrupt_file = tracking_dir / "corrupted_tracking.json"
    corrupt_file.write_bytes(b"INVALID_JSON_CORRUPTED_BYTES{{{")

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="unresolved containment"):
        await reconciler.reconcile_post_restore("p0-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED
    tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_reproducer_unresolved_legacy_execution_blocks_ready(pg_engine, tmp_path, monkeypatch):
    """Proves that pre-existing unresolved or unattributed legacy executions block READY."""
    tracking_dir = tmp_path / "tracking_legacy"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-legacy-test",
                name="Legacy Test Org",
                slug="legacy-test-org",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-legacy-test",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=1,
            revocation_floor=1,
        )
    )

    registry = tracking.InFlightExecutionRegistry.get_instance()
    legacy_entry = tracking.InFlightExecution(
        execution_id="exec-unattributed-legacy",
        organization_id="unknown",
        action_id="act-legacy",
        authorization_id=None,
        task=None,
        terminate_callback=None,
        created_at=time.time(),
        termination_attempts=1,
        last_termination_error="Unattributed legacy worker",
        containment_status="unresolved",
    )
    registry._unresolved["exec-unattributed-legacy"] = legacy_entry

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="unresolved containment"):
        await reconciler.reconcile_post_restore("p0-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED
    tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_reproducer_sibling_tenant_isolation_under_store_b(pg_engine, tmp_path, monkeypatch):
    """Proves that Store B records for Tenant X do not cross-contaminate or alter Tenant Y."""
    tracking_dir = tmp_path / "tracking_iso"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                [
                    {
                        "id": "tenant-iso-alpha",
                        "name": "Alpha Tenant",
                        "slug": "alpha-tenant",
                        "created_at": now.isoformat(),
                        "governance_status": "ACTIVE",
                    },
                    {
                        "id": "tenant-iso-beta",
                        "name": "Beta Tenant",
                        "slug": "beta-tenant",
                        "created_at": now.isoformat(),
                        "governance_status": "ACTIVE",
                    },
                ]
            )
        )
        await conn.execute(
            insert(governance_revocation_epochs).values(
                [
                    {
                        "organization_id": "tenant-iso-alpha",
                        "scope": "governance",
                        "epoch": 2,
                        "updated_at": now.isoformat(),
                    },
                    {
                        "organization_id": "tenant-iso-beta",
                        "scope": "governance",
                        "epoch": 10,
                        "updated_at": now.isoformat(),
                    },
                ]
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-iso-alpha",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=5,
            revocation_floor=5,
        )
    )
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-iso-beta",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=10,
            revocation_floor=10,
        )
    )
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-unrelated-gamma",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=99,
            revocation_floor=99,
        )
    )

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)
    report = await reconciler.reconcile_post_restore("p0-test")
    assert report.status == "RECONCILED"
    assert gate.state == RestoreReadinessState.READY

    async with pg_engine.raw.connect() as conn:
        rows = (
            await conn.execute(
                select(
                    governance_revocation_epochs.c.organization_id,
                    governance_revocation_epochs.c.scope,
                    governance_revocation_epochs.c.epoch,
                ).where(governance_revocation_epochs.c.scope == "governance")
            )
        ).fetchall()
        epoch_map = {r[0]: r[2] for r in rows}

        assert epoch_map["tenant-iso-alpha"] == 5
        assert epoch_map["tenant-iso-beta"] == 10
        assert "tenant-unrelated-gamma" not in epoch_map
    tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_reproducer_corrupt_and_stale_store_b_records(pg_engine, tmp_path, monkeypatch):
    """Proves that corrupt Store B verification fails closed and stale epochs are monotonic."""
    tracking_dir = tmp_path / "tracking_stale"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-monotonic",
                name="Monotonic Org",
                slug="monotonic-org",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )
        await conn.execute(
            insert(governance_revocation_epochs).values(
                organization_id="tenant-monotonic",
                scope="governance",
                epoch=15,
                updated_at=now.isoformat(),
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-monotonic",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=10,
            revocation_floor=10,
        )
    )

    # 1. Stale epoch in Store B does not degrade higher epoch in Store A
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)
    await reconciler.reconcile_post_restore("p0-test")
    assert gate.state == RestoreReadinessState.READY

    async with pg_engine.raw.connect() as conn:
        ep = (
            await conn.execute(
                select(governance_revocation_epochs.c.epoch).where(
                    governance_revocation_epochs.c.organization_id == "tenant-monotonic",
                    governance_revocation_epochs.c.scope == "governance",
                )
            )
        ).scalar()
        assert ep == 15

    # 2. Corrupt provider fails closed
    provider.set_available(False)
    gate_corrupt = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler_corrupt = RestoreReconciliationEngine(
        pg_engine, lifecycle_provider=provider, gate=gate_corrupt
    )
    with pytest.raises(RestoreReconciliationError, match="integrity check failed|unavailable"):
        await reconciler_corrupt.reconcile_post_restore("p0-test")
    assert gate_corrupt.state == RestoreReadinessState.FAILED
    tracking.InFlightExecutionRegistry.reset_instance()


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


@pytest.mark.asyncio
async def test_reproducer_credential_fencing_matrix_full_verification(pg_engine, tmp_path, monkeypatch):
    """Direct integration test against Phase7AAuthorityKernel verifying all 7 credential fencing scenarios."""
    tracking_dir = tmp_path / "tracking_kernel"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    kernel = Phase7AAuthorityKernel(pg_engine)

    # Setup base organizations in Store A
    async with pg_engine.raw.begin() as conn:
        for org_id in ["org-s123", "org-s4-revoked", "org-s5-tombstone", "org-s6-consumed", "org-s7-stale"]:
            await conn.execute(
                insert(organizations).values(
                    id=org_id,
                    name=f"Org {org_id}",
                    slug=f"slug-{org_id}",
                    created_at=now.isoformat(),
                    governance_status="ACTIVE",
                )
            )
            await conn.execute(
                insert(governance_revocation_epochs).values(
                    organization_id=org_id,
                    scope="governance",
                    epoch=5,
                    updated_at=now.isoformat(),
                )
            )

    provider = InMemoryLifecycleStateProvider()
    for org_id in ["org-s123", "org-s4-revoked", "org-s5-tombstone", "org-s6-consumed", "org-s7-stale"]:
        provider.record_state(
            LifecycleStateRecord(
                tenant_id=org_id,
                generation_id="gen-1",
                state=LifecycleState.ACTIVE,
                effective_at=now.isoformat(),
                security_epoch=5,
                revocation_floor=5,
            )
        )

    # -------------------------------------------------------------
    # Scenario 1, 2, 3: Restored epoch == Store B floor == issuer epoch, no subsequent revocation
    # -------------------------------------------------------------
    issued_123 = await kernel.issue(**_issue_kwargs("org-s123"))
    assert issued_123.observed_epoch == 5
    await kernel.acquire_lease(request_id=issued_123.request_id, worker_id="w-1", organization_id="org-s123")
    await kernel.admit(request_id=issued_123.request_id, worker_id="w-1", organization_id="org-s123")
    claim_123 = await kernel.claim_backend_start(request_id=issued_123.request_id, worker_id="w-1", organization_id="org-s123")
    assert claim_123.organization_id == "org-s123"

    # -------------------------------------------------------------
    # Scenario 4: Store B recorded a later revocation (floor > issuer_epoch)
    # -------------------------------------------------------------
    issued_4 = await kernel.issue(**_issue_kwargs("org-s4-revoked"))
    assert issued_4.observed_epoch == 5
    await kernel.acquire_lease(request_id=issued_4.request_id, worker_id="w-4", organization_id="org-s4-revoked")
    # Later revocation recorded in Store B (floor elevated to 8)
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="org-s4-revoked",
            generation_id="gen-2",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=8,
            revocation_floor=8,
        )
    )
    # Reconcile post-restore elevates Store A epoch to 8
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider)
    await reconciler.reconcile_post_restore("reconciler-p0")
    # Verification of credential issued at epoch 5 must be rejected
    with pytest.raises(AuthorizationIneligibleError, match="Authorization epoch mismatch"):
        await kernel.admit(request_id=issued_4.request_id, worker_id="w-4", organization_id="org-s4-revoked")

    # -------------------------------------------------------------
    # Scenario 5: Tenant lifecycle state is TOMBSTONED
    # -------------------------------------------------------------
    issued_5 = await kernel.issue(**_issue_kwargs("org-s5-tombstone"))
    await kernel.acquire_lease(request_id=issued_5.request_id, worker_id="w-5", organization_id="org-s5-tombstone")
    # Store B marks tenant as TOMBSTONED
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="org-s5-tombstone",
            generation_id="gen-tomb",
            state=LifecycleState.TOMBSTONED,
            effective_at=now.isoformat(),
            security_epoch=10,
            revocation_floor=10,
        )
    )
    # Reconcile post-restore quarantines tenant
    await reconciler.reconcile_post_restore("reconciler-p0")
    # Verifier must reject because organization is disabled / quarantined
    with pytest.raises(AuthorityKernelError, match="Organization is not ACTIVE"):
        await kernel.admit(request_id=issued_5.request_id, worker_id="w-5", organization_id="org-s5-tombstone")

    # -------------------------------------------------------------
    # Scenario 6: A grant was already consumed before backup / nonce replayed
    # -------------------------------------------------------------
    issued_6 = await kernel.issue(**_issue_kwargs("org-s6-consumed"))
    await kernel.acquire_lease(request_id=issued_6.request_id, worker_id="w-6", organization_id="org-s6-consumed")
    await kernel.admit(request_id=issued_6.request_id, worker_id="w-6", organization_id="org-s6-consumed")
    # 6a: Attempting to admit an already consumed authorization
    with pytest.raises(AuthorizationIneligibleError, match="Authorization is not ISSUED"):
        await kernel.admit(request_id=issued_6.request_id, worker_id="w-6", organization_id="org-s6-consumed")
    # 6b: If authorization status was forcibly reset to ISSUED in DB, nonce uniqueness still blocks it
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            update(governance_execution_authorizations)
            .where(governance_execution_authorizations.c.request_id == issued_6.request_id)
            .values(status=AuthorizationStatus.ISSUED.value)
        )
        await conn.execute(
            update(runtime_execution_attempts)
            .where(runtime_execution_attempts.c.request_id == issued_6.request_id)
            .values(state=AttemptState.LEASED.value)
        )
    with pytest.raises(AuthorizationIneligibleError, match="Oneshot authority already consumed"):
        await kernel.admit(request_id=issued_6.request_id, worker_id="w-6", organization_id="org-s6-consumed")

    # -------------------------------------------------------------
    # Scenario 7: Stale authorization survives backup snapshot (expired or stale epoch)
    # -------------------------------------------------------------
    issued_7 = await kernel.issue(**_issue_kwargs("org-s7-stale"))
    await kernel.acquire_lease(request_id=issued_7.request_id, worker_id="w-7", organization_id="org-s7-stale")
    # 7a: Expired authorization
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            update(governance_execution_authorizations)
            .where(governance_execution_authorizations.c.request_id == issued_7.request_id)
            .values(expires_at=now - timedelta(seconds=60))
        )
    with pytest.raises(AuthorizationIneligibleError, match="Authorization expired"):
        await kernel.admit(request_id=issued_7.request_id, worker_id="w-7", organization_id="org-s7-stale")

    # 7b: Stale issuer epoch
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            update(governance_execution_authorizations)
            .where(governance_execution_authorizations.c.request_id == issued_7.request_id)
            .values(expires_at=now + timedelta(seconds=60), issuer_epoch=1)
        )
    with pytest.raises(AuthorizationIneligibleError, match="Authorization epoch mismatch"):
        await kernel.admit(request_id=issued_7.request_id, worker_id="w-7", organization_id="org-s7-stale")

    tracking.InFlightExecutionRegistry.reset_instance()
