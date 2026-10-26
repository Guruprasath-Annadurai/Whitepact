# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Codex Fortress objectives under founder-approved nonproduction signed recovery.

No production recovery implementation or internal authorization context is
changed. Genuine signed disposable installation and operator identities are
nonproduction qualification fixtures, not production enrollment evidence.
"""

import base64
import hashlib
import json
import os
import sqlite3
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from scripts.engineering import m13_floor_repair_poc as floor_repair
from sqlalchemy import insert, text
from sqlalchemy.exc import IntegrityError

from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
    SqliteDurableLifecycleStateProvider,
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
from responsibleai.db.engine import create_engine, governance_approvals, runtime_execution_requests
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.isolation import in_flight as tracking
from tests.stage3_freshness_setup import provision_freshness_tenant
from tests.stage3_restore_transport import fence_restore_incident, postgres_snapshot
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_operator_recovery_postgres import sign


@pytest.fixture
async def qualified_target(real_recovery, monkeypatch, tmp_path):
    engine, provider, gate, profile, keys = real_recovery
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "codex-tracking")
    monkeypatch.setattr(
        tracking.InFlightExecutionRegistry, "_instance", tracking.InFlightExecutionRegistry()
    )
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    try:
        _, tenant, _, _ = await provision_freshness_tenant(engine, provider)
        assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 1
        assert not os.environ.get("WHITEPACT_ALLOW_UNISOLATED_EXECUTION")
        yield engine, provider, gate, profile, keys, tenant
    finally:
        set_restore_readiness_gate(previous)


async def no_effect_counts(engine):
    tables = (
        "governance_execution_authorizations",
        "governance_root_authority_records",
        "runtime_execution_attempts",
        "runtime_execution_dispatch_outbox",
        "governance_outcomes",
    )
    async with engine.raw.connect() as connection:
        result = {
            table: await connection.scalar(text(f"SELECT count(*) FROM {table}"))
            for table in tables
        }
    assert set(result.values()) == {0}
    return result


def recovery_receipt(profile, request_id):
    path = json.loads(profile.read_text())["ledger_path"]
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        receipt = connection.execute(
            "SELECT state FROM recovery_receipts WHERE request_id=?", (request_id,)
        ).fetchone()
        operation = connection.execute(
            "SELECT phase FROM recovery_operations WHERE request_id=?", (request_id,)
        ).fetchone()
    return receipt, operation


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_active_floor_is_reconciled_after_real_postgres_restore(
    qualified_target, tmp_path, request
):
    """Required historical ACTIVE repair objective: do not relabel refusal PASS."""
    engine, provider, gate, profile, keys, tenant = qualified_target
    epochs = RevocationEpochRepository(engine)
    await epochs.bump(tenant)
    await epochs.bump(tenant)
    assert (await epochs.current(tenant)).epoch == 3
    archive = tmp_path / "active-epoch-three.dump"
    await postgres_snapshot(engine, archive)
    archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    for _ in range(4):
        await epochs.bump(tenant)
    established = provider.get_state(tenant)
    provider.record_state(replace(established, security_epoch=7, revocation_floor=7, digest=""))
    assert (await epochs.current(tenant)).epoch == 7
    # Retain independent, signed evidence before Store A is rolled back.
    floor_repair.initialize(profile)
    witness = await floor_repair.witness(engine, provider, profile_path=profile, tenant=tenant)
    floor_repair.retain_witness(
        profile,
        witness,
        {
            name: base64.b64encode(
                key.sign(floor_repair.ANCHOR_DOMAIN + floor_repair._bytes(witness))
            ).decode()
            for name, key in keys.items()
        },
    )
    await fence_restore_incident(engine, provider, profile)
    url = engine.raw.url.render_as_string(hide_password=False)
    await engine.close()
    await postgres_snapshot(engine, archive, restore=True, provider=provider)
    restored = create_engine(url)
    current_b = SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    restored_gate = RestoreReadinessGate(provider=current_b, db_engine=restored)
    try:
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_digest
        assert current_b.get_state(tenant).generation_id == established.generation_id
        assert current_b.get_state(tenant).revocation_floor == 7
        assert (await RevocationEpochRepository(restored).current(tenant)).epoch == 3
        before = await no_effect_counts(restored)
        with pytest.raises(RestoreQuarantineError):
            await restored_gate.assert_current_traffic_admitted()
        request.node.user_properties.extend(
            [
                ("snapshot_digest", archive_digest),
                ("restored_epoch", "3"),
                ("authoritative_floor", "7"),
            ]
        )
        with pytest.raises(RecoveryAuthorizationError, match="completion evidence") as denied:
            await prepare_offline_recovery(restored, current_b, profile_path=profile)
        assert await no_effect_counts(restored) == before
        assert not restored_gate.is_admitted()
        assert (await RevocationEpochRepository(restored).current(tenant)).epoch == 3
        request.node.user_properties.append(("pre_repair_denial", str(denied.value)))
        plan = await floor_repair.prepare(restored, current_b, profile_path=profile, tenant=tenant)
        result = await floor_repair.execute(
            restored,
            current_b,
            profile_path=profile,
            plan=plan,
            signatures={
                name: base64.b64encode(key.sign(plan.canonical_bytes())).decode()
                for name, key in keys.items()
            },
        )
        assert result == {"state": "FLOOR_ADVANCED", "epoch": 7, "ready": False}
        assert not restored_gate.is_admitted()
        assert current_b.get_state(tenant).generation_id == established.generation_id
        assert current_b.get_state(tenant).revocation_floor == 7
        assert (await RevocationEpochRepository(restored).current(tenant)).epoch == 7
        assert await no_effect_counts(restored) == before
        manifest = await prepare_offline_recovery(restored, current_b, profile_path=profile)
        report = await execute_offline_recovery(
            restored,
            current_b,
            restored_gate,
            profile_path=profile,
            manifest=manifest,
            signatures=sign(manifest, keys),
        )
        assert report.status == "RECONCILED"
        assert (await RevocationEpochRepository(restored).current(tenant)).epoch >= 7
        assert await no_effect_counts(restored) == before
    finally:
        await restored.close()


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
@pytest.mark.parametrize("point", ["after_approval", "during_recovery"])
async def test_late_unconfirmed_containment_never_restores_admission(
    qualified_target, monkeypatch, point, request
):
    engine, provider, gate, profile, keys, tenant = qualified_target
    await TenantDeletionOrchestrator(engine, provider).delete_tenant(
        tenant, deleted_by="disposable-test-controller", reason="codex-late-discovery"
    )
    assert provider.get_state(tenant).state == LifecycleState.TOMBSTONED
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile)
    signatures = sign(manifest, keys)
    assert set(signatures) == {"security", "operator"}
    signed_bytes = manifest.canonical_bytes()
    registry = tracking.InFlightExecutionRegistry.get_instance()
    before = await no_effect_counts(engine)
    callbacks = []

    def unconfirmed():
        callbacks.append("termination-unconfirmed")
        return False

    async def discover():
        # Environmental late-discovery injection, not a new authorized execution
        # or a claim of physical Docker termination. Do not mint a grant.
        try:
            await registry.register(
                "late-discovered-fixture",
                tenant,
                "structural-test-only",
                terminate_callback=unconfirmed,
            )
        except PermissionError:
            # Integrated deletion now fences stale late registration itself.
            # Its real callback must still have failed and tracking must remain;
            # continue to challenge the unchanged signed recovery boundary.
            assert callbacks == ["termination-unconfirmed"]
            assert registry.has_unresolved(tenant)

    if point == "after_approval":
        await discover()
        assert await registry.terminate_in_flight(organization_id=tenant) == []
        expected = RecoveryAuthorizationError
        message = "In-flight execution tracking is unresolved"
    else:
        original = RestoreReconciliationEngine.reconcile_post_restore

        async def discovered_during_reconciliation(self, *args, **kwargs):
            # Observe the real controller's durable consumption; never create or
            # modify a session, receipt, signature or trust requirement.
            assert recovery_receipt(profile, manifest.request_id) == (("CONSUMED",), ("CONSUMED",))
            await discover()
            return await original(self, *args, **kwargs)

        monkeypatch.setattr(
            RestoreReconciliationEngine, "reconcile_post_restore", discovered_during_reconciliation
        )
        expected = RestoreReconciliationError
        message = "Containment unconfirmed"
    with pytest.raises(expected, match=message):
        await execute_offline_recovery(
            engine,
            provider,
            gate,
            profile_path=profile,
            manifest=manifest,
            signatures=signatures,
        )
    assert callbacks == ["termination-unconfirmed"]
    assert registry.has_unresolved(tenant)
    assert list(tracking._DISTRIBUTED_REGISTRY_DIR.glob("*.json"))
    assert manifest.canonical_bytes() == signed_bytes
    assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    assert not gate.is_admitted()
    assert await no_effect_counts(engine) == before
    receipt, operation = recovery_receipt(profile, manifest.request_id)
    if point == "during_recovery":
        assert receipt == ("CONSUMED",)
        assert operation != ("COMPLETE",)
    else:
        assert receipt is None and operation is None
    with pytest.raises(RecoveryAuthorizationError):
        await execute_offline_recovery(
            engine,
            provider,
            gate,
            profile_path=profile,
            manifest=manifest,
            signatures=signatures,
        )
    assert registry.has_unresolved(tenant)
    assert await no_effect_counts(engine) == before
    request.node.user_properties.extend(
        [
            ("recovery_request", manifest.request_id),
            ("late_discovery_point", point),
            ("receipt", json.dumps(receipt)),
            ("operation", json.dumps(operation)),
        ]
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_approval_fk_survives_real_backup_restore_and_signed_recovery(
    qualified_target, tmp_path, request
):
    report = await approval_fk_restore_scenario(qualified_target, tmp_path, request)
    assert report.status == "RECONCILED"


async def approval_fk_restore_scenario(qualified_target, tmp_path, request, *, minimum_floor=None):
    """Shared real restore transport; every original FK/evidence assertion remains active."""
    engine, provider, gate, profile, keys, tenant = qualified_target
    now = datetime.now(UTC)
    async with engine.raw.begin() as connection:
        await connection.execute(
            insert(governance_approvals).values(
                id="codex-original-approval",
                org_id=tenant,
                action_id="action",
                action_type="test",
                target="harmless",
                reason_codes="[]",
                status="PENDING",
                requested_at=now.isoformat(),
            )
        )
        await connection.execute(
            insert(runtime_execution_requests).values(
                request_id="codex-original-request",
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
                observed_governance_epoch=1,
                idempotency_key="codex-original-request",
                approval_id="codex-original-approval",
                created_at=now,
            )
        )
        original_request = dict(
            (
                await connection.execute(
                    text(
                        "SELECT * FROM runtime_execution_requests WHERE request_id='codex-original-request'"
                    )
                )
            )
            .mappings()
            .one()
        )
    archive = tmp_path / "original-approval-fk.dump"
    await postgres_snapshot(engine, archive)
    archive_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    request.node.user_properties.append(("snapshot_digest", archive_digest))
    before = await no_effect_counts(engine)
    try:
        await TenantDeletionOrchestrator(engine, provider).delete_tenant(
            tenant, deleted_by="disposable-test-controller", reason="codex-real-fk-restore"
        )
    except IntegrityError as exc:
        # Retain a genuine prerequisite failure. Never remove immutable request
        # evidence or its FK merely to make the later restore executable.
        request.node.user_properties.append(
            ("deletion_sqlstate", getattr(exc.orig, "sqlstate", "unknown"))
        )
        assert await no_effect_counts(engine) == before
        async with engine.raw.connect() as connection:
            assert (
                dict(
                    (
                        await connection.execute(
                            text(
                                "SELECT * FROM runtime_execution_requests WHERE request_id='codex-original-request'"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                == original_request
            )
            with pytest.raises(ProvisioningAuthorizationError):
                await verify_tenant_completion_evidence(connection, tenant, 1, provider)
        raise
    tombstone = provider.get_state(tenant)
    assert tombstone.state == LifecycleState.TOMBSTONED
    if minimum_floor is not None:
        provider.record_state(
            replace(
                tombstone,
                security_epoch=max(tombstone.security_epoch, minimum_floor),
                revocation_floor=max(tombstone.revocation_floor, minimum_floor),
                digest="",
            )
        )
        tombstone = provider.get_state(tenant)
        assert tombstone.revocation_floor >= minimum_floor
    await fence_restore_incident(engine, provider, profile)
    url = engine.raw.url.render_as_string(hide_password=False)
    await engine.close()
    await postgres_snapshot(engine, archive, restore=True, provider=provider)
    restored = create_engine(url)
    current_b = SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    restored_gate = RestoreReadinessGate(provider=current_b, db_engine=restored)
    try:
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == archive_digest
        assert current_b.get_state(tenant) == tombstone
        async with restored.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text(
                        "SELECT status FROM governance_approvals WHERE id='codex-original-approval'"
                    )
                )
                == "PENDING"
            )
            assert (
                dict(
                    (
                        await connection.execute(
                            text(
                                "SELECT * FROM runtime_execution_requests WHERE request_id='codex-original-request'"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                == original_request
            )
        manifest = await prepare_offline_recovery(restored, current_b, profile_path=profile)
        report = await execute_offline_recovery(
            restored,
            current_b,
            restored_gate,
            profile_path=profile,
            manifest=manifest,
            signatures=sign(manifest, keys),
        )
        assert report.status == "RECONCILED"
        assert restored_gate.is_admitted()
        assert current_b.get_state(tenant) == tombstone
        # Authorization stays permanently consumed; completion is a distinct
        # operation phase, not a reusable authorization receipt.
        assert recovery_receipt(profile, manifest.request_id) == (("CONSUMED",), ("COMPLETE",))
        async with restored.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text(
                        "SELECT status FROM governance_approvals WHERE id='codex-original-approval'"
                    )
                )
                == "REVOKED"
            )
            assert (
                dict(
                    (
                        await connection.execute(
                            text(
                                "SELECT * FROM runtime_execution_requests WHERE request_id='codex-original-request'"
                            )
                        )
                    )
                    .mappings()
                    .one()
                )
                == original_request
            )
            with pytest.raises(ProvisioningAuthorizationError):
                await verify_tenant_completion_evidence(connection, tenant, 1, current_b)
        assert await no_effect_counts(restored) == before
        return report
    finally:
        await restored.close()
