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
