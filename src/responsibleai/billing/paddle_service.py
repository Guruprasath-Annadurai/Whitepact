# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Paddle Billing — server-side checkout and customer portal (production provider)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import httpx

from responsibleai.rbac.models import Plan

PaddleEnvironment = Literal["sandbox", "production"]
PADDLE_API_BASES: dict[PaddleEnvironment, str] = {
    "sandbox": "https://sandbox-api.paddle.com",
    "production": "https://api.paddle.com",
}

# Subscription lifecycle events that may change org commercial entitlement.
PADDLE_SUBSCRIPTION_ENTITLEMENT_EVENTS: frozenset[str] = frozenset(
    {
        "subscription.created",
        "subscription.activated",
        "subscription.trialing",
        "subscription.updated",
        "subscription.past_due",
        "subscription.paused",
        "subscription.resumed",
        "subscription.canceled",
    }
)


class PaddleBillingError(Exception):
    """Raised when Paddle API calls fail or configuration is invalid."""


class PaddleNotConfiguredError(PaddleBillingError):
    """Raised when Paddle billing is invoked without API credentials."""


@dataclass(frozen=True)
class PaddleCheckoutRequest:
    org_id: str
    plan: Plan
    success_url: str
    customer_email: str | None = None
    existing_customer_id: str | None = None


class PaddleBillingService:
    """Thin async client for Paddle Billing v2 transactions and portal sessions."""

    def __init__(
        self,
        api_key: str,
        price_ids: dict[Plan, str],
        *,
        environment: str | None,
    ) -> None:
        if not api_key.strip():
            raise PaddleNotConfiguredError("Paddle API key is required.")
        if environment not in PADDLE_API_BASES:
            raise PaddleNotConfiguredError(
                "Paddle environment must be explicitly set to sandbox or production."
            )
        self._api_key = api_key.strip()
        if environment == "sandbox" and self._api_key.startswith("pdl_live_"):
            raise PaddleBillingError("Paddle API credential does not match sandbox environment.")
        if environment == "production" and self._api_key.startswith("pdl_sdbx_"):
            raise PaddleBillingError("Paddle API credential does not match production environment.")
        self._api_base = PADDLE_API_BASES[environment]
        self._price_ids = {plan: pid.strip() for plan, pid in price_ids.items() if pid}

    def resolve_price_id(self, plan: Plan) -> str:
        if plan == Plan.FREE:
            raise PaddleBillingError("Cannot create Paddle checkout for the FREE plan.")
        price_id = self._price_ids.get(plan)
        if not price_id:
            raise PaddleBillingError(f"No Paddle price configured for plan {plan.value}.")
        return price_id

    async def create_checkout_session(self, request: PaddleCheckoutRequest) -> str:
        price_id = self.resolve_price_id(request.plan)
        payload: dict[str, Any] = {
            "items": [{"price_id": price_id, "quantity": 1}],
            "custom_data": {"org_id": request.org_id},
            "checkout": {"url": request.success_url},
        }
        if request.existing_customer_id:
            payload["customer_id"] = request.existing_customer_id
        elif request.customer_email:
            payload["customer"] = {"email": request.customer_email}
        data = await self._post("/transactions", payload)
        checkout = (data.get("data") or {}).get("checkout") or {}
        url = checkout.get("url")
        if not url:
            raise PaddleBillingError("Paddle did not return a checkout URL.")
        return str(url)

    async def create_portal_session(self, customer_id: str, return_url: str) -> str:
        data = await self._post(
            f"/customers/{customer_id}/portal-sessions",
            {"return_url": return_url},
        )
        urls = (data.get("data") or {}).get("urls") or {}
        portal_url = urls.get("general") or urls.get("overview")
        if not portal_url:
            raise PaddleBillingError("Paddle did not return a customer portal URL.")
        return str(portal_url)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(base_url=self._api_base, timeout=30.0) as client:
            response = await client.post(path, json=body, headers=headers)
        if response.status_code >= 400:
            raise PaddleBillingError(
                f"Paddle API error {response.status_code}: {response.text[:500]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise PaddleBillingError("Paddle returned non-JSON response.") from exc
