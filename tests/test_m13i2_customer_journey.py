# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evidence semantics only; no fake authentication or authority fixtures."""

import json

import httpx
import pytest
from scripts.engineering.m13i2_customer_journey import (
    DOWNSTREAM,
    JourneyEvidence,
    JourneyStoppedError,
    configured_settings,
)

import responsibleai.dashboard.app as dashboard


def test_http_success_cannot_confirm_a_failed_semantic_contract():
    evidence = JourneyEvidence()
    with pytest.raises(JourneyStoppedError):
        evidence.check("owner_session", httpx.Response(200), 200, False)
    assert evidence.phases[-1]["result"] == "BLOCKED"


def test_unexpected_http_status_stops_without_recording_response_secrets():
    evidence = JourneyEvidence()
    response = httpx.Response(503, json={"detail": "PRIVATE-RESPONSE-TOKEN"})
    with pytest.raises(JourneyStoppedError):
        evidence.check("signup", response, 202)
    serialized = json.dumps(evidence.report())
    assert "PRIVATE-RESPONSE-TOKEN" not in serialized
    assert evidence.phases[-1]["http_status"] == 503
    assert evidence.phases[-1]["result"] == "BLOCKED"


def test_report_never_promotes_partial_account_success_to_authority_acceptance():
    evidence = JourneyEvidence()
    evidence.check("signup", httpx.Response(202), 202)
    report = evidence.report()
    assert report["acceptance"] == "BLOCKED"
    assert report["production"] == "GLOBAL PRODUCTION NO-GO"
    assert report["not_executed"] == list(DOWNSTREAM)
    assert "authority_revocation" in report["not_executed"]
    assert "policy" in report["not_executed"]
    assert "denial_after_authority_revocation" in report["not_executed"]


def test_temporary_settings_restore_even_when_attempt_fails():
    previous = dashboard.settings.web_auth_dev_tokens
    with pytest.raises(JourneyStoppedError):
        with configured_settings({"web_auth_dev_tokens": not previous}):
            assert dashboard.settings.web_auth_dev_tokens is not previous
            raise JourneyStoppedError("local stop")
    assert dashboard.settings.web_auth_dev_tokens is previous


def test_semantic_parse_exception_retains_prior_phases_without_private_diagnostics():
    evidence = JourneyEvidence()
    evidence.check("signup", httpx.Response(202), 202)
    response = httpx.Response(200, content=b"PRIVATE-MALFORMED-RESPONSE")
    with pytest.raises(JourneyStoppedError):
        evidence.check("owner_session", response, 200, lambda: response.json()["organization"])
    assert [phase["result"] for phase in evidence.phases] == ["CONFIRMED", "BLOCKED"]
    assert evidence.phases[-1]["phase"] == "owner_session"
    assert "PRIVATE-MALFORMED-RESPONSE" not in json.dumps(evidence.report())
