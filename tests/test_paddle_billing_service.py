# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
import respx
from httpx import Response

from responsibleai.billing.paddle_service import (
    PADDLE_SUBSCRIPTION_ENTITLEMENT_EVENTS,
    PaddleBillingError,
    PaddleBillingService,
    PaddleCheckoutRequest,
)
from responsibleai.rbac.models import Plan


@pytest.mark.asyncio
@respx.mock
async def test_paddle_checkout_binds_org_in_custom_data() -> None:
    service = PaddleBillingService(
        "test_api_key",
        {Plan.PRO: "pri_pro_test", Plan.ENTERPRISE: "pri_ent_test"},
        environment="production",
    )
    route = respx.post("https://api.paddle.com/transactions").mock(
        return_value=Response(
            200,
            json={"data": {"checkout": {"url": "https://checkout.paddle.com/sess_123"}}},
        )
    )
    url = await service.create_checkout_session(
        PaddleCheckoutRequest(
            org_id="org-server-bound",
            plan=Plan.PRO,
            success_url="https://whitepact.com/billing/success",
            customer_email="owner@example.com",
        )
    )
    assert url.endswith("sess_123")
    body = route.calls.last.request.content.decode()
    assert "org-server-bound" in body
    assert "pri_pro_test" in body


def test_paddle_subscription_entitlement_event_allowlist() -> None:
    required = {
        "subscription.created",
        "subscription.activated",
        "subscription.canceled",
        "subscription.past_due",
    }
    assert required <= PADDLE_SUBSCRIPTION_ENTITLEMENT_EVENTS


@pytest.mark.asyncio
async def test_paddle_rejects_unconfigured_plan_price() -> None:
    service = PaddleBillingService("key", {Plan.PRO: "pri_pro"}, environment="production")
    with pytest.raises(PaddleBillingError, match="ENTERPRISE"):
        await service.create_checkout_session(
            PaddleCheckoutRequest(
                org_id="org-1",
                plan=Plan.ENTERPRISE,
                success_url="https://whitepact.com/ok",
            )
        )


@pytest.mark.asyncio
@respx.mock
async def test_paddle_sandbox_uses_sandbox_api_and_server_price() -> None:
    service = PaddleBillingService(
        "pdl_sdbx_apikey_test",  # gitleaks:allow
        {Plan.PRO: "pri_server_selected"},
        environment="sandbox",
    )
    route = respx.post("https://sandbox-api.paddle.com/transactions").mock(
        return_value=Response(
            200,
            json={"data": {"checkout": {"url": "https://sandbox-checkout.paddle.com/ok"}}},
        )
    )

    await service.create_checkout_session(
        PaddleCheckoutRequest(
            org_id="org-server-bound",
            plan=Plan.PRO,
            success_url="https://whitepact.test/billing/success",
        )
    )

    assert route.called
    assert "pri_server_selected" in route.calls.last.request.content.decode()


@pytest.mark.asyncio
@respx.mock
async def test_paddle_production_uses_live_api() -> None:
    service = PaddleBillingService(
        "pdl_live_apikey_test",  # gitleaks:allow
        {Plan.PRO: "pri_live"},
        environment="production",
    )
    route = respx.post("https://api.paddle.com/transactions").mock(
        return_value=Response(
            200,
            json={"data": {"checkout": {"url": "https://checkout.paddle.com/ok"}}},
        )
    )

    await service.create_checkout_session(
        PaddleCheckoutRequest(
            org_id="org-server-bound",
            plan=Plan.PRO,
            success_url="https://whitepact.com/billing/success",
        )
    )

    assert route.called


@pytest.mark.parametrize(
    ("environment", "api_key"),
    [
        ("sandbox", "pdl_live_apikey_mismatch"),
        ("production", "pdl_sdbx_apikey_mismatch"),
    ],
)
def test_paddle_rejects_obviously_mismatched_credentials(environment: str, api_key: str) -> None:
    with pytest.raises(PaddleBillingError, match="does not match"):
        PaddleBillingService(api_key, {Plan.PRO: "pri_test"}, environment=environment)


@pytest.mark.parametrize("environment", [None, "staging", ""])
def test_paddle_service_requires_explicit_valid_environment(
    environment: str | None,
) -> None:
    with pytest.raises(PaddleBillingError, match="environment"):
        PaddleBillingService("key", {Plan.PRO: "pri_test"}, environment=environment)
