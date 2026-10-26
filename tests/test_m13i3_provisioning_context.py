# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A real browser must reach provisioning, not silently omit its controller.

This negative test is not the full customer journey. The positive mandatory
journey remains a failed gate until legitimate installation authority exists.
"""

import pytest
from scripts.engineering.m13i3_browser_journey import attempt


@pytest.mark.asyncio
async def test_unbootstrapped_browser_reaches_controller_and_remains_denied():
    report = await attempt()
    phases = {phase["phase"]: phase for phase in report["phases"]}
    assert report["acceptance"] == "BLOCKED"
    assert report["fresh_postgresql_migration"] == "CONFIRMED"
    for name in ("signup", "genuine_mail_verification", "password_login"):
        assert phases[name]["result"] == "CONFIRMED"
    assert phases["organization_onboarding"]["result"] == "BLOCKED"
    assert phases["organization_onboarding"]["http_status"] == 403
    assert phases["session_cleanup_logout"]["result"] == "CONFIRMED"
    assert "server_registration_verification" in report["not_executed"]
    assert "controlled_execution" in report["not_executed"]
    assert "authority_revocation" in report["not_executed"]


@pytest.mark.asyncio
async def test_signed_bootstrap_allows_real_webauthn_but_not_false_full_acceptance():
    from scripts.engineering.m13i3_browser_journey import webauthn_component_qualified

    report = await attempt(authorized_bootstrap=True)
    phases = {phase["phase"]: phase for phase in report["phases"]}
    for name in (
        "signup",
        "genuine_mail_verification",
        "password_login",
        "organization_onboarding",
        "browser_generated_registration",
        "server_registration_verification",
        "authentication_challenge",
        "browser_generated_assertion",
        "server_assertion_verification",
        "session_cleanup_logout",
    ):
        assert phases[name]["result"] == "CONFIRMED"
    assert report["acceptance"] == "BLOCKED"
    assert webauthn_component_qualified(report)
    assert {"root_authority", "controlled_execution", "authority_revocation"}.issubset(
        report["not_executed"]
    )


@pytest.mark.asyncio
async def test_strict_uninitialized_browser_denied_without_any_authority(monkeypatch):
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    report = await attempt()
    phases = {phase["phase"]: phase for phase in report["phases"]}
    assert report["acceptance"] == "BLOCKED"
    assert phases["signup"]["result"] == "BLOCKED"
    assert phases["signup"]["http_status"] == 503
    assert "organization_onboarding" not in phases
    assert report["store_b_readiness"] is None
    assert set(report["authority_counts"].values()) == {0}
    assert {"root_authority", "controlled_execution", "authority_revocation"}.issubset(
        report["not_executed"]
    )
