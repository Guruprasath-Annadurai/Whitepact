# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial qualification suite for approval resume (Phase 4).

Proves the 10 non-negotiable security requirements for human approval execution:
1. Changed tool arguments after approval (byte mismatch / digest drift).
2. Changed policies before resume (policy update revokes or denies resume).
3. Expired approvals fail closed.
4. Concurrent resume attempts cannot double-spend approval or execute twice.
5. Revoked identity or revoked API key blocks resume.
6. Tenant switching (Tenant B cannot see, approve, or resume Tenant A's approval).
7. Different agent or tool substitution fails closed.
8. Revocation epoch bump during or before execution halts resume.
9. One-time grant replay fails closed (CONSUMED status invariant).
10. Execution failure or rejection leaves no unauthorized counter increment.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import update

import responsibleai.dashboard.app as dashboard
from responsibleai.db.engine import governance_approvals
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.governance.synthetic_counter import snapshot as counter_snapshot
from tests.test_customer_real_approval_journey import (
    ADMIN_EMAIL,
    PURPOSE,
    _counter,
    _execute,
    _resolve,
)
from tests.test_v1_customer_journey import (
    _login,
    _onboard,
    _register,
    _token_from_url,
    _verify_login,
)


@pytest.mark.asyncio
async def test_01_changed_tool_arguments_after_approval_fails_closed(live_customer):
    """Requirement 1: Changed tool arguments after approval must be rejected by digest mismatch."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert pending.requires_approval
    approval_id = pending.approval_id

    # Approve via 2 humans
    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    second = await _resolve(browser, approval_id, "APPROVED")
    assert second.status_code == 200

    # Tamper with the stored arguments in DB behind the scenes
    async with dashboard._db_engine.raw.begin() as conn:
        await conn.execute(
            update(governance_approvals)
            .where(governance_approvals.c.id == approval_id)
            .values(arguments='{"amount": 999999, "tampered": true}')
        )

    # Attempt to execute: digest or argument mismatch must fail closed
    res = await _execute(browser, approval_id)
    assert res.status_code in {400, 409, 500}
    # Verify counter NEVER incremented
    assert await _counter(browser, key) == 0


@pytest.mark.asyncio
async def test_02_changed_policy_before_resume_denies_execution(live_customer):
    """Requirement 2: Policy updated to deny action before resume must reject execution."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert pending.requires_approval
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    # Policy update: remove existing approval rule and add deny rule
    from responsibleai.governance.models import GovernanceDecision
    from responsibleai.governance.policy import PolicyRule

    await dashboard._policy_repo.remove_rule(org_id, "require-test-counter")
    deny_rule = PolicyRule(
        rule_id="deny_all_counter",
        reason_code="blocked_by_adversarial_test",
        effect=GovernanceDecision.DENY,
        action_types=frozenset([SYNTHETIC_COUNTER_TOOL]),
    )
    await dashboard._policy_repo.add_rule(org_id, deny_rule)

    # Attempt execute
    res = await _execute(browser, approval_id)
    assert res.status_code == 409
    # Verify counter remains unchanged
    assert await _counter(browser, key) == 0


@pytest.mark.asyncio
async def test_03_expired_approval_fails_closed(live_customer):
    """Requirement 3: Expired approvals fail closed even if approved."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    # Expire the approval in DB
    past_time = "2020-01-01T00:00:00+00:00"
    async with dashboard._db_engine.raw.begin() as conn:
        await conn.execute(
            update(governance_approvals)
            .where(governance_approvals.c.id == approval_id)
            .values(expires_at=past_time)
        )

    # Attempt execute
    res = await _execute(browser, approval_id)
    assert res.status_code == 409
    assert await _counter(browser, key) == 0


@pytest.mark.asyncio
async def test_04_concurrent_resume_attempts_cannot_double_spend(live_customer):
    """Requirement 4: 10 concurrent resume calls must result in exactly 1 execution and 9 409 conflicts."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    # Launch 10 simultaneous execute requests
    tasks = [_execute(browser, approval_id) for _ in range(10)]
    responses = await asyncio.gather(*tasks)

    status_codes = [r.status_code for r in responses]
    assert status_codes.count(200) == 1, f"Expected exactly 1 200, got: {status_codes}"
    assert status_codes.count(409) == 9, f"Expected 9 409s, got: {status_codes}"
    # Counter must be exactly 1
    assert await _counter(browser, key) == 1


@pytest.mark.asyncio
async def test_05_revoked_identity_or_api_key_blocks_resume(live_customer):
    """Requirement 5: Revoking principal API key before resume must prevent execution."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    # Revoke the API key used by the agent
    from responsibleai.db.org_repository import OrgRepository

    principal = await OrgRepository(dashboard._db_engine).authenticate(key)
    assert principal is not None
    del_res = await browser.delete(
        f"/api/v1/web/api-keys/{principal.key_id}",
        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
    )
    assert del_res.status_code == 200

    # Resume attempt must fail because identity authority was revoked
    res = await _execute(browser, approval_id)
    assert res.status_code == 409
    assert (await counter_snapshot(org_id))["counter"] == 0


@pytest.mark.asyncio
async def test_06_tenant_switching_and_isolation(live_customer):
    """Requirement 6: Tenant B cannot inspect, resolve, or execute Tenant A's approval."""
    import httpx

    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    # Create Tenant B
    async with httpx.AsyncClient(base_url=browser.base_url, timeout=10) as tenant_b:
        _, registration = await _register(
            tenant_b, name="Tenant B Admin", email="tenant_b_admin@example.com"
        )
        csrf = await _verify_login(
            tenant_b,
            "tenant_b_admin@example.com",
            _token_from_url(registration["verification_url"]),
        )
        b_session = await _onboard(tenant_b, csrf, "Tenant B Corp")
        assert b_session["organization"]["id"] != org_id

        # Tenant B attempts to resolve Tenant A's approval -> 404
        resolve_attempt = await _resolve(tenant_b, approval_id, "APPROVED")
        assert resolve_attempt.status_code == 404

        # Tenant B attempts to execute Tenant A's approval -> 404
        exec_attempt = await _execute(tenant_b, approval_id)
        assert exec_attempt.status_code == 404

    # Tenant A counter remains untouched
    assert await _counter(browser, key) == 0


@pytest.mark.asyncio
async def test_07_different_agent_or_tool_substitution_fails_closed(live_customer):
    """Requirement 7: Substituting agent or action_type in approval record fails closed on match check."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    # Tamper with action_type
    async with dashboard._db_engine.raw.begin() as conn:
        await conn.execute(
            update(governance_approvals)
            .where(governance_approvals.c.id == approval_id)
            .values(action_type="mcp:unauthorized_admin_drop_db")
        )

    res = await _execute(browser, approval_id)
    assert res.status_code in {400, 409, 500}
    assert await _counter(browser, key) == 0


@pytest.mark.asyncio
async def test_08_revocation_epoch_bump_rejects_resume(live_customer):
    """Requirement 8: Bumping org revocation epoch invalidates approved resume before execution."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    # Bump org revocation epoch
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

    epoch_repo = RevocationEpochRepository(dashboard._db_engine)
    await epoch_repo.bump(org_id)

    # Resume must be rejected due to security epoch mismatch
    res = await _execute(browser, approval_id)
    assert res.status_code == 409
    assert await _counter(browser, key) == 0


@pytest.mark.asyncio
async def test_09_one_time_grant_replay_fails_closed(live_customer):
    """Requirement 9: An approval already CONSUMED cannot be executed again."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    first = await _execute(browser, approval_id)
    assert first.status_code == 200
    assert first.json()["execution_status"] == "SUCCEEDED"
    assert await _counter(browser, key) == 1

    # Second execution attempt immediately rejected
    second = await _execute(browser, approval_id)
    assert second.status_code == 409
    assert await _counter(browser, key) == 1


@pytest.mark.asyncio
async def test_10_execution_failure_leaves_no_counter_increment(live_customer, monkeypatch):
    """Requirement 10: If execution encounters error during tool call, counter does not leak side effects."""
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    approval_id = pending.approval_id

    await _resolve(browser, approval_id, "APPROVED")
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    assert (await _resolve(browser, approval_id, "APPROVED")).status_code == 200

    # Patch InternalToolExecutor.execute to simulate unexpected crash
    from responsibleai.governance.execution import InternalToolExecutor

    async def failing_execute(self, authorization, action):
        raise RuntimeError("Simulated execution environment failure")

    monkeypatch.setattr(InternalToolExecutor, "execute", failing_execute)

    res = await _execute(browser, approval_id)
    assert res.status_code in {409, 500}
    # Verify counter NEVER incremented
    assert await _counter(browser, key) == 0
