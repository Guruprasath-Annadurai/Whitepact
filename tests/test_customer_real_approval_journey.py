# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual TCP/browser-session approval resume; no policy-removal workaround."""

from __future__ import annotations

import asyncio
import json
import platform
import re
import socket
from pathlib import Path
from urllib.parse import urlparse

import httpx
import pytest
import uvicorn
from sdk.python.rai_client.governance import GovernanceRequestError, GovernanceRuntimeClient
from sqlalchemy import func, select

import responsibleai.dashboard.app as dashboard
from responsibleai.dashboard.signup_guard import SignupRateWindow
from responsibleai.db.engine import governance_execution_authorizations
from responsibleai.db.org_repository import OrgRepository
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.governance.synthetic_counter import snapshot as counter_snapshot
from tests.pg_test_url import isolated_pg_url, resolve_admin_url
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


@pytest.mark.asyncio
async def test_authenticated_customer_cannot_self_authorize_restore_reconciliation(live_customer):
    """Real PG/session boundary; a synthetic FAILED precondition is not recovery proof."""
    from responsibleai.data_governance.backup_defense import (
        RestoreReadinessState,
        get_restore_readiness_gate,
    )

    browser, sdk, org_id, key = live_customer
    gate = get_restore_readiness_gate()
    gate.set_state(RestoreReadinessState.FAILED)
    responses = await asyncio.gather(
        *(
            browser.post(
                route,
                headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
                json={"reconciled_by": "customer-claimed-operator", "status": "READY"},
            )
            for route in ("/api/restore/reconcile", "/api/v1/restore/reconcile")
        )
    )
    assert all(response.status_code == 503 for response in responses)
    assert all(
        response.json()["error"] == "RESTORE_SECURITY_QUALIFICATION_REQUIRED"
        for response in responses
    )
    assert gate.state == RestoreReadinessState.FAILED
    with pytest.raises(GovernanceRequestError) as denied:
        await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert denied.value.status_code == 503
    assert key not in str(denied.value)
    assert (await counter_snapshot(org_id))["counter"] == 0


@pytest.mark.asyncio
async def test_go_sdk_analytics_against_real_backend(live_customer, tmp_path):
    browser, _, _, key = live_customer
    root = Path(__file__).resolve().parents[1]
    target_os = "darwin" if platform.system() == "Darwin" else "linux"
    target_arch = "arm64" if platform.machine() in {"arm64", "aarch64"} else "amd64"
    compiler = await asyncio.create_subprocess_exec(
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-v",
        f"{root / 'sdk/go'}:/src:ro",
        "-v",
        f"{tmp_path}:/out",
        "-w",
        "/src",
        "-e",
        f"GOOS={target_os}",
        "-e",
        f"GOARCH={target_arch}",
        "golang@sha256:1cf6c45ba39db9fd6db16922041d074a63c935556a05c5ccb62d181034df7f02",
        "go",
        "build",
        "-o",
        "/out/livecheck",
        "./cmd/livecheck",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(compiler.communicate(), timeout=120)
    assert compiler.returncode == 0, "Go smoke build failed; Docker/toolchain required"
    process = await asyncio.create_subprocess_exec(
        str(tmp_path / "livecheck"),
        str(browser.base_url).rstrip("/"),
        "--analytics",
        env={"WHITEPACT_API_KEY": key},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    output, error = await asyncio.wait_for(process.communicate(), timeout=15)
    assert key.encode() not in output + error
    assert process.returncode == 0, "Go actual authenticated analytics request failed"
    result = json.loads(output)
    assert result["health"] in {"ok", "healthy"}
    assert result["scan_blocked"] is True
    assert result["heuristic_risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    principal = await OrgRepository(dashboard._db_engine).authenticate(key)
    assert principal is not None
    revoked = await browser.delete(
        f"/api/v1/web/api-keys/{principal.key_id}",
        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
    )
    assert revoked.status_code == 200
    for invalid_key in (key, "invalid-synthetic-test-key", ""):
        denied = await asyncio.create_subprocess_exec(
            str(tmp_path / "livecheck"),
            str(browser.base_url).rstrip("/"),
            "--analytics",
            env={"WHITEPACT_API_KEY": invalid_key},
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        denied_output, denied_error = await asyncio.wait_for(denied.communicate(), timeout=15)
        assert denied.returncode == 1
        assert not denied_output
        assert key.encode() not in denied_error


@pytest.mark.asyncio
async def test_real_database_outage_blocks_new_admission_and_recovers(live_customer):
    import asyncpg

    browser, sdk, org_id, key = live_customer
    pending = await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert pending.requires_approval
    assert dashboard._db_engine is not None
    grants_query = (
        select(func.count())
        .select_from(governance_execution_authorizations)
        .where(governance_execution_authorizations.c.organization_id == org_id)
    )
    async with dashboard._db_engine.raw.connect() as conn:
        grants_before = await conn.scalar(grants_query)
    database = urlparse(dashboard.settings.database_url).path.lstrip("/")
    assert re.fullmatch(r"wp_approval_tcp_[0-9a-f]{12}", database)
    admin_url = await resolve_admin_url()
    assert urlparse(admin_url).hostname in {None, "localhost", "127.0.0.1"}
    admin = await asyncpg.connect(admin_url)
    try:
        await admin.execute(f'ALTER DATABASE "{database}" WITH ALLOW_CONNECTIONS false')
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = $1",
            database,
        )
        with pytest.raises(GovernanceRequestError) as unavailable:
            await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
        assert unavailable.value.status_code in {500, 503}
        assert key not in str(unavailable.value)
    finally:
        # Only the exact randomly generated disposable database is restored.
        await admin.execute(f'ALTER DATABASE "{database}" WITH ALLOW_CONNECTIONS true')
        await admin.close()
    # Availability alone is not authorized recovery. The public reconciliation
    # route remains qualification-blocked; do not fake an operator transition.
    with pytest.raises(GovernanceRequestError) as unreconciled:
        await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
    assert unreconciled.value.status_code == 503
    assert "restore_quarantine" in str(unreconciled.value)
    assert key not in str(unreconciled.value)
    async with dashboard._db_engine.raw.connect() as conn:
        assert await conn.scalar(grants_query) == grants_before
    assert (await counter_snapshot(org_id))["counter"] == 0
