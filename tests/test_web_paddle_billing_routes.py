# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import responsibleai.dashboard.app as app_module


@pytest.fixture()
async def paddle_web_client(monkeypatch):
    monkeypatch.setattr(app_module.settings, "db_path", ":memory:")
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "auth_enabled", False)
    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(app_module.settings, "paddle_api_key", "pdl_test_apikey")  # gitleaks:allow
    monkeypatch.setattr(app_module.settings, "paddle_env", "sandbox")
    monkeypatch.setattr(app_module.settings, "paddle_price_id_pro", "pri_pro_test")
    monkeypatch.setattr(app_module.settings, "paddle_price_id_enterprise", "pri_enterprise_test")
    monkeypatch.setattr(app_module.settings, "web_public_url", "https://app.test")
    monkeypatch.setattr(
        app_module.settings, "billing_success_url", "https://app.test/billing/success"
    )
    monkeypatch.setattr(app_module.settings, "environment", "staging")
    monkeypatch.setattr(app_module.settings, "stripe_secret_key", None)
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


async def _register_onboard(client: AsyncClient, email: str) -> tuple[str, str]:
    reg = await client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Billing User",
            "email": email,
            "password": "Correct-Horse-42!",
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    assert (await client.post("/api/v1/web/auth/verify", json={"token": token})).status_code == 200
    login = await client.post(
        "/api/v1/web/auth/login",
        json={"email": email, "password": "Correct-Horse-42!"},
    )
    assert login.status_code == 200
    csrf = client.cookies.get("wp_csrf", "")
    onboard = await client.post(
        "/api/v1/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": "Paddle Checkout Org", "use_case": "Testing"},
    )
    assert onboard.status_code == 200
    session_info = await client.get("/api/v1/web/session")
    assert session_info.status_code == 200
    org_id = session_info.json()["organization"]["id"]
    return org_id, csrf


@pytest.mark.asyncio
@respx.mock
async def test_web_checkout_uses_paddle_and_server_derived_org(
    paddle_web_client: AsyncClient,
) -> None:
    org_id, csrf = await _register_onboard(paddle_web_client, "paddle-checkout@example.com")
    route = respx.post("https://sandbox-api.paddle.com/transactions").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"checkout": {"url": "https://checkout.paddle.com/sess_web"}}},
        )
    )
    res = await paddle_web_client.post(
        "/api/web/billing/checkout",
        headers={"X-WP-CSRF": csrf},
        json={
            "plan": "PRO",
            "org_email": "forged@evil.example",
            "organization_id": "forged-tenant",
            "org_id": "forged-tenant",
            "price_id": "pri_attacker_selected",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["checkout_url"] == "https://checkout.paddle.com/sess_web"
    assert route.called
    body = json.loads(route.calls[0].request.content.decode())
    assert body["custom_data"]["org_id"] == org_id
    assert body["items"][0]["price_id"] == "pri_pro_test"
    assert body["items"][0]["price_id"] != "pri_attacker_selected"


@pytest.mark.asyncio
@respx.mock
async def test_web_checkout_rejects_unconfigured_plan_price(paddle_web_client: AsyncClient) -> None:
    _, csrf = await _register_onboard(paddle_web_client, "paddle-bad-plan@example.com")
    res = await paddle_web_client.post(
        "/api/web/billing/checkout",
        headers={"X-WP-CSRF": csrf},
        json={"plan": "FREE"},
    )
    assert res.status_code == 422


@pytest.mark.asyncio
@respx.mock
async def test_web_portal_requires_paddle_customer(paddle_web_client: AsyncClient) -> None:
    _, csrf = await _register_onboard(paddle_web_client, "paddle-portal@example.com")
    res = await paddle_web_client.post(
        "/api/web/billing/portal",
        headers={"X-WP-CSRF": csrf},
        json={"return_url": "https://app.test/settings"},
    )
    assert res.status_code == 404


@pytest.mark.asyncio
@respx.mock
async def test_web_portal_uses_server_bound_paddle_customer(
    paddle_web_client: AsyncClient,
) -> None:
    org_id, csrf = await _register_onboard(paddle_web_client, "paddle-portal-bound@example.com")
    await app_module._org_repo.apply_paddle_entitlement(
        org_id=org_id,
        customer_id="ctm_server_bound",
        subscription_id="sub_server_bound",
        plan=app_module.Plan.PRO,
        subscription_status="active",
        occurred_at="2026-09-22T00:00:00Z",
    )
    route = respx.post(
        "https://sandbox-api.paddle.com/customers/ctm_server_bound/portal-sessions"
    ).mock(
        return_value=httpx.Response(
            200,
            json={"data": {"urls": {"general": "https://sandbox-login.paddle.com/portal"}}},
        )
    )

    res = await paddle_web_client.post(
        "/api/web/billing/portal",
        headers={"X-WP-CSRF": csrf},
        json={
            "return_url": "https://app.test/dashboard/billing",
            "organization_id": "forged-tenant",
            "customer_id": "ctm_attacker_selected",
        },
    )

    assert res.status_code == 200, res.text
    assert route.called
    assert res.json()["portal_url"] == "https://sandbox-login.paddle.com/portal"


@pytest.mark.asyncio
async def test_production_never_falls_back_to_stripe(
    paddle_web_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, csrf = await _register_onboard(paddle_web_client, "paddle-production@example.com")
    monkeypatch.setattr(app_module, "_paddle_billing_service", None)
    monkeypatch.setattr(app_module, "_stripe_service", object())
    monkeypatch.setattr(app_module.settings, "environment", "production")

    res = await paddle_web_client.post(
        "/api/web/billing/checkout",
        headers={"X-WP-CSRF": csrf},
        json={"plan": "PRO"},
    )

    assert res.status_code == 503
    assert "Paddle billing is required in production." in res.text
