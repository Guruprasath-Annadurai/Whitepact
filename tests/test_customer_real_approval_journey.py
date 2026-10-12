# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual TCP/browser-session approval resume; no policy-removal workaround."""

from __future__ import annotations

import asyncio
import socket

import httpx
import pytest
import uvicorn
from sdk.python.rai_client.governance import GovernanceRequestError, GovernanceRuntimeClient

import responsibleai.dashboard.app as dashboard
from responsibleai.dashboard.signup_guard import SignupRateWindow
from responsibleai.db.org_repository import OrgRepository
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.governance.synthetic_counter import snapshot as counter_snapshot
from tests.pg_test_url import isolated_pg_url
from tests.test_v1_customer_journey import (
    PURPOSE,
    _login,
    _onboard,
    _register,
    _token_from_url,
    _upgrade_head,
    _verify_login,
)
from tests.test_v1_exactly_one_effect import ADMIN_EMAIL, _prepare_org


@pytest.fixture()
async def live_customer(monkeypatch, seed_runtime_authority):
    async for url in isolated_pg_url("wp_approval_tcp"):
        await _upgrade_head(url)
        for name, value in {
            "database_url": url,
            "auto_migrate": False,
            "auth_enabled": True,
            "web_auth_dev_tokens": True,
            "web_session_secure": False,
            "web_verification_delivery_url": None,
            "paddle_webhook_secret": "local-only-unused-placeholder",
            "environment": "development",
        }.items():
            monkeypatch.setattr(dashboard.settings, name, value)
        monkeypatch.setattr(dashboard.limiter, "enabled", False)
        monkeypatch.setattr(
            dashboard, "_signup_window", SignupRateWindow(max_per_window=1000, window_seconds=3600)
        )
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(dashboard.app, log_level="critical", access_log=False)
        )
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(30):
                while not server.started:
                    if task.done():
                        await task
                        raise AssertionError("Local server did not start")
                    await asyncio.sleep(0.01)
            async with httpx.AsyncClient(base_url=origin, timeout=10) as browser:
                org_id, key = await _prepare_org(browser, monkeypatch, seed_runtime_authority, url)
                yield browser, GovernanceRuntimeClient(key, base_url=origin), org_id, key
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=30)
            sock.close()


async def _resolve(browser, approval_id, outcome):
    return await browser.post(
        f"/api/v1/web/approvals/{approval_id}/resolve",
        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
        json={"outcome": outcome},
    )


async def _execute(browser, approval_id):
    return await browser.post(
        f"/api/v1/web/approvals/{approval_id}/execute",
        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
        json={},
    )


async def _counter(browser, key):
    response = await browser.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {key}"}
    )
    assert response.status_code == 200
    return response.json()["counter"]


@pytest.mark.asyncio
async def test_real_distinct_humans_approve_resume_once_and_deny(live_customer):
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert pending.requires_approval and not pending.completed
    approval_id = pending.approval_id
    assert approval_id
    assert await _counter(browser, key) == 0
    # Missing CSRF cannot cast a vote.
    csrf_denied = await browser.post(
        f"/api/v1/web/approvals/{approval_id}/resolve", json={"outcome": "APPROVED"}
    )
    assert csrf_denied.status_code == 403
    first = await _resolve(browser, approval_id, "APPROVED")
    assert first.status_code == 200
    assert first.json()["status"] == "PENDING"
    assert (await _execute(browser, approval_id)).status_code == 409
    assert await _counter(browser, key) == 0
    # Same human cannot supply the missing second vote.
    duplicate = await _resolve(browser, approval_id, "APPROVED")
    assert duplicate.status_code == 409
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    second = await _resolve(browser, approval_id, "APPROVED")
    assert second.status_code == 200
    assert second.json()["status"] == "APPROVED"
    executed = await _execute(browser, approval_id)
    assert executed.status_code == 200
    assert executed.json()["execution_status"] == "SUCCEEDED"
    assert await _counter(browser, key) == 1

    assert (await _execute(browser, approval_id)).status_code == 409
    assert await _counter(browser, key) == 1
    records = (await sdk.list_evidence())["evidence"]
    assert all(record["organization_id"] == org_id for record in records)
    assert any(record.get("approval_id") == approval_id for record in records)
    attestation = await sdk.get_attestation(records[0]["evidence_id"])
    assert attestation["evidence_id"] == records[0]["evidence_id"]
    denied = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert denied.requires_approval
    resolved = await _resolve(browser, denied.approval_id, "DENIED")
    assert resolved.status_code == 200
    assert (await _execute(browser, denied.approval_id)).status_code == 409
    assert await _counter(browser, key) == 1
    # No policy is removed; every request still requires real approval.
    another = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert another.requires_approval and not another.completed
    # Independent browser/session and supported onboarding, not an org-ID header override.
    async with httpx.AsyncClient(base_url=browser.base_url, timeout=10) as other:
        _, registration = await _register(
            other, name="Other Tenant Owner", email="other.tenant.owner@example.com"
        )
        csrf = await _verify_login(
            other,
            "other.tenant.owner@example.com",
            _token_from_url(registration["verification_url"]),
        )
        other_session = await _onboard(other, csrf, "Other Tenant")
        assert other_session["organization"]["id"] != org_id
        for path in [
            f"/api/v1/web/evidence/{records[0]['evidence_id']}",
            f"/api/v1/web/evidence/{records[0]['evidence_id']}/attestation",
        ]:
            assert (await other.get(path)).status_code == 404
        assert (await _resolve(other, another.approval_id, "APPROVED")).status_code == 404
        assert (await _execute(other, approval_id)).status_code == 404
    assert await _counter(browser, key) == 1


@pytest.mark.asyncio
async def test_real_approval_resume_after_credential_revocation_has_zero_effect(live_customer):
    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert pending.requires_approval
    assert (await _resolve(browser, pending.approval_id, "APPROVED")).status_code == 200
    principal = await OrgRepository(dashboard._db_engine).authenticate(key)
    assert principal is not None
    # Developer credentials cannot perform an ADMIN mutation; do not upgrade the key.
    with pytest.raises(GovernanceRequestError) as forbidden:
        await sdk.revoke_delegation(principal.key_id, reason="Approval race regression")
    assert forbidden.value.status_code == 403
    revoked = await browser.delete(
        f"/api/v1/web/api-keys/{principal.key_id}",
        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
    )
    assert revoked.status_code == 200
    assert revoked.json()["revoked"] == principal.key_id
    await browser.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    resolved = await _resolve(browser, pending.approval_id, "APPROVED")
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "APPROVED"
    assert (await _execute(browser, pending.approval_id)).status_code == 409
    assert (await counter_snapshot(org_id))["counter"] == 0
    with pytest.raises(GovernanceRequestError) as invalid:
        await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert invalid.value.status_code == 401
