# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fresh customer harness provisioning is not authorization to recover a failure."""

import os
import sqlite3

import pytest
from scripts.engineering.m13_bootstrap_customer_fixture import authorized_disposable_installation

from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
    StoreBUnavailableError,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from tests.test_stage3_bootstrap_store_preflight import fresh_target as fresh_target


def test_isolated_runtime_without_store_b_denies_initial_admission(monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    for key in (
        "WHITEPACT_ALLOW_UNISOLATED_EXECUTION",
        "WHITEPACT_STORE_B_PATH",
        "WHITEPACT_LIFECYCLE_STORE_PATH",
    ):
        monkeypatch.delenv(key, raising=False)
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.READY)
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.provider_error == "Hosted readiness requires the durable Store B provider"
    with pytest.raises(RestoreQuarantineError):
        gate.assert_traffic_admitted()


def test_fresh_harness_has_durable_store_b_but_cannot_clear_failure(monkeypatch):
    from scripts.engineering.m13_apex_customer_journey import isolated_startup_store_b

    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    original = get_restore_readiness_gate()
    try:
        with isolated_startup_store_b():
            gate = get_restore_readiness_gate()
            assert gate is not original
            assert gate.provider is not None
            assert gate.provider.verify_integrity()
            assert gate.provider.get_readiness_state() is None
            assert gate.state == RestoreReadinessState.RESTORE_PENDING
            gate.set_state(RestoreReadinessState.FAILED)
            with pytest.raises(RecoveryAuthorizationError):
                gate.set_state(RestoreReadinessState.READY)
            assert gate.state == RestoreReadinessState.FAILED
            restarted = RestoreReadinessGate(
                initial_state=RestoreReadinessState.READY,
                provider=SqliteDurableLifecycleStateProvider(gate.provider.path),
            )
            assert restarted.state == RestoreReadinessState.FAILED
            with pytest.raises(RestoreQuarantineError):
                restarted.assert_traffic_admitted()
        assert get_restore_readiness_gate() is original
    finally:
        set_restore_readiness_gate(original)


def test_harness_restores_prior_quarantine_and_environment_on_error(monkeypatch, tmp_path):
    from scripts.engineering.m13_apex_customer_journey import isolated_startup_store_b

    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    old = get_restore_readiness_gate()
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "original.sqlite3")
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    original = RestoreReadinessGate(provider=provider)
    set_restore_readiness_gate(original)
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(provider.path))
    try:
        with pytest.raises(RuntimeError, match="fixture stopped"):
            with isolated_startup_store_b():
                assert get_restore_readiness_gate().provider.path != provider.path
                raise RuntimeError("fixture stopped")
        assert os.environ["WHITEPACT_STORE_B_PATH"] == str(provider.path)
        assert get_restore_readiness_gate() is original
        assert original.state == RestoreReadinessState.FAILED
        assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    finally:
        set_restore_readiness_gate(old)


@pytest.mark.parametrize("damage", ["missing", "corrupt"])
@pytest.mark.asyncio
async def test_store_b_loss_after_initial_startup_never_reopens_admission(
    monkeypatch, tmp_path, damage, fresh_target
):
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    engine, provider, _, _ = fresh_target
    async with authorized_disposable_installation(
        engine, provider, deployment_id="startup-loss-fixture", environment="development"
    ):
        gate = RestoreReadinessGate(initial_state=RestoreReadinessState.READY, provider=provider)
        assert gate.is_admitted()
        # Only this disposable fixture file is damaged, never a runtime Store B.
        if damage == "missing":
            provider.path.unlink()
        else:
            provider.path.write_bytes(b"invalid disposable database")
        assert gate.state == RestoreReadinessState.FAILED
        with pytest.raises(RestoreQuarantineError):
            gate.assert_traffic_admitted()
        with pytest.raises(
            (RecoveryAuthorizationError, sqlite3.DatabaseError, StoreBUnavailableError)
        ):
            gate.set_state(RestoreReadinessState.READY)
        assert gate.state == RestoreReadinessState.FAILED
