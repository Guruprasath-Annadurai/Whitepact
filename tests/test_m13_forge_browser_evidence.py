# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Journal validation only. No fixture is customer authentication evidence."""

import copy

import pytest
from scripts.engineering.m13_forge_browser_journey import stage_journal


def evidence():
    return {
        "kind": "ACTUAL_POSTGRESQL_HTTP_CHROMIUM_WEBAUTHN_EMULATOR",
        "acceptance": "BLOCKED",
        "phases": [
            {"phase": "signup", "result": "CONFIRMED", "http_status": 202},
            {"phase": "registration", "result": "BLOCKED", "http_status": 403},
        ],
        "not_executed": ["root_authority", "controlled_execution", "authority_revocation"],
    }


def test_journal_preserves_prefix_blocker_and_original_evidence():
    original = evidence()
    snapshot = copy.deepcopy(original)
    journal = stage_journal(original)
    assert original == snapshot
    assert journal["acceptance"] == "BLOCKED"
    assert journal["first_blocked_stage"] == "registration"
    assert [stage["status"] for stage in journal["stages"]] == [
        "PASS",
        "BLOCKED",
        "NOT EXECUTED",
        "NOT EXECUTED",
        "NOT EXECUTED",
    ]
    assert journal["original_evidence"] == snapshot


@pytest.mark.parametrize("extra", ["signup", "root_authority", "", None])
def test_journal_rejects_ambiguous_or_contradictory_unexecuted_steps(extra):
    original = evidence()
    original["not_executed"].append(extra)
    with pytest.raises(ValueError):
        stage_journal(original)


def test_incomplete_journey_requires_an_explicit_blocker():
    original = evidence()
    original["phases"].pop()
    with pytest.raises(ValueError, match="blocking stage"):
        stage_journal(original)


def test_successful_passkey_prefix_stops_at_explicit_downstream_boundary():
    original = evidence()
    original["stop"] = "DOWNSTREAM_AUTHORITY_CONTRACTS_NOT_QUALIFIED"
    original["phases"] = [
        {"phase": name, "result": "CONFIRMED"}
        for name in (
            "server_registration_verification",
            "browser_generated_assertion",
            "server_assertion_verification",
        )
    ]
    journal = stage_journal(original)
    assert journal["first_blocked_stage"] == "downstream_authority_qualification"
    assert journal["acceptance"] == "BLOCKED"
    assert journal["stages"][-1]["status"] == "BLOCKED"
    assert journal["original_evidence"] == original


def test_downstream_boundary_without_verified_assertion_is_not_accepted():
    original = evidence()
    original["stop"] = "DOWNSTREAM_AUTHORITY_CONTRACTS_NOT_QUALIFIED"
    original["phases"].pop()
    with pytest.raises(ValueError, match="assertion verification"):
        stage_journal(original)
