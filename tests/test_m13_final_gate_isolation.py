# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Hermetic test isolation must never manufacture restore admission."""

import pytest

from responsibleai.data_governance import backup_defense


def test_fresh_factory_still_denies_production_without_durable_authority(monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.delenv("WHITEPACT_STORE_B_PATH", raising=False)
    monkeypatch.delenv("WHITEPACT_LIFECYCLE_STORE_PATH", raising=False)
    gate = backup_defense.get_restore_readiness_gate()
    assert gate.state == backup_defense.RestoreReadinessState.FAILED
    with pytest.raises(backup_defense.RestoreQuarantineError):
        gate.assert_traffic_admitted()


def test_new_instance_preserves_actual_durable_failed_state(monkeypatch, tmp_path):
    path = tmp_path / "store-b.sqlite"
    provider = backup_defense.DurableLifecycleStateProvider(path)
    provider.set_readiness_state(backup_defense.RestoreReadinessState.FAILED)
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(path))
    gate = backup_defense.get_restore_readiness_gate()
    assert gate.state == backup_defense.RestoreReadinessState.FAILED
    backup_defense.set_restore_readiness_gate(None)
    restarted = backup_defense.get_restore_readiness_gate()
    assert restarted is not gate
    assert restarted.state == backup_defense.RestoreReadinessState.FAILED
    with pytest.raises(backup_defense.RestoreQuarantineError):
        restarted.assert_traffic_admitted()
