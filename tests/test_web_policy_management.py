# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-3 M2 — web session policy management (P1-01)."""

from __future__ import annotations

import uuid
from urllib.parse import parse_qs, urlparse

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module


@pytest.fixture()
async def web_client(monkeypatch: pytest.MonkeyPatch):
    from responsibleai.dashboard.signup_guard import SignupRateWindow

    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=30, window_seconds=3600.0)
    )
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}@example.com"


def _verification_token(reg_body: dict) -> str:
    url = reg_body.get("verification_url")
    assert url, f"expected dev verification_url in register response, got {reg_body!r}"
    return parse_qs(urlparse(url).query)["token"][0]


async def _onboard_owner(web_client: AsyncClient, email: str | None = None) -> str:
    owner_email = email or _unique_email("policy-owner")
    reg = await web_client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Policy Owner",
            "email": owner_email,
            "password": "Policy-Owner-42!",
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    token = _verification_token(reg.json())
    assert (
        await web_client.post("/api/v1/web/auth/verify", json={"token": token})
    ).status_code == 200
    assert (
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": owner_email, "password": "Policy-Owner-42!"},
        )
    ).status_code == 200
    csrf = web_client.cookies["wp_csrf"]
    onboard = await web_client.post(
        "/api/v1/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": "Policy Org", "use_case": "Agent development"},
    )
    assert onboard.status_code == 200
    return csrf


@pytest.mark.asyncio
async def test_web_policy_read_and_admin_mutations(web_client: AsyncClient) -> None:
    csrf = await _onboard_owner(web_client)
    listing = await web_client.get("/api/v1/web/policy")
    assert listing.status_code == 200
    body = listing.json()
    assert body["can_edit"] is True
    assert isinstance(body["rules"], list)

    created = await web_client.post(
        "/api/v1/web/policy/rules",
        headers={"X-WP-CSRF": csrf},
        json={
            "rule_id": "journey-deny-external",
            "reason_code": "DENY_EXTERNAL_SEND",
            "effect": "DENY",
            "action_types": ["external.send"],
        },
    )
    assert created.status_code == 200
    assert created.json()["rule_id"] == "journey-deny-external"

    dashboard = await web_client.get("/api/v1/web/dashboard/policies")
    assert dashboard.status_code == 200
    assert any(item["rule_id"] == "journey-deny-external" for item in dashboard.json()["items"])

    removed = await web_client.delete(
        "/api/v1/web/policy/rules/journey-deny-external",
        headers={"X-WP-CSRF": csrf},
    )
    assert removed.status_code == 200


@pytest.mark.asyncio
async def test_web_policy_mutations_require_admin(web_client: AsyncClient) -> None:
    viewer_email = _unique_email("policy-viewer")
    owner_csrf = await _onboard_owner(web_client)
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": viewer_email, "role": "VIEWER"},
    )
    assert invite.status_code in {200, 202}
    invite_url = invite.json()["invitation_url"]
    token = parse_qs(urlparse(invite_url).query)["token"][0]

    reg = await web_client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Policy Viewer",
            "email": viewer_email,
            "password": "Viewer-Policy-42!",
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    verify_token = _verification_token(reg.json())
    await web_client.post("/api/v1/web/auth/verify", json={"token": verify_token})
    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": viewer_email, "password": "Viewer-Policy-42!"},
    )
    viewer_csrf = web_client.cookies["wp_csrf"]
    accepted = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": viewer_csrf},
        json={"token": token},
    )
    assert accepted.status_code == 200

    read = await web_client.get("/api/v1/web/policy")
    assert read.status_code == 200
    assert read.json()["can_edit"] is False

    denied = await web_client.post(
        "/api/v1/web/policy/rules",
        headers={"X-WP-CSRF": viewer_csrf},
        json={
            "rule_id": "viewer-forged",
            "reason_code": "FORGED",
            "effect": "ALLOW",
        },
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_web_approval_resolve_requires_admin(web_client: AsyncClient) -> None:
    analyst_email = _unique_email("policy-analyst")
    csrf = await _onboard_owner(web_client)
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": csrf},
        json={"email": analyst_email, "role": "ANALYST"},
    )
    assert invite.status_code in {200, 202}
    token = parse_qs(urlparse(invite.json()["invitation_url"]).query)["token"][0]
    reg = await web_client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Analyst",
            "email": analyst_email,
            "password": "Analyst-Policy-42!",
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    verify_token = _verification_token(reg.json())
    await web_client.post("/api/v1/web/auth/verify", json={"token": verify_token})
    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": analyst_email, "password": "Analyst-Policy-42!"},
    )
    analyst_csrf = web_client.cookies["wp_csrf"]
    accepted = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": analyst_csrf},
        json={"token": token},
    )
    assert accepted.status_code == 200
    analyst_csrf = web_client.cookies["wp_csrf"]

    fake_id = "00000000-0000-0000-0000-000000000099"
    denied = await web_client.post(
        f"/api/v1/web/approvals/{fake_id}/resolve",
        headers={"X-WP-CSRF": analyst_csrf},
        json={"outcome": "APPROVED"},
    )
    assert denied.status_code == 403
    assert "administrator" in denied.json().get("message", "").lower()
