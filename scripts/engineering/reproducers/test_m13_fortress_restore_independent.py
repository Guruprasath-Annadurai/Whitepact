# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL structural restore tests; fixture data is NOT a customer journey."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from scripts.engineering import m13_floor_repair_poc as floor_repair
from sqlalchemy import insert, text
from tests.test_codex_fortress_recovery_qualification import (
    approval_fk_restore_scenario,
    no_effect_counts,
    recovery_receipt,
)
from tests.test_codex_fortress_recovery_qualification import (
    qualified_target as qualified_target,
)
from tests.test_codex_fortress_recovery_qualification import (
    real_recovery as real_recovery,
)
from tests.test_final_floor_repair_poc import floor_target as floor_target
from tests.test_final_floor_repair_poc import signatures
from tests.test_operator_recovery_postgres import sign
from tests.test_stage3_controller_postgres import isolated_controller_context

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
)
from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
from responsibleai.data_governance.operator_recovery_control import (
    execute_offline_recovery,
    prepare_offline_recovery,
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
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_store_b_floor_fences_canonical_governance_epoch(floor_target):
    restored, provider, gate, profile, keys, tenant = floor_target
    epochs = RevocationEpochRepository(restored)
    generation = provider.get_state(tenant).generation_id
    before = await no_effect_counts(restored)
    assert (await epochs.current(tenant)).epoch == 3
    plan = await floor_repair.prepare(restored, provider, profile_path=profile, tenant=tenant)
    result = await floor_repair.execute(
        restored,
        provider,
        profile_path=profile,
        plan=plan,
        signatures=signatures(plan.canonical_bytes(), keys),
    )
    assert result == {"state": "FLOOR_ADVANCED", "epoch": 7, "ready": False}
    assert not gate.is_admitted()
    assert provider.get_state(tenant).generation_id == generation
    assert provider.get_state(tenant).revocation_floor == 7
    manifest = await prepare_offline_recovery(restored, provider, profile_path=profile)
    report = await execute_offline_recovery(
        restored,
        provider,
        gate,
        profile_path=profile,
        manifest=manifest,
        signatures=sign(manifest, keys),
    )
    assert report.status == "RECONCILED"
    assert (await epochs.current(tenant)).epoch >= 7
    assert await no_effect_counts(restored) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_tombstone_reconciliation_retains_uncertain_execution(qualified_target, monkeypatch):
    """Isolating fixtures must never turn genuine uncertainty into success."""
    restored, provider, gate, profile, keys, tenant = qualified_target
    await TenantDeletionOrchestrator(restored, provider).delete_tenant(
        tenant, deleted_by="disposable-test-controller", reason="historical-containment"
    )
    assert provider.get_state(tenant).state == LifecycleState.TOMBSTONED
    tombstone = provider.get_state(tenant)
    provider.record_state(replace(tombstone, security_epoch=7, revocation_floor=7, digest=""))
    assert provider.get_state(tenant).generation_id == tombstone.generation_id
    assert provider.get_state(tenant).revocation_floor == 7
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    manifest = await prepare_offline_recovery(restored, provider, profile_path=profile)
    approvals = sign(manifest, keys)
    assert set(approvals) == {"security", "operator"}
    before = await no_effect_counts(restored)
    registry = tracking.InFlightExecutionRegistry.get_instance()
    original = RestoreReconciliationEngine.reconcile_post_restore
    callbacks = []

    def unconfirmed():
        callbacks.append("unconfirmed")
        return False

    async def observe_late_work(self, *args, **kwargs):
        assert recovery_receipt(profile, manifest.request_id) == (("CONSUMED",), ("CONSUMED",))
        try:
            await registry.register(
                "uncertain-execution", tenant, "component-test", terminate_callback=unconfirmed
            )
        except PermissionError:
            assert callbacks == ["unconfirmed"]
            assert registry.has_unresolved(tenant)
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(RestoreReconciliationEngine, "reconcile_post_restore", observe_late_work)
    with pytest.raises(RestoreReconciliationError, match="Containment unconfirmed"):
        await execute_offline_recovery(
            restored,
            provider,
            gate,
            profile_path=profile,
            manifest=manifest,
            signatures=approvals,
        )
    assert registry.has_unresolved(tenant)
    assert list(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))
    assert callbacks == ["unconfirmed"]
    assert not gate.is_admitted()
    assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    assert await no_effect_counts(restored) == before


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
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_tombstone_reconciliation_handles_real_approval_request_fk(
    qualified_target, tmp_path, request
):
    report = await approval_fk_restore_scenario(
        qualified_target, tmp_path, request, minimum_floor=7
    )
    assert report.status == "RECONCILED"
