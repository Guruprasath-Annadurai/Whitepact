# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real TCP/PostgreSQL customer contracts; explicit inherited authority fixtures.

This is not proof of fixture-free customer authority provisioning or production
identity delivery. The existing live_customer fixture retains browser auth/CSRF,
uses development identity proofs, and disables the local request limiter.
"""

import pytest

from tests import test_customer_real_approval_journey as customer_journey

live_customer = customer_journey.live_customer


@pytest.mark.parametrize("effect", ["ALLOW_WITH_REDACTION", "QUARANTINE"])
async def test_unsupported_ordered_rule_is_safe_422_not_runtime_outcome_loss(live_customer, effect):
    browser, _, organization_id, _ = live_customer
    before = await browser.get("/api/v1/web/policy")
    assert before.status_code == 200
    rejected = await browser.post(
        "/api/v1/web/policy/rules",
        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
        json={"rule_id": "m11-unsupported", "reason_code": "M11", "effect": effect},
    )
    assert rejected.status_code == 422
    after = await browser.get("/api/v1/web/policy")
    assert after.status_code == 200
    assert after.json()["org_id"] == organization_id
    assert after.json()["rules"] == before.json()["rules"]


async def test_policy_history_uses_authenticated_tenant_and_explicit_verification_scope(
    live_customer,
):
    browser, _, organization_id, _ = live_customer
    result = await browser.get(
        "/api/v1/web/policy/history",
        params={"limit": 100, "organization_id": "untrusted-browser-value"},
    )
    assert result.status_code == 200
    payload = result.json()
    assert payload["org_id"] == organization_id
    assert isinstance(payload["chain_valid"], bool)
    assert payload["checkpoint_checked"] is False
    assert isinstance(payload["entries"], list)
    assert len(payload["entries"]) <= 100
    assert payload["head"] is None or (
        isinstance(payload["head"]["version"], int)
        and isinstance(payload["head"]["entry_digest"], str)
    )
