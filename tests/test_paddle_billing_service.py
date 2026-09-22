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
    service = PaddleBillingService("key", {Plan.PRO: "pri_pro"})
    with pytest.raises(PaddleBillingError, match="ENTERPRISE"):
        await service.create_checkout_session(
            PaddleCheckoutRequest(
                org_id="org-1",
                plan=Plan.ENTERPRISE,
                success_url="https://whitepact.com/ok",
            )
        )
