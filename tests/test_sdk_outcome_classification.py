# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Completion is a positive result contract, never absence of an error."""

import pytest
from sdk.python.rai_client.governance import GovernanceToolOutcome


@pytest.mark.parametrize("field", ["status", "outcome_status", "decision"])
@pytest.mark.parametrize(
    "value",
    [
        "UNKNOWN",
        "DENY",
        "DENIED",
        "REQUIRE_APPROVAL",
        "QUARANTINE",
        "FAILED",
        "PENDING",
        "ERRORED",
        "BLOCKED",
        "ALLOW",
        "unrecognized",
        None,
        1,
        {},
    ],
)
def test_non_success_markers_never_complete(field, value):
    # ALLOW is a decision, not proof of execution; null outcome_status is legacy-compatible.
    if (field, value) in [("decision", "ALLOW"), ("outcome_status", None)]:
        assert GovernanceToolOutcome(raw={field: value, "result": {"ok": True}}).completed
        return
    assert not GovernanceToolOutcome(raw={field: value, "result": {"ok": True}}).completed


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"status": "SUCCEEDED"},
        {"decision": "ALLOW"},
        {"message": "ok"},
        {"result": {}, "reconciliation_required": True},
        {"result": {}, "denied": True},
        {"result": {}, "requires_approval": True},
        {"result": {"error": "downstream_failure"}},
        {"result": {"is_error": True}},
        {"result": {"isError": True}},
        {"result": {}, "status": "SUCCEEDED", "decision": "DENY"},
        {"result": {}, "reconciliation_required": "false"},
        None,
        [],
        "ok",
    ],
)
def test_malformed_or_contradictory_result_is_not_completed(body):
    assert not GovernanceToolOutcome(raw=body).completed


@pytest.mark.parametrize(
    "body",
    [
        {"result": {"ok": True}},
        {"tool": "local", "result": None, "outcome_status": "SUCCEEDED"},
        {"tool": "local", "result": 0, "outcome_status": None},
        {
            "result": {},
            "status": "SUCCEEDED",
            "decision": "ALLOW",
            "reconciliation_required": False,
        },
    ],
)
def test_real_and_legacy_success_contract(body):
    assert GovernanceToolOutcome(raw=body).completed
