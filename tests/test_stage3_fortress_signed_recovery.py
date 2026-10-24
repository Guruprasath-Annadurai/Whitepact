# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Separate durable R1 successors; never replace the original Fortress tests.

Disposable operator enrollment and component initial READY are not production
bootstrap/enrollment evidence. No internal recovery session is constructed here.
"""

from dataclasses import replace
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, text

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.data_governance.operator_recovery_control import (
    execute_offline_recovery,
    prepare_offline_recovery,
)
from responsibleai.data_governance.provisioning_manifest import ProvisioningAuthorizationError
from responsibleai.data_governance.tenant_admission import verify_tenant_completion_evidence
from responsibleai.db.engine import governance_approvals, runtime_execution_requests
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.isolation import in_flight as tracking
from tests.stage3_freshness_setup import provision_freshness_tenant
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_operator_recovery_postgres import sign


@pytest.fixture
async def established(real_recovery, monkeypatch, tmp_path):
    engine, provider, gate, profile, keys = real_recovery
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    monkeypatch.setattr(
        tracking.InFlightExecutionRegistry, "_instance", tracking.InFlightExecutionRegistry()
    )
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    try:
        _, tenant, _, _ = await provision_freshness_tenant(engine, provider)
        assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 1
        yield engine, provider, gate, profile, keys, tenant
    finally:
        set_restore_readiness_gate(previous)


async def authority_counts(engine):
    # None of these scenarios is permitted to issue a grant/root or tool effect.
    tables = (
        "governance_execution_authorizations",
        "governance_root_authority_records",
        "runtime_execution_attempts",
        "runtime_execution_dispatch_outbox",
        "governance_outcomes",
    )
    async with engine.raw.connect() as conn:
        return {table: await conn.scalar(text(f"SELECT count(*) FROM {table}")) for table in tables}


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
@pytest.mark.parametrize("consistent", [True, False], ids=["intact-floor", "stale-epoch"])
async def test_fortress_r1_authoritative_floor(established, consistent, request):
    engine, provider, gate, profile, keys, tenant = established
    epochs = RevocationEpochRepository(engine)
    if consistent:
        for _ in range(6):
            await epochs.bump(tenant)
    original = provider.get_state(tenant)
    provider.record_state(replace(original, security_epoch=7, revocation_floor=7, digest=""))
    assert provider.get_state(tenant).generation_id == original.generation_id
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    before = await authority_counts(engine)
    if not consistent:
        with pytest.raises(
            RecoveryAuthorizationError, match="Active tenant completion evidence is unverified"
        ):
            await prepare_offline_recovery(engine, provider, profile_path=profile)
        assert (await epochs.current(tenant)).epoch == 1
        assert not gate.is_admitted()
    else:
        manifest = await prepare_offline_recovery(engine, provider, profile_path=profile)
        signatures = sign(manifest, keys)
        assert set(signatures) == {"security", "operator"}
        report = await execute_offline_recovery(
            engine,
            provider,
            gate,
            profile_path=profile,
            manifest=manifest,
            signatures=signatures,
        )
        assert report.status == "RECONCILED"
        assert (await epochs.current(tenant)).epoch >= 7
        await gate.assert_current_traffic_admitted()
        assert provider.get_state(tenant).revocation_floor == 7
        request.node.user_properties.append(("signed_request", manifest.request_id))
    assert await authority_counts(engine) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_fortress_r1_unconfirmed_termination_blocks_prepare(established):
    engine, provider, gate, profile, _, tenant = established
    registry = tracking.InFlightExecutionRegistry.get_instance()
    calls = []

    def unconfirmed():
        calls.append("attempted")
        return False

    await registry.register(
        "fortress-uncertain", tenant, "component-only", terminate_callback=unconfirmed
    )
    assert await registry.terminate_in_flight(organization_id=tenant) == []
    assert calls == ["attempted"]
    assert registry.has_unresolved(tenant)
    evidence = {p.name: p.read_bytes() for p in tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json")}
    assert evidence
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    before = await authority_counts(engine)
    with pytest.raises(
        RecoveryAuthorizationError, match="In-flight execution tracking is unresolved"
    ):
        await prepare_offline_recovery(engine, provider, profile_path=profile)
    assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    assert not gate.is_admitted()
    assert registry.has_unresolved(tenant)
    assert {
        p.name: p.read_bytes() for p in tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json")
    } == evidence
    assert await authority_counts(engine) == before


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_fortress_r1_tombstone_real_approval_fk(established, request):
    engine, provider, gate, profile, keys, tenant = established
    generation = provider.get_state(tenant).generation_id
    await TenantDeletionOrchestrator(engine, provider).delete_tenant(
        tenant, deleted_by="isolated-fixture-controller", reason="fortress-successor"
    )
    tombstone = provider.get_state(tenant)
    assert tombstone.state == LifecycleState.TOMBSTONED
    assert tombstone.generation_id == generation
    # Targeted restoration of stale operational records in a disposable DB.
    # This is not a full backup/restore or genuine execution-attempt receipt.
    now = datetime.now(UTC)
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(governance_approvals).values(
                id="fortress-approval",
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
                request_id="fortress-request",
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
                idempotency_key="fortress-request",
                approval_id="fortress-approval",
                created_at=now,
            )
        )
        assert (
            await conn.scalar(
                text(
                    "SELECT count(*) FROM runtime_execution_requests r JOIN governance_approvals a "
                    "ON r.approval_id=a.id WHERE r.organization_id=:tenant"
                ),
                {"tenant": tenant},
            )
            == 1
        )
        original_request = dict(
            (
                await conn.execute(
                    text(
                        "SELECT * FROM runtime_execution_requests WHERE request_id='fortress-request'"
                    )
                )
            )
            .mappings()
            .one()
        )
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    before = await authority_counts(engine)
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile)
    report = await execute_offline_recovery(
        engine,
        provider,
        gate,
        profile_path=profile,
        manifest=manifest,
        signatures=sign(manifest, keys),
    )
    assert report.status == "RECONCILED"
    assert provider.get_state(tenant) == tombstone
    async with engine.raw.connect() as conn:
        assert (
            await conn.scalar(
                text("SELECT status FROM governance_approvals WHERE org_id=:tenant"),
                {"tenant": tenant},
            )
            == "REVOKED"
        )
        assert (
            await conn.scalar(
                text(
                    "SELECT count(*) FROM runtime_execution_requests WHERE organization_id=:tenant"
                ),
                {"tenant": tenant},
            )
            == 1
        )
        assert (
            dict(
                (
                    await conn.execute(
                        text(
                            "SELECT * FROM runtime_execution_requests WHERE request_id='fortress-request'"
                        )
                    )
                )
                .mappings()
                .one()
            )
            == original_request
        )
        assert (
            await conn.scalar(
                text("SELECT governance_status FROM organizations WHERE id=:tenant"),
                {"tenant": tenant},
            )
            == "DISABLED"
        )
        epoch = (await RevocationEpochRepository(engine).current(tenant)).epoch
        with pytest.raises(ProvisioningAuthorizationError):
            await verify_tenant_completion_evidence(conn, tenant, epoch, provider)
    assert await authority_counts(engine) == before
    await gate.assert_current_traffic_admitted()
    request.node.user_properties.append(("signed_request", manifest.request_id))


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_fortress_direct_engine_denial_no_authority_or_effect(established):
    engine, provider, gate, _, _, _ = established
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    before = await authority_counts(engine)
    with pytest.raises(
        RecoveryAuthorizationError, match="Verified offline operator recovery session required"
    ):
        await RestoreReconciliationEngine(
            engine, lifecycle_provider=provider, gate=gate, require_durable=True
        ).reconcile_post_restore("claimed-security-owner")
    assert await authority_counts(engine) == before
    async with engine.raw.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM restore_reconciliation_records")) == 0
    assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    assert not gate.is_admitted()
