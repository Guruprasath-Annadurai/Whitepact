# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 restore drill evidence — chokepoint + readiness state machine."""

from __future__ import annotations

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    RestoreReadinessState,
)


def test_restore_gate_transitions_require_explicit_ready() -> None:
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    assert not gate.is_admitted()
    gate.set_state(RestoreReadinessState.RECONCILING)
    assert gate.state == RestoreReadinessState.RECONCILING
    assert not gate.is_admitted()
    gate.set_state(RestoreReadinessState.READY)
    assert gate.is_admitted()


def test_restore_drill_documented_in_runbook() -> None:
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "docs/operations/runbooks/RESTORE_VERIFICATION.md"
    text = path.read_text(encoding="utf-8").lower()
    assert "isolated" in text
    assert "restore" in text
