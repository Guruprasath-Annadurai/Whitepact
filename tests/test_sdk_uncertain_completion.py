# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Uncertain downstream effects must never be reported as completed by an SDK."""

import pytest
from sdk.python.rai_client.governance import GovernanceToolOutcome


@pytest.mark.parametrize(
    "body",
    [
        {"status": "UNKNOWN", "evidence_id": "ev-local"},
        {"reconciliation_required": True, "evidence_id": "ev-local"},
        {"status": "UNKNOWN", "reconciliation_required": True},
        {"tool": "local.tool", "result": None, "outcome_status": "UNKNOWN"},
        {"error": "governance_unknown_outcome"},
    ],
)
def test_uncertain_effect_is_not_completed(body):
    outcome = GovernanceToolOutcome(raw=body)
    assert outcome.completed is False
    assert outcome.raw == body
    assert outcome.reconciliation_required is True


def test_confirmed_legacy_tool_response_remains_compatible():
    assert GovernanceToolOutcome(raw={"result": {"ok": True}}).completed is True
