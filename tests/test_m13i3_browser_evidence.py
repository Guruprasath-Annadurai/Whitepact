# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evidence invariants only; these do not simulate customer authentication."""

import pytest
from scripts.engineering.m13i3_browser_journey import (
    WEBAUTHN_COMPONENT_PHASES,
    validate_report,
    webauthn_component_qualified,
)


def report():
    return {
        "kind": "ACTUAL_POSTGRESQL_HTTP_CHROMIUM_WEBAUTHN_EMULATOR",
        "acceptance": "BLOCKED",
        "phases": [{"phase": "server_registration_verification", "result": "BLOCKED"}],
        "not_executed": ["root_authority", "controlled_execution", "authority_revocation"],
    }


def test_blocked_registration_remains_valid_incomplete_evidence():
    validate_report(report())


@pytest.mark.parametrize(
    "field,value",
    [("kind", "FIXTURE"), ("acceptance", "PASS"), ("phases", []), ("not_executed", [])],
)
def test_incomplete_evidence_cannot_be_promoted_or_lose_unexecuted_stages(field, value):
    value_report = report()
    value_report[field] = value
    with pytest.raises(ValueError):
        validate_report(value_report)


def test_assertion_cannot_be_qualified_after_blocked_registration():
    value_report = report()
    value_report["phases"].append({"phase": "server_assertion_verification", "result": "CONFIRMED"})
    with pytest.raises(ValueError, match="prerequisite"):
        validate_report(value_report)


def test_duplicate_phases_cannot_conceal_failed_verification():
    value_report = report()
    value_report["phases"].append(
        {"phase": "server_registration_verification", "result": "CONFIRMED"}
    )
    with pytest.raises(ValueError, match="identity"):
        validate_report(value_report)


def test_component_qualification_never_promotes_full_customer_acceptance():
    value_report = report()
    value_report["phases"] = [
        {"phase": name, "result": "CONFIRMED"} for name in sorted(WEBAUTHN_COMPONENT_PHASES)
    ]
    assert webauthn_component_qualified(value_report)
    assert value_report["acceptance"] == "BLOCKED"
    assert "controlled_execution" in value_report["not_executed"]


@pytest.mark.parametrize("missing", sorted(WEBAUTHN_COMPONENT_PHASES))
def test_component_requires_every_real_ceremony_phase(missing):
    value_report = report()
    value_report["phases"] = [
        {"phase": name, "result": "CONFIRMED"}
        for name in sorted(WEBAUTHN_COMPONENT_PHASES - {missing})
    ]
    try:
        qualified = webauthn_component_qualified(value_report)
    except ValueError:
        qualified = False
    assert not qualified
