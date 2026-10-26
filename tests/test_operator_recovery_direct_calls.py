# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Direct calls must not promote quarantined hosted authority."""

import sqlite3

import pytest

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError


@pytest.mark.parametrize("state", ["FAILED", "RESTORE_PENDING", "RECONCILING"])
@pytest.mark.parametrize("surface", ["gate", "provider"])
def test_hosted_direct_ready_transition_requires_operator_authorization(
    tmp_path, monkeypatch, state, surface
):
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
    provider.set_readiness_state(RestoreReadinessState(state))
    gate = RestoreReadinessGate(provider=provider)
    target = gate.set_state if surface == "gate" else provider.set_readiness_state
    with pytest.raises(RecoveryAuthorizationError):
        target(RestoreReadinessState.READY, updated_by="claimed-security-owner")
    assert provider.get_readiness_state() == RestoreReadinessState(state)
    assert not gate.is_admitted()


def test_local_development_transition_is_not_production_recovery(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "test")
    monkeypatch.setenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", "1")
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    gate = RestoreReadinessGate(provider=provider)
    gate.set_state(RestoreReadinessState.READY)
    assert gate.is_admitted()


def test_hosted_failure_cannot_be_demoted_by_a_development_flag(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    monkeypatch.setenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", "1")
    restarted = SqliteDurableLifecycleStateProvider(provider.path)
    assert restarted.requires_operator_recovery()
    with pytest.raises(RecoveryAuthorizationError):
        restarted.set_readiness_state(RestoreReadinessState.READY)
    assert restarted.get_readiness_state() == RestoreReadinessState.FAILED


def test_missing_readiness_row_cannot_reenter_initial_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    with sqlite3.connect(provider.path) as connection:
        connection.execute("DELETE FROM durable_restore_readiness")
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.READY, provider=provider)
    assert gate.state == RestoreReadinessState.FAILED
    with pytest.raises(RecoveryAuthorizationError):
        provider.set_readiness_state(RestoreReadinessState.READY)


def test_missing_tenant_lookup_remains_distinct_from_missing_readiness(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    assert provider.get_state("unknown-tenant") is None


@pytest.mark.asyncio
async def test_direct_engine_call_rejects_audit_label_before_any_mutation(tmp_path, monkeypatch):
    from responsibleai.data_governance.backup_defense import RestoreReconciliationEngine
    from responsibleai.db.engine import create_engine

    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    gate = RestoreReadinessGate(provider=provider)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'store-a.sqlite3'}")
    try:
        reconciler = RestoreReconciliationEngine(
            engine, lifecycle_provider=provider, gate=gate, require_durable=True
        )
        with pytest.raises(RecoveryAuthorizationError):
            await reconciler.reconcile_post_restore(reconciled_by="security-owner")
        assert gate.state == RestoreReadinessState.FAILED
        assert provider.get_readiness_state() == RestoreReadinessState.FAILED
    finally:
        await engine.close()
