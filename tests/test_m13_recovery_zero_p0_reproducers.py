# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression reproducers for P0 recovery containment, Store B completeness, and verifiers."""

import json
import subprocess
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select, update

from responsibleai.data_governance.backup_defense import (
    DurableLifecycleStateProvider,
    InMemoryLifecycleStateProvider,
    LifecycleState,
    LifecycleStateRecord,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
    StartupAuthorityMode,
    evaluate_startup_authority,
)
from responsibleai.db.engine import (
    create_engine,
    governance_approvals,
    governance_execution_authorizations,
    governance_policies,
    governance_revocation_epochs,
    org_api_keys,
    organizations,
    restore_reconciliation_records,
    runtime_execution_attempts,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.isolation import in_flight as tracking
from responsibleai.runtime.authority_kernel import (
    AuthorityKernelError,
    AuthorizationIneligibleError,
    Phase7AAuthorityKernel,
)
from responsibleai.runtime.models import (
    AttemptState,
    AuthorizationStatus,
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


@pytest.mark.asyncio
async def test_reproducer_task1_unresolved_execution_file_absent_fails_closed(pg_engine, tmp_path, monkeypatch):
    """Task 1: Unresolved execution with absent tracking file and no callback MUST fail closed.

    Ensures that file absence, PID death, and callback absence are NOT treated as containment
    evidence, and private registry state is never popped or manipulated.
    """
    tracking_dir = tmp_path / "tracking_task1"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-task1-active",
                name="Task 1 Active Org",
                slug="task1-active",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-task1-active",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=1,
            revocation_floor=1,
        )
    )

    registry = tracking.InFlightExecutionRegistry.get_instance()
    unresolved_entry = tracking.InFlightExecution(
        execution_id="exec-task1-unresolved",
        organization_id="tenant-task1-active",
        action_id="action-task1",
        authorization_id=None,
        task=None,
        terminate_callback=None,  # No callback!
        created_at=time.time(),
        termination_attempts=1,
        last_termination_error="Unconfirmed remote container",
        containment_status="unresolved",
    )
    # Registry contains unresolved execution owned by tenant-task1-active
    registry._unresolved["exec-task1-unresolved"] = unresolved_entry

    # On-disk tracking file is ABSENT
    assert len(list(tracking_dir.glob("*.json"))) == 0

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    # Reconciliation MUST fail closed and MUST NOT transition to READY
    with pytest.raises(RestoreReconciliationError, match="[Uu]nresolved containment"):
        await reconciler.reconcile_post_restore("task1-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED

    # Private registry state must NOT have been manipulated or popped!
    assert "exec-task1-unresolved" in registry._unresolved
    assert len(registry.get_unresolved_containments("tenant-task1-active")) == 1
    tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_reproducer_task2_store_b_empty_fails_closed_preserves_authority_data(pg_engine):
    """Task 2: Restored Store A with active orgs when Store B is valid but empty MUST fail closed.

    Customer authority data (policies, API keys, approvals) must be preserved intact (not deleted),
    while tenant is placed in quarantine (governance_status=DISABLED) and admission fails closed.
    """
    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-task2-active",
                name="Task 2 Active Org",
                slug="task2-active",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )
        await conn.execute(
            insert(governance_policies).values(
                id="policy-task2",
                org_id="tenant-task2-active",
                rule_id="rule-task2",
                reason_code="REASON_KEEP_INTACT",
                effect="ALLOW",
                position=0,
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
            )
        )
        await conn.execute(
            insert(org_api_keys).values(
                id="key-task2",
                org_id="tenant-task2-active",
                key_hash="hash-task2",
                name="Task 2 Key",
                created_at=now.isoformat(),
                role="admin",
                revoked=0,
            )
        )
        await conn.execute(
            insert(governance_approvals).values(
                id="app-task2",
                org_id="tenant-task2-active",
                action_id="act-task2",
                action_type="test",
                target="data",
                reason_codes="[]",
                status="PENDING",
                requested_at=now.isoformat(),
            )
        )

    # Store B is valid but completely EMPTY (no records, no tombstones)
    provider = InMemoryLifecycleStateProvider()
    assert provider.verify_integrity() is True
    assert len(provider.list_all()) == 0
    assert len(provider.list_tombstones()) == 0

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    # Default call to reconcile_post_restore (fail_closed_on_unestablished_tenant=True by default)
    with pytest.raises(RestoreReconciliationError, match="lacking authoritative Store B lifecycle record"):
        await reconciler.reconcile_post_restore("task2-test")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED

    # Verify that tenant was quarantined (governance_status=DISABLED)
    async with pg_engine.raw.begin() as conn:
        org_row = (
            await conn.execute(
                select(organizations.c.governance_status, organizations.c.name)
                .where(organizations.c.id == "tenant-task2-active")
            )
        ).fetchone()
        assert org_row[0] == "DISABLED"
        assert "RESTORE_QUARANTINED" in org_row[1]

        # CRITICAL SAFETY CHECK: Customer authority data MUST be preserved (NOT deleted!)
        policy_row = (
            await conn.execute(
                select(governance_policies.c.id).where(governance_policies.c.org_id == "tenant-task2-active")
            )
        ).fetchone()
        assert policy_row is not None and policy_row[0] == "policy-task2"

        key_row = (
            await conn.execute(
                select(org_api_keys.c.id).where(org_api_keys.c.org_id == "tenant-task2-active")
            )
        ).fetchone()
        assert key_row is not None and key_row[0] == "key-task2"

        app_row = (
            await conn.execute(
                select(governance_approvals.c.id).where(governance_approvals.c.org_id == "tenant-task2-active")
            )
        ).fetchone()
        assert app_row is not None and app_row[0] == "app-task2"


@pytest.mark.asyncio
async def test_reproducer_task3_persistent_admission_proof_across_restart(tmp_path, monkeypatch):
    """Task 3: Unfinished or failed restore cannot become admitted across crash/restart.

    Tests that independent readiness gates initialized as READY, as well as production admission callers,
    strictly fail closed and block traffic when Store B persists FAILED or RECONCILING state.
    """
    store_b_file = tmp_path / "store_b_persistent_admission.db"
    provider = DurableLifecycleStateProvider(store_b_file)
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(store_b_file))

    # Simulate a restore failure in Store B
    provider.set_readiness_state(RestoreReadinessState.FAILED, updated_by="supervisor")
    assert provider.get_readiness_state() == RestoreReadinessState.FAILED

    # Simulate process crash and restart: reset global gate
    from responsibleai.data_governance import backup_defense
    backup_defense.set_restore_readiness_gate(None)

    # 1. Independent gate initialized as READY by a new process must NOT admit traffic!
    independent_gate = RestoreReadinessGate(initial_state=RestoreReadinessState.READY)
    assert independent_gate.state == RestoreReadinessState.FAILED
    assert independent_gate.is_admitted() is False
    with pytest.raises(RestoreQuarantineError, match="FAILED"):
        independent_gate.assert_traffic_admitted()

    # 2. Production admission callers must fail closed
    with pytest.raises(RestoreQuarantineError, match="FAILED"):
        backup_defense.assert_restore_readiness_admitted()

    # 3. Test production callers from other subsystems
    # Subsystem A: IAM PrivilegedSurfaceGuard
    from responsibleai.iam.enums import PrivilegedAction
    from responsibleai.iam.guard import PrivilegedSurfaceGuard
    from responsibleai.iam.models import PrivilegedCallerContext
    from responsibleai.rbac.models import Role
    with pytest.raises(RestoreQuarantineError, match="FAILED"):
        iam_guard = PrivilegedSurfaceGuard.__new__(PrivilegedSurfaceGuard)
        caller = PrivilegedCallerContext(
            principal_id="usr-1",
            org_id="org-any",
            role=Role.OWNER,
            session_id="sess-1",
        )
        await iam_guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org-any",
            action=PrivilegedAction.REVOKE_API_KEY,
        )

    # Subsystem B: Data Governance TenantDeletionOrchestrator
    from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
    with pytest.raises(RestoreQuarantineError, match="FAILED"):
        del_orch = TenantDeletionOrchestrator.__new__(TenantDeletionOrchestrator)
        await del_orch.delete_tenant(
            org_id="org-any",
            deleted_by="operator-1",
            reason="test deletion under quarantine",
        )

    # 4. Also verify unfinished restore (RECONCILING state)
    provider.set_readiness_state(RestoreReadinessState.RECONCILING, updated_by="reconciler")
    backup_defense.set_restore_readiness_gate(None)
    independent_gate_2 = RestoreReadinessGate(initial_state=RestoreReadinessState.READY)
    assert independent_gate_2.state == RestoreReadinessState.RECONCILING
    assert independent_gate_2.is_admitted() is False
    with pytest.raises(RestoreQuarantineError, match="RECONCILING"):
        independent_gate_2.assert_traffic_admitted()

    with pytest.raises(RestoreQuarantineError, match="RECONCILING"):
        backup_defense.assert_restore_readiness_admitted()


@pytest.mark.asyncio
async def test_reproducer_p0_01_corrupt_store_b_at_startup_fails_closed(tmp_path, monkeypatch):
    """Proves that when Store B is corrupt or unreadable at startup, gate strictly evaluates to FAILED."""
    corrupt_file = tmp_path / "corrupt_store_b_startup.db"
    corrupt_file.write_bytes(b"NOT_A_VALID_SQLITE_DATABASE_HEADER")
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(corrupt_file))
    monkeypatch.delenv("WHITEPACT_RESTORE_MODE", raising=False)
    monkeypatch.delenv("WHITEPACT_RESTORE_PENDING", raising=False)

    from responsibleai.data_governance import backup_defense
    backup_defense.set_restore_readiness_gate(None)

    gate = backup_defense.get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False
    assert gate.provider_error is not None

    eval_result = evaluate_startup_authority(gate)
    assert eval_result.mode == StartupAuthorityMode.UNCERTAIN
    assert eval_result.readiness_state == RestoreReadinessState.FAILED
    assert eval_result.integrity_verified is False

    with pytest.raises(RestoreQuarantineError, match="FAILED"):
        gate.assert_traffic_admitted()
    with pytest.raises(RestoreQuarantineError, match="FAILED"):
        backup_defense.assert_restore_readiness_admitted()


@pytest.mark.asyncio
async def test_reproducer_p0_02_quarantined_tenant_detached_unresolved_blocks_ready(pg_engine):
    """Proves that an unresolved execution for a quarantined tenant strictly blocks READY even with no callback or dead PID."""
    now = datetime.now(UTC).isoformat()
    org_id = f"org-q-detached-{uuid.uuid4().hex[:8]}"

    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Tombstoned Detached Org",
                slug=f"slug-{org_id}",
                created_at=now,
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id=org_id,
            generation_id="gen-q1",
            state=LifecycleState.TOMBSTONED,
            effective_at=now,
            security_epoch=1,
            revocation_floor=1,
        )
    )

    tracking.InFlightExecutionRegistry.reset_instance()
    registry = tracking.InFlightExecutionRegistry.get_instance()

    rec = tracking.InFlightExecution(
        execution_id=f"exec-detached-{uuid.uuid4().hex[:8]}",
        organization_id=org_id,
        action_id="act-detached",
        authorization_id="auth-detached",
        task=None,
        terminate_callback=None,
        created_at=time.time(),
        last_termination_error="Worker process detached and absent from process table",
        containment_status="unresolved",
    )
    registry._unresolved[rec.execution_id] = rec

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="Containment unconfirmed for quarantined tenant"):
        await reconciler.reconcile_post_restore("p0-02-auditor")

    assert gate.state != RestoreReadinessState.READY
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False


@pytest.mark.asyncio
async def test_reproducer_p0_04_crash_consistency_database_status_never_prematurely_reconciled(pg_engine, monkeypatch):
    """Proves that PostgreSQL status is never marked RECONCILED before containment completes, and failures record FAILED cleanly."""
    now = datetime.now(UTC).isoformat()
    org_id = f"org-crash-{uuid.uuid4().hex[:8]}"

    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Crash Consist Org",
                slug=f"slug-{org_id}",
                created_at=now,
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id=org_id,
            generation_id="gen-c1",
            state=LifecycleState.ACTIVE,
            effective_at=now,
            security_epoch=1,
            revocation_floor=1,
        )
    )

    tracking.InFlightExecutionRegistry.reset_instance()
    registry = tracking.InFlightExecutionRegistry.get_instance()

    async def _failing_reconcile_epochs(*args, **kwargs):
        raise RuntimeError("Simulated crash/network failure during in-flight epoch reconciliation")

    monkeypatch.setattr(registry, "reconcile_epochs", _failing_reconcile_epochs)

    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="Revocation epoch reconciliation failed"):
        await reconciler.reconcile_post_restore("crash-auditor")

    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # Check database record: must be exactly 1 record and its status must be FAILED, NEVER RECONCILED
    async with pg_engine.raw.connect() as conn:
        records = (
            await conn.execute(
                select(restore_reconciliation_records).order_by(
                    restore_reconciliation_records.c.restored_at.desc()
                )
            )
        ).fetchall()
        matching = [r for r in records if r.reconciled_by == "crash-auditor"]
        assert len(matching) == 1
        assert matching[0].status == "FAILED"
        assert "Simulated crash" in matching[0].details_json


@pytest.mark.asyncio
async def test_reproducer_p0_05_multiprocess_authority_consistency(tmp_path, monkeypatch):
    """Proves that multiple independent worker processes observing Store B maintain identical fail-closed admission."""
    store_b_file = tmp_path / "store_b_multiprocess.db"
    provider = DurableLifecycleStateProvider(store_b_file)
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(store_b_file))
    monkeypatch.delenv("WHITEPACT_RESTORE_MODE", raising=False)
    monkeypatch.delenv("WHITEPACT_RESTORE_PENDING", raising=False)

    from responsibleai.data_governance import backup_defense

    # 1. Store B set to FAILED by Recovery Orchestrator
    provider.set_readiness_state(RestoreReadinessState.FAILED, updated_by="orch-1")

    # Worker A initializes fresh gate
    gate_worker_a = RestoreReadinessGate(initial_state=RestoreReadinessState.READY)
    # Worker B initializes fresh gate
    gate_worker_b = RestoreReadinessGate(initial_state=RestoreReadinessState.READY)

    assert gate_worker_a.state == RestoreReadinessState.FAILED
    assert gate_worker_b.state == RestoreReadinessState.FAILED
    assert gate_worker_a.is_admitted() is False
    assert gate_worker_b.is_admitted() is False

    # 2. Worker C starts up with global getter
    backup_defense.set_restore_readiness_gate(None)
    gate_worker_c = backup_defense.get_restore_readiness_gate()
    assert gate_worker_c.state == RestoreReadinessState.FAILED
    assert gate_worker_c.is_admitted() is False

    # 3. Store B updated to RECONCILING
    provider.set_readiness_state(RestoreReadinessState.RECONCILING, updated_by="orch-2")
    assert gate_worker_a.state == RestoreReadinessState.RECONCILING
    assert gate_worker_b.state == RestoreReadinessState.RECONCILING
    assert gate_worker_c.state == RestoreReadinessState.RECONCILING
    assert gate_worker_a.is_admitted() is False
    assert gate_worker_b.is_admitted() is False
    assert gate_worker_c.is_admitted() is False

    # 4. Store B successfully updated to READY
    provider.set_readiness_state(RestoreReadinessState.READY, updated_by="orch-3")
    assert gate_worker_a.state == RestoreReadinessState.READY
    assert gate_worker_b.state == RestoreReadinessState.READY
    assert gate_worker_c.state == RestoreReadinessState.READY
    assert gate_worker_a.is_admitted() is True
    assert gate_worker_b.is_admitted() is True
    assert gate_worker_c.is_admitted() is True


@pytest.mark.asyncio
async def test_adversarial_p0_01_detached_alive_container_without_tracking_fails_closed(pg_engine, tmp_path, monkeypatch):
    """Adversarial P0-01: Proves that a detached container whose tracking file disappears
    remains in _unresolved and blocks READY until Docker authoritatively establishes termination.
    """
    tracking_dir = tmp_path / "tracking_p0_01"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="tenant-adv-p01",
                name="Adv P01 Org",
                slug="adv-p01",
                created_at=now.isoformat(),
                governance_status="ACTIVE",
            )
        )

    provider = InMemoryLifecycleStateProvider()
    provider.record_state(
        LifecycleStateRecord(
            tenant_id="tenant-adv-p01",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at=now.isoformat(),
            security_epoch=1,
            revocation_floor=1,
        )
    )

    registry = tracking.InFlightExecutionRegistry.get_instance()
    container_id = "wp-sandbox-detached-1234"

    # Register in-flight execution with container_name
    await registry.register(
        execution_id="exec-adv-p01",
        organization_id="tenant-adv-p01",
        action_id="action-adv-p01",
        container_name=container_id,
    )

    # 1. Simulate worker crash/exit: tracking file disappears from disk, task & callback are None
    entry = registry._active.pop("exec-adv-p01")
    entry.task = None
    entry.terminate_callback = None
    registry._active["exec-adv-p01"] = entry

    # Mock docker calls: container is currently ALIVE
    docker_running_output = json.dumps([{"State": {"Running": True, "Status": "running"}}])
    docker_dead_output = json.dumps([{"State": {"Running": False, "Status": "exited"}}])

    def mock_subprocess_run(cmd, *args, **kwargs):
        if "inspect" in cmd:
            if mock_state["running"]:
                return subprocess.CompletedProcess(cmd, 0, stdout=docker_running_output, stderr="")
            else:
                return subprocess.CompletedProcess(cmd, 0, stdout=docker_dead_output, stderr="")
        elif "rm" in cmd:
            mock_state["running"] = False
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    mock_state = {"running": True}
    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)

    # 2. Terminate in flight is invoked (or cleanup scan)
    # If Docker rm fails or container remains running, it MUST NOT be resolved
    def mock_failing_rm(cmd, *args, **kwargs):
        if "inspect" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=docker_running_output, stderr="")
        if "rm" in cmd:
            raise subprocess.CalledProcessError(1, cmd, stderr="Docker daemon error on rm")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", mock_failing_rm)
    await registry.terminate_in_flight(organization_id="tenant-adv-p01")

    # Execution MUST be in _unresolved!
    assert "exec-adv-p01" in registry._unresolved
    assert registry.get_unresolved_containments("tenant-adv-p01")

    # Reconciliation MUST fail closed
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(pg_engine, lifecycle_provider=provider, gate=gate)

    with pytest.raises(RestoreReconciliationError, match="[Uu]nresolved containment"):
        await reconciler.reconcile_post_restore("adv-p01-test")

    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # 3. Now let Docker confirm container is dead / removed
    monkeypatch.setattr(subprocess, "run", mock_subprocess_run)
    mock_state["running"] = False

    resolved = await registry.retry_unresolved()
    assert len(resolved) == 1
    assert "exec-adv-p01" in resolved
    assert "exec-adv-p01" not in registry._unresolved

    # Now reconciliation must succeed
    gate.set_state(RestoreReadinessState.RESTORE_PENDING)
    await reconciler.reconcile_post_restore("adv-p01-test")
    assert gate.state == RestoreReadinessState.READY
    assert gate.is_admitted() is True

    tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_adversarial_p0_01_docker_timeout_daemon_failure_fails_closed(tmp_path, monkeypatch):
    """Adversarial P0-01: Proves that Docker timeouts and daemon connection errors
    fail closed and maintain unresolved tracking.
    """
    tracking_dir = tmp_path / "tracking_p0_01_timeout"
    tracking_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
    tracking.InFlightExecutionRegistry.reset_instance()

    registry = tracking.InFlightExecutionRegistry.get_instance()
    container_id = "wp-sandbox-timeout-test"

    registry._unresolved["exec-timeout"] = tracking.InFlightExecution(
        execution_id="exec-timeout",
        organization_id="tenant-timeout",
        action_id="act-1",
        authorization_id=None,
        task=None,
        terminate_callback=None,
        created_at=time.time(),
        container_name=container_id,
        termination_attempts=1,
    )

    # 1. Simulate Docker timeout
    def mock_timeout(cmd, *args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr(subprocess, "run", mock_timeout)

    is_contained = await tracking.verify_authoritative_container_containment(container_id)
    assert is_contained is False

    resolved = await registry.retry_unresolved()
    assert len(resolved) == 0
    assert "exec-timeout" in registry._unresolved

    # 2. Simulate Docker daemon error
    def mock_daemon_error(cmd, *args, **kwargs):
        raise subprocess.CalledProcessError(1, cmd, stderr="Cannot connect to the Docker daemon at unix:///var/run/docker.sock. Is the docker daemon running?")

    monkeypatch.setattr(subprocess, "run", mock_daemon_error)

    is_contained = await tracking.verify_authoritative_container_containment(container_id)
    assert is_contained is False

    resolved = await registry.retry_unresolved()
    assert len(resolved) == 0
    assert "exec-timeout" in registry._unresolved

    tracking.InFlightExecutionRegistry.reset_instance()


@pytest.mark.asyncio
async def test_adversarial_p0_02_startup_authority_matrix(pg_engine, tmp_path, monkeypatch):
    """Adversarial P0-02: Exhaustively verifies startup authority evaluation across
    NORMAL, RECOVERY, and UNCERTAIN modes.
    """
    from responsibleai.data_governance.backup_defense import (
        StartupAuthorityMode,
        bind_restore_gate_engine,
        evaluate_startup_authority,
        evaluate_startup_authority_async,
        get_restore_readiness_gate,
        set_restore_readiness_gate,
    )

    # Clean state
    set_restore_readiness_gate(None)
    bind_restore_gate_engine(None)

    # -------------------------------------------------------------
    # 1. NORMAL mode: clean startup without restore flags
    # -------------------------------------------------------------
    monkeypatch.delenv("WHITEPACT_RESTORE_MODE", raising=False)
    monkeypatch.delenv("WHITEPACT_RESTORE_PENDING", raising=False)
    monkeypatch.delenv("WHITEPACT_STORE_B_PATH", raising=False)

    bind_restore_gate_engine(pg_engine)
    res = await evaluate_startup_authority_async(engine=pg_engine)
    assert res.mode == StartupAuthorityMode.NORMAL
    gate = get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.READY
    assert gate.is_admitted() is True

    # -------------------------------------------------------------
    # 2. Database authority violation in NORMAL mode:
    # If the database has an unreconciled recovery record in FAILED
    # -------------------------------------------------------------
    now = datetime.now(UTC)
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            insert(restore_reconciliation_records).values(
                id=str(uuid.uuid4()),
                restored_at=now.isoformat(),
                status="FAILED",
                tombstones_detected=1,
                tenants_quarantined=1,
                details_json=json.dumps({"error": "Unfinished restore attempt"}),
                reconciled_by="admin-1",
            )
        )

    set_restore_readiness_gate(None)
    res = await evaluate_startup_authority_async(engine=pg_engine)
    assert res.mode in (StartupAuthorityMode.RECOVERY, StartupAuthorityMode.UNCERTAIN)
    assert res.readiness_state == RestoreReadinessState.FAILED
    gate = get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # Clean up that record so we can test other branches
    async with pg_engine.raw.begin() as conn:
        await conn.execute(
            update(restore_reconciliation_records)
            .where(restore_reconciliation_records.c.reconciled_by == "admin-1")
            .values(status="RECONCILED")
        )

    # -------------------------------------------------------------
    # 3. RECOVERY mode: flags set, valid Store B file present and READY
    # -------------------------------------------------------------
    store_b_file = tmp_path / "store_b_valid.db"
    provider = DurableLifecycleStateProvider(store_b_file)
    provider.set_readiness_state(RestoreReadinessState.READY, updated_by="test-orch")

    monkeypatch.setenv("WHITEPACT_RESTORE_MODE", "1")
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(store_b_file))

    set_restore_readiness_gate(None)
    res = await evaluate_startup_authority_async(engine=pg_engine)
    assert res.readiness_state == RestoreReadinessState.READY
    gate = get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.READY
    assert gate.is_admitted() is True

    # -------------------------------------------------------------
    # 4. UNCERTAIN mode under recovery conditions:
    # 4a. Missing WHITEPACT_STORE_B_PATH
    # -------------------------------------------------------------
    monkeypatch.delenv("WHITEPACT_STORE_B_PATH", raising=False)
    set_restore_readiness_gate(None)
    res = evaluate_startup_authority()
    assert res.mode == StartupAuthorityMode.UNCERTAIN
    gate = get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # 4b. Forbidden Store B filename
    forbidden_store_b = tmp_path / "whitepact_store_b_lifecycle.db"
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(forbidden_store_b))
    set_restore_readiness_gate(None)
    res = evaluate_startup_authority()
    assert res.mode == StartupAuthorityMode.UNCERTAIN
    gate = get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # 4c. Corrupt Store B file
    corrupt_file = tmp_path / "corrupt_store_b.db"
    corrupt_file.write_bytes(b"NOT A SQLITE FILE HEADER")
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(corrupt_file))
    set_restore_readiness_gate(None)
    res = evaluate_startup_authority()
    assert res.mode == StartupAuthorityMode.UNCERTAIN
    gate = get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # 4d. Store B file in FAILED state
    failed_store_b = tmp_path / "failed_store_b.db"
    prov_failed = DurableLifecycleStateProvider(failed_store_b)
    prov_failed.set_readiness_state(RestoreReadinessState.FAILED, updated_by="test-orch")
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(failed_store_b))
    set_restore_readiness_gate(None)
    res = evaluate_startup_authority()
    assert res.readiness_state == RestoreReadinessState.FAILED
    gate = get_restore_readiness_gate()
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # Reset gate for subsequent tests
    set_restore_readiness_gate(None)
    bind_restore_gate_engine(None)
