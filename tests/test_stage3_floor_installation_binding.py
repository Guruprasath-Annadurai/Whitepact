# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable installation-receipt attacks against the isolated floor operation."""

import json
import sqlite3
from pathlib import Path

import pytest
from scripts.engineering import m13_floor_repair_poc as poc
from scripts.engineering.m13_bootstrap_authorization import BootstrapRefusedError, _profile
from scripts.engineering.m13_bootstrap_publication import publication_profile

from responsibleai.data_governance.backup_defense import RestoreQuarantineError
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from tests.test_codex_fortress_recovery_qualification import no_effect_counts
from tests.test_final_floor_repair_poc import floor_target as floor_target
from tests.test_final_floor_repair_poc import qualified_target as qualified_target
from tests.test_final_floor_repair_poc import real_recovery as real_recovery
from tests.test_final_floor_repair_poc import signatures

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True),
]


def corrupt_receipt(provider, fault):
    # Fault injection is confined to disposable qualification records. Never
    # create ACTIVE state, change tenant generation or alter recovery trust.
    with sqlite3.connect(provider.path, timeout=0) as connection:
        binding = connection.execute(
            "SELECT profile_path FROM bootstrap_installation_binding WHERE id=1"
        ).fetchone()
        if fault == "missing_binding":
            connection.execute("DELETE FROM bootstrap_installation_binding WHERE id=1")
        elif fault == "changed_binding":
            connection.execute(
                "UPDATE bootstrap_installation_binding SET digest=? WHERE id=1", ("0" * 64,)
            )
    if fault in {"missing_completion", "changed_deployment", "missing_registry"}:
        publication = publication_profile(binding[0])
        authorization = _profile(publication["authorization_profile"])
        if fault == "missing_completion":
            with sqlite3.connect(authorization["registry"]) as connection:
                connection.execute("DELETE FROM bootstrap_publication WHERE id=1")
        elif fault == "changed_deployment":
            path = Path(publication["authorization_profile"])
            authorization["deployment_id"] = "another-installation-target"
            path.write_text(json.dumps(authorization))
        else:
            path = Path(authorization["registry"])
            path.rename(path.with_suffix(".unavailable"))


@pytest.mark.parametrize(
    "fault",
    [
        "missing_binding",
        "changed_binding",
        "missing_completion",
        "changed_deployment",
        "missing_registry",
    ],
)
async def test_floor_prepare_requires_verified_installation_receipt(floor_target, fault):
    engine, provider, gate, profile, keys, tenant = floor_target
    before = await no_effect_counts(engine)
    corrupt_receipt(provider, fault)
    with pytest.raises(RecoveryAuthorizationError, match="installation"):
        await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
    assert provider.get_state(tenant).revocation_floor == 7
    assert await no_effect_counts(engine) == before
    with pytest.raises((RestoreQuarantineError, BootstrapRefusedError, RecoveryAuthorizationError)):
        await gate.assert_current_traffic_admitted()


async def test_installation_receipt_changed_after_approval_burns_plan_without_advancement(
    floor_target,
):
    engine, provider, gate, profile, keys, tenant = floor_target
    plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    approved = signatures(plan.canonical_bytes(), keys)
    signed = plan.canonical_bytes()
    before = await no_effect_counts(engine)
    corrupt_receipt(provider, "changed_binding")
    try:
        await poc.execute(engine, provider, profile_path=profile, plan=plan, signatures=approved)
    except RecoveryAuthorizationError as error:
        assert "installation" in str(error)
    else:
        epoch = (await RevocationEpochRepository(engine).current(tenant)).epoch
        pytest.fail(f"Changed installation receipt accepted; observed epoch={epoch}")
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
    assert provider.get_state(tenant).revocation_floor == 7
    assert plan.canonical_bytes() == signed
    assert await no_effect_counts(engine) == before
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        await poc.execute(engine, provider, profile_path=profile, plan=plan, signatures=approved)


async def test_floor_witness_requires_verified_installation_receipt(qualified_target):
    engine, provider, gate, profile, keys, tenant = qualified_target
    before = await no_effect_counts(engine)
    corrupt_receipt(provider, "missing_binding")
    with pytest.raises(RecoveryAuthorizationError, match="installation"):
        await poc.witness(engine, provider, profile_path=profile, tenant=tenant)
    assert await no_effect_counts(engine) == before


async def test_v1_floor_domains_cannot_authorize_v2_installation_bound_operation(floor_target):
    engine, provider, gate, profile, keys, tenant = floor_target
    ledger = Path(json.loads(profile.read_text())["ledger_path"]).with_suffix(".floor-poc.sqlite3")
    with sqlite3.connect(ledger) as connection:
        payload = json.loads(
            connection.execute(
                "SELECT payload FROM floor_witness WHERE tenant=?", (tenant,)
            ).fetchone()[0]
        )
    assert len(payload["installation"]["installation_id"]) == 64
    legacy_anchor = b"WHITEPACT-M13-NONPRODUCTION-FLOOR-WITNESS-V1\0" + poc._bytes(payload)
    with pytest.raises(RecoveryAuthorizationError, match="Invalid floor approval"):
        poc.retain_witness(profile, payload, signatures(legacy_anchor, keys))
    plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    legacy_plan = (
        b"WHITEPACT-M13-NONPRODUCTION-FLOOR-REPAIR-V1\0"
        + plan.canonical_bytes()[len(poc.PLAN_DOMAIN) :]
    )
    with pytest.raises(RecoveryAuthorizationError, match="Invalid floor approval"):
        await poc.execute(
            engine,
            provider,
            profile_path=profile,
            plan=plan,
            signatures=signatures(legacy_plan, keys),
        )
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
    assert provider.get_state(tenant).revocation_floor == 7
    await no_effect_counts(engine)


@pytest.mark.parametrize("fault", ["installation", "expired", "revoked_operator"])
async def test_floor_rechecks_authority_immediately_before_epoch_cas(
    floor_target, monkeypatch, fault
):
    engine, provider, gate, profile, keys, tenant = floor_target
    plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    approved = signatures(plan.canonical_bytes(), keys)
    original = poc._evidence

    async def change_after_observation(*args, **kwargs):
        evidence = await original(*args, **kwargs)
        if fault == "installation":
            # The Store B lock already blocks direct writes here. Challenge
            # the independently held publication receipt instead.
            corrupt_receipt(provider, "missing_completion")
        elif fault == "expired":
            monkeypatch.setattr(poc.time, "time", lambda: plan.expires_at + 1)
        else:
            content = json.loads(profile.read_text())
            content["keys"][0]["revoked"] = True
            profile.write_text(json.dumps(content))
        return evidence

    monkeypatch.setattr(poc, "_evidence", change_after_observation)
    with pytest.raises(RecoveryAuthorizationError):
        await poc.execute(engine, provider, profile_path=profile, plan=plan, signatures=approved)
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
    assert provider.get_state(tenant).revocation_floor == 7
    await no_effect_counts(engine)


async def test_store_b_lock_blocks_intermediate_binding_write(floor_target, monkeypatch):
    engine, provider, gate, profile, keys, tenant = floor_target
    plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    original = poc._evidence
    reached = []

    async def attempt_write(*args, **kwargs):
        evidence = await original(*args, **kwargs)
        reached.append("protected-observation-complete")
        corrupt_receipt(provider, "changed_binding")
        return evidence

    monkeypatch.setattr(poc, "_evidence", attempt_write)
    with pytest.raises(sqlite3.OperationalError, match="database is locked"):
        await poc.execute(
            engine,
            provider,
            profile_path=profile,
            plan=plan,
            signatures=signatures(plan.canonical_bytes(), keys),
        )
    assert reached == ["protected-observation-complete"]
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 3
    assert provider.get_state(tenant).revocation_floor == 7
    await no_effect_counts(engine)


async def test_installation_loss_after_epoch_commit_never_reports_completion(
    floor_target, monkeypatch
):
    engine, provider, gate, profile, keys, tenant = floor_target
    plan = await poc.prepare(engine, provider, profile_path=profile, tenant=tenant)
    approved = signatures(plan.canonical_bytes(), keys)

    async def lose_receipt(phase):
        if phase == "PG_COMMITTED":
            corrupt_receipt(provider, "changed_binding")

    monkeypatch.setattr(poc, "_checkpoint", lose_receipt)
    with pytest.raises(RecoveryAuthorizationError, match="installation"):
        await poc.execute(engine, provider, profile_path=profile, plan=plan, signatures=approved)
    # Never lower an epoch committed while the authorization was valid.
    assert (await RevocationEpochRepository(engine).current(tenant)).epoch == 7
    assert provider.get_state(tenant).revocation_floor == 7
    ledger = Path(json.loads(profile.read_text())["ledger_path"]).with_suffix(".floor-poc.sqlite3")
    with sqlite3.connect(ledger) as connection:
        assert connection.execute(
            "SELECT state,final_digest FROM floor_attempts WHERE request_id=?", (plan.request_id,)
        ).fetchone() == ("FAILED", None)
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        await poc.execute(engine, provider, profile_path=profile, plan=plan, signatures=approved)
    await no_effect_counts(engine)
    with pytest.raises((RestoreQuarantineError, BootstrapRefusedError, RecoveryAuthorizationError)):
        await gate.assert_current_traffic_admitted()
