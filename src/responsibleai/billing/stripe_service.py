"""Stripe billing integration — converts MCP/API plan tiers into recurring revenue.

Design intent
-------------
This module never touches the database directly. It only talks to Stripe and
returns plain data. The caller (dashboard/app.py) is responsible for updating
``organizations.plan`` via ``OrgRepository.set_plan`` after a webhook confirms
a subscription change. Keeping billing DB-agnostic makes it independently
testable and keeps Stripe's SDK out of the core dependency graph — it's an
optional extra (``pip install rai-governance-platform[billing]``).

Flow
----
1. Org owner calls ``POST /api/v1/billing/checkout`` with a target plan.
2. ``StripeService.create_checkout_session`` returns a hosted Stripe URL.
3. User completes payment on Stripe's page.
4. Stripe calls ``POST /api/v1/billing/webhook`` with a signed event.
5. ``verify_and_parse_webhook`` validates the signature, ``extract_plan_update``
   maps the event to (org_id, Plan, subscription_id, renews_at).
6. The route handler persists that via ``OrgRepository.set_plan``.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from responsibleai.rbac.models import Plan


class StripeBillingError(Exception):
    """Raised when a Stripe API call or webhook verification fails."""


class StripeNotConfigured(StripeBillingError):
    """Raised when billing is invoked without STRIPE_SECRET_KEY configured."""


@dataclass(frozen=True)
class PlanUpdate:
    org_id: str
    plan: Plan
    stripe_customer_id: str
    stripe_subscription_id: str | None
    plan_renews_at: str | None


class StripeService:
    """Thin async wrapper around the Stripe Python SDK.

    The SDK is imported lazily so the ``stripe`` package stays an optional
    dependency — self-hosted / open-source users never need it installed.
    """

    def __init__(
        self,
        secret_key: str,
        webhook_secret: str | None,
        price_ids: dict[Plan, str],
    ) -> None:
        try:
            import stripe  # noqa: F401
        except ImportError as exc:
            raise StripeNotConfigured(
                "The 'stripe' package is required for billing. "
                "Install with: pip install 'rai-governance-platform[billing]'"
            ) from exc

        self._stripe = stripe
        self._stripe.api_key = secret_key
        self._webhook_secret = webhook_secret
        self._price_ids = price_ids

    async def create_checkout_session(
        self,
        org_id: str,
        org_email: str | None,
        plan: Plan,
        success_url: str,
        cancel_url: str,
        existing_customer_id: str | None = None,
    ) -> str:
        """Create a Stripe Checkout session for a plan upgrade. Returns the hosted URL."""
        if plan == Plan.FREE:
            raise StripeBillingError("Cannot create a checkout session for the FREE plan.")

        price_id = self._price_ids.get(plan)
        if not price_id:
            raise StripeBillingError(f"No Stripe price configured for plan {plan.value}.")

        def _create() -> str:
            kwargs: dict[str, object] = {
                "mode": "subscription",
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "client_reference_id": org_id,
                "metadata": {"org_id": org_id, "plan": plan.value},
                "subscription_data": {"metadata": {"org_id": org_id, "plan": plan.value}},
            }
            if existing_customer_id:
                kwargs["customer"] = existing_customer_id
            elif org_email:
                kwargs["customer_email"] = org_email
            session = self._stripe.checkout.Session.create(**kwargs)
            return str(session.url)

        return await asyncio.to_thread(_create)

    async def create_billing_portal_session(self, customer_id: str, return_url: str) -> str:
        """Create a Stripe Billing Portal session so orgs can self-manage/cancel subscriptions."""

        def _create() -> str:
            session = self._stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
            return str(session.url)

        return await asyncio.to_thread(_create)

    def verify_and_parse_webhook(self, payload: bytes, sig_header: str) -> object:
        """Verify the Stripe signature and return the parsed Event object."""
        if not self._webhook_secret:
            raise StripeBillingError("STRIPE_WEBHOOK_SECRET is not configured.")
        try:
            return self._stripe.Webhook.construct_event(
                payload, sig_header, self._webhook_secret
            )
        except Exception as exc:  # signature or payload error
            raise StripeBillingError(f"Webhook verification failed: {exc}") from exc

    def extract_plan_update(self, event: object) -> PlanUpdate | None:
        """Map a Stripe event to a plan change, or None if not actionable.

        Handles: checkout.session.completed, customer.subscription.updated,
        customer.subscription.deleted.
        """
        etype = getattr(event, "type", None)
        data_object = getattr(getattr(event, "data", None), "object", None)
        if data_object is None:
            return None

        if etype == "checkout.session.completed":
            metadata = getattr(data_object, "metadata", {}) or {}
            org_id = metadata.get("org_id") or getattr(data_object, "client_reference_id", None)
            plan_str = metadata.get("plan")
            customer_id = getattr(data_object, "customer", None)
            subscription_id = getattr(data_object, "subscription", None)
            if not org_id or not plan_str or not customer_id:
                return None
            return PlanUpdate(
                org_id=str(org_id),
                plan=Plan(plan_str),
                stripe_customer_id=str(customer_id),
                stripe_subscription_id=str(subscription_id) if subscription_id else None,
                plan_renews_at=None,
            )

        if etype == "customer.subscription.updated":
            metadata = getattr(data_object, "metadata", {}) or {}
            org_id = metadata.get("org_id")
            plan_str = metadata.get("plan")
            customer_id = getattr(data_object, "customer", None)
            subscription_id = getattr(data_object, "id", None)
            period_end = getattr(data_object, "current_period_end", None)
            status = getattr(data_object, "status", None)
            if not org_id or not customer_id:
                return None
            renews_at = (
                datetime.fromtimestamp(period_end, tz=UTC).isoformat() if period_end else None
            )
            # Downgrade to FREE if subscription is no longer active/trialing.
            effective_plan = (
                Plan(plan_str) if plan_str and status in ("active", "trialing") else Plan.FREE
            )
            return PlanUpdate(
                org_id=str(org_id),
                plan=effective_plan,
                stripe_customer_id=str(customer_id),
                stripe_subscription_id=str(subscription_id) if subscription_id else None,
                plan_renews_at=renews_at,
            )

        if etype == "customer.subscription.deleted":
            metadata = getattr(data_object, "metadata", {}) or {}
            org_id = metadata.get("org_id")
            customer_id = getattr(data_object, "customer", None)
            if not org_id or not customer_id:
                return None
            return PlanUpdate(
                org_id=str(org_id),
                plan=Plan.FREE,
                stripe_customer_id=str(customer_id),
                stripe_subscription_id=None,
                plan_renews_at=None,
            )

        return None
