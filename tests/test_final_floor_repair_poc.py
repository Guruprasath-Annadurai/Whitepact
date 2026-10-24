# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable floor experiment, NOT production enrollment or bootstrap proof."""

import asyncio
import base64
import json
import multiprocessing
import os
import secrets
import sqlite3
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from scripts.engineering import m13_floor_repair_poc as poc
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.data_governance.operator_recovery_control import (
    execute_offline_recovery,
    prepare_offline_recovery,
)
from responsibleai.data_governance.provisioning_manifest import ProvisioningAuthorizationError
from responsibleai.db.engine import create_engine
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from tests.stage3_restore_transport import fence_restore_incident, postgres_snapshot
from tests.test_codex_fortress_recovery_qualification import (
    no_effect_counts,
)
from tests.test_codex_fortress_recovery_qualification import (
    qualified_target as qualified_target,
)
from tests.test_codex_fortress_recovery_qualification import (
    real_recovery as real_recovery,
)
from tests.test_operator_recovery_postgres import sign

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True),
]


def signatures(payload, keys):
    return {name: base64.b64encode(key.sign(payload)).decode() for name, key in keys.items()}


@pytest.fixture
async def floor_target(qualified_target, tmp_path):
    engine, provider, gate, profile, keys, tenant = qualified_target
    epochs = RevocationEpochRepository(engine)
    for _ in range(2):
        await epochs.bump(tenant)
    archive = tmp_path / "floor-three.dump"
    await postgres_snapshot(engine, archive)
    for _ in range(4):
        await epochs.bump(tenant)
    lifecycle = provider.get_state(tenant)
    provider.record_state(replace(lifecycle, security_epoch=7, revocation_floor=7, digest=""))
    poc.initialize(profile)
    witness = await poc.witness(engine, provider, profile_path=profile, tenant=tenant)
    poc.retain_witness(profile, witness, signatures(poc.ANCHOR_DOMAIN + poc._bytes(witness), keys))
    await fence_restore_incident(engine, provider, profile)
    url = engine.raw.url.render_as_string(hide_password=False)
    await engine.close()
    await postgres_snapshot(engine, archive, restore=True, provider=provider)
    restored = create_engine(url)
    current_b = SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    current_gate = RestoreReadinessGate(provider=current_b, db_engine=restored)
    try:
        assert (await RevocationEpochRepository(restored).current(tenant)).epoch == 3
        assert current_b.get_state(tenant).revocation_floor == 7
        assert not current_gate.is_admitted()
        yield restored, current_b, current_gate, profile, keys, tenant
    finally:
        await restored.close()


async def test_separate_floor_poc_then_unchanged_signed_r1(floor_target):
    engine, provider, gate, profile, keys, tenant = floor_target
    with pytest.raises(RecoveryAuthorizationError, match="completion evidence"):
        await prepare_offline_recovery(engine, provider, profile_path=profile)
    before = await no_effect_counts(engine)
    plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    result = await poc.execute(
        engine,
        provider,
        profile_path=profile,
        plan=plan,
        signatures=signatures(plan.canonical_bytes(), keys),
    )
    assert result == {"state": "FLOOR_ADVANCED", "epoch": 7, "ready": False}
    assert not gate.is_admitted()
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 7
    assert provider.get_state(tenant).revocation_floor == 7
    assert await no_effect_counts(engine) == before
    ledger = Path(json.loads(profile.read_text())["ledger_path"]).with_suffix(".floor-poc.sqlite3")
    with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT state,details,final_digest FROM floor_attempts WHERE request_id=?",
            (plan.request_id,),
        ).fetchone()
    assert row[0] == "COMPLETE"
    assert json.loads(row[1]) == {
        "plan": asdict(plan),
        "signatures": signatures(plan.canonical_bytes(), keys),
    }
    assert len(row[2]) == 64
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        await poc.execute(
            engine,
            provider,
            profile_path=profile,
            plan=plan,
            signatures=signatures(plan.canonical_bytes(), keys),
        )
    # A separate, genuinely signed ordinary R1 operation remains mandatory.
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
    assert gate.is_admitted()
    assert await no_effect_counts(engine) == before


async def test_forged_expired_wrong_binding_and_replay_never_advance(floor_target):
    engine, provider, gate, profile, keys, tenant = floor_target
    cases = [
        ({"generation": "wrong-generation"}, False, "Exact floor binding"),
        ({"expected_epoch": 2}, False, "Exact floor binding"),
        ({"evidence_digest": "0" * 64}, False, "Signed floor evidence changed"),
        ({"created_at": 1, "expires_at": 2}, False, "Stale or wrong-target"),
        ({"profile_digest": "0" * 64}, False, "Stale or wrong-target"),
        ({}, True, "Invalid floor approval"),
    ]
    for changes, forged, error in cases:
        plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
        candidate = replace(
            plan, nonce=secrets.token_hex(32), request_id=secrets.token_hex(32), **changes
        )
        approved = signatures(candidate.canonical_bytes(), keys)
        if forged:
            approved["operator"] = approved["security"]
        with pytest.raises(RecoveryAuthorizationError, match=error):
            await poc.execute(
                engine, provider, profile_path=profile, plan=candidate, signatures=approved
            )
        with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
            await poc.execute(
                engine, provider, profile_path=profile, plan=candidate, signatures=approved
            )
        assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
        assert not gate.is_admitted()
        await no_effect_counts(engine)


@pytest.mark.parametrize(
    "fault",
    [
        "missing_witness",
        "tampered_witness",
        "incomplete_provisioning",
        "revoked_key",
        "missing_store_b",
    ],
)
async def test_non_epoch_evidence_failures_cannot_be_repaired(floor_target, fault, request):
    engine, provider, gate, profile, keys, tenant = floor_target
    valid = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    assert valid.expected_epoch == 3 and valid.target_epoch == 7
    ledger = Path(json.loads(profile.read_text())["ledger_path"]).with_suffix(".floor-poc.sqlite3")
    moved = None
    if fault == "missing_witness":
        with sqlite3.connect(ledger) as connection:
            connection.execute("DELETE FROM floor_witness WHERE tenant=?", (tenant,))
    elif fault == "tampered_witness":
        with sqlite3.connect(ledger) as connection:
            row = connection.execute(
                "SELECT payload FROM floor_witness WHERE tenant=?", (tenant,)
            ).fetchone()
            payload = json.loads(row[0])
            payload["floor"] = 8
            connection.execute(
                "UPDATE floor_witness SET payload=? WHERE tenant=?", (json.dumps(payload), tenant)
            )
    elif fault == "incomplete_provisioning":
        # Real PostgreSQL refuses this fault before it can be introduced.
        # Do not disable the guard or represent this as downstream repair proof.
        with pytest.raises(DBAPIError, match="Protected tenant controller required"):
            async with engine.raw.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE tenant_provisioning_records SET completion_digest=:digest WHERE tenant_id=:id"
                    ),
                    {"digest": "0" * 64, "id": tenant},
                )
        request.node.user_properties.append(
            ("refusal_boundary", "PostgreSQL protected provisioning trigger; not downstream repair")
        )
        assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
        assert not gate.is_admitted()
        await no_effect_counts(engine)
        return
    elif fault == "revoked_key":
        content = json.loads(profile.read_text())
        content["keys"][0]["revoked"] = True
        profile.write_text(json.dumps(content))
    else:
        moved = provider.path.with_suffix(".unavailable")
        provider.path.rename(moved)
    try:
        with pytest.raises((RecoveryAuthorizationError, ProvisioningAuthorizationError, OSError)):
            await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
        assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
        assert not gate.is_admitted()
        await no_effect_counts(engine)
    finally:
        if moved is not None:
            moved.rename(provider.path)


async def test_unknown_work_blocks_floor_operation(floor_target):
    engine, provider, gate, profile, keys, tenant = floor_target
    registry = InFlightExecutionRegistry.get_instance()
    await registry.register(
        "floor-unresolved", tenant, "harmless", admission_epoch=1, terminate_callback=lambda: False
    )
    with pytest.raises(RecoveryAuthorizationError, match="Unresolved work"):
        await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    assert await registry.terminate_in_flight(organization_id=tenant) == []
    assert registry.has_unresolved(tenant)
    assert not gate.is_admitted()
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
    await no_effect_counts(engine)


async def test_concurrent_floor_operation_is_denied(floor_target, monkeypatch):
    engine, provider, gate, profile, keys, tenant = floor_target
    first = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    second = replace(first, nonce=secrets.token_hex(32), request_id=secrets.token_hex(32))
    reached, release = asyncio.Event(), asyncio.Event()

    async def pause(phase):
        if phase == "CONSUMED":
            reached.set()
            await release.wait()

    monkeypatch.setattr(poc, "_checkpoint", pause)
    operation = asyncio.create_task(
        poc.execute(
            engine,
            provider,
            profile_path=profile,
            plan=first,
            signatures=signatures(first.canonical_bytes(), keys),
        )
    )
    try:
        await asyncio.wait_for(reached.wait(), 10)
        with pytest.raises(BlockingIOError):
            await poc.execute(
                engine,
                provider,
                profile_path=profile,
                plan=second,
                signatures=signatures(second.canonical_bytes(), keys),
            )
        assert not gate.is_admitted()
    finally:
        release.set()
        result = await operation
    assert result["ready"] is False
    await no_effect_counts(engine)


def _crash_repair(url, store_b, key, profile, plan_data, approved, phase):
    import asyncio

    os.environ["WHITEPACT_ENV"] = "staging"
    os.environ["WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG"] = profile
    os.environ.pop("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", None)

    async def stop_at(observed):
        if observed == phase:
            os._exit(23)

    async def run():
        engine = create_engine(url)
        provider = SqliteDurableLifecycleStateProvider(store_b, secret_key=key)
        poc._checkpoint = stop_at
        await poc.execute(
            engine,
            provider,
            profile_path=Path(profile),
            plan=poc.FloorPlan(**plan_data),
            signatures=approved,
        )

    asyncio.run(run())


@pytest.mark.parametrize("phase", ["CONSUMED", "PG_UNCOMMITTED", "PG_COMMITTED"])
async def test_real_floor_process_crash_keeps_quarantine_and_burns_approval(floor_target, phase):
    import asyncio

    engine, provider, gate, profile, keys, tenant = floor_target
    plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    approved = signatures(plan.canonical_bytes(), keys)
    context = multiprocessing.get_context("spawn")
    child = context.Process(
        target=_crash_repair,
        args=(
            engine.raw.url.render_as_string(hide_password=False),
            provider.path,
            provider._secret_key,
            str(profile),
            asdict(plan),
            approved,
            phase,
        ),
    )
    try:
        child.start()
        await asyncio.to_thread(child.join, 30)
        assert child.exitcode == 23
        assert (await RevocationEpochRepository(engine).current(tenant)).epoch == (
            7 if phase == "PG_COMMITTED" else 3
        )
        assert not gate.is_admitted()
        assert provider.get_state(tenant).revocation_floor == 7
        ledger = Path(json.loads(profile.read_text())["ledger_path"]).with_suffix(
            ".floor-poc.sqlite3"
        )
        with sqlite3.connect(f"file:{ledger}?mode=ro", uri=True) as connection:
            assert connection.execute(
                "SELECT state FROM floor_attempts WHERE request_id=?", (plan.request_id,)
            ).fetchone() == ("CONSUMED",)
        with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
            await poc.execute(
                engine, provider, profile_path=profile, plan=plan, signatures=approved
            )
        await no_effect_counts(engine)
    finally:
        if child.is_alive():
            child.terminate()
            await asyncio.to_thread(child.join, 10)
