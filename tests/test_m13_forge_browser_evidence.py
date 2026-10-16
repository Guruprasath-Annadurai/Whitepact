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
