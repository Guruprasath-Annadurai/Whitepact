# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""UNKNOWN semantics preparation — not a final campaign PASS."""

from __future__ import annotations

from responsibleai.governance.outcome import OutcomeStatus


def test_unknown_is_distinct_from_success_and_failure() -> None:
    assert OutcomeStatus.UNKNOWN != OutcomeStatus.SUCCEEDED
    assert OutcomeStatus.UNKNOWN != OutcomeStatus.FAILED


def test_unknown_not_treated_as_success_for_retry_logic() -> None:
    """Document invariant: callers must reconcile UNKNOWN, not auto-retry as success."""
    state = OutcomeStatus.UNKNOWN
    assert state not in (OutcomeStatus.SUCCEEDED,)
