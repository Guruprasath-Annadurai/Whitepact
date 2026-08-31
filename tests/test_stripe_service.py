# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for StripeService -- previously entirely untested (0% branch
coverage). `stripe` is an optional [billing] extra not installed in
this environment (or in CI's default install matrix) -- a fake module
is injected into sys.modules so StripeService's lazy `import stripe`
succeeds and every real branch of its own logic (plan validation,
checkout kwargs construction, webhook signature verification, event ->
PlanUpdate mapping) is genuinely exercised, without needing the real
SDK or a live Stripe account.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from responsibleai.billing.stripe_service import (
    StripeBillingError,
    StripeNotConfiguredError,
    StripeService,
)
from responsibleai.rbac.models import Plan


@pytest.fixture()
def fake_stripe_module(monkeypatch):
    """Injects a fake `stripe` module into sys.modules so
    `StripeService.__init__`'s lazy `import stripe` succeeds, returning
    the fake module so tests can configure its Mock call sites."""
    fake = types.ModuleType("stripe")
    fake.api_key = None
    fake.checkout = SimpleNamespace(Session=MagicMock())
    fake.billing_portal = SimpleNamespace(Session=MagicMock())
    fake.Webhook = MagicMock()
    monkeypatch.setitem(sys.modules, "stripe", fake)
    yield fake
    monkeypatch.delitem(sys.modules, "stripe", raising=False)


@pytest.fixture()
def service(fake_stripe_module):
    return StripeService(
        secret_key="sk_test_fake",
        webhook_secret="whsec_fake",
        price_ids={Plan.PRO: "price_pro", Plan.ENTERPRISE: "price_enterprise"},
    )


class TestInit:
    def test_raises_not_configured_when_stripe_package_missing(self, monkeypatch):
        monkeypatch.delitem(sys.modules, "stripe", raising=False)
        # Force the import to fail regardless of what's actually installed.
        real_import = __import__

        def _blocking_import(name, *args, **kwargs):
            if name == "stripe":
                raise ImportError("no stripe here")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr("builtins.__import__", _blocking_import)
        with pytest.raises(StripeNotConfiguredError):
            StripeService(secret_key="sk", webhook_secret=None, price_ids={})

    def test_sets_api_key_on_construction(self, service, fake_stripe_module):
        assert fake_stripe_module.api_key == "sk_test_fake"


class TestCreateCheckoutSession:
    async def test_rejects_free_plan(self, service):
        with pytest.raises(StripeBillingError, match="FREE plan"):
            await service.create_checkout_session(
                "org-1", "a@b.com", Plan.FREE, "https://ok", "https://cancel"
            )

    async def test_rejects_unconfigured_price(self, fake_stripe_module):
        svc = StripeService(secret_key="sk_test_fake", webhook_secret="whsec_fake", price_ids={})
        with pytest.raises(StripeBillingError, match="No Stripe price"):
            await svc.create_checkout_session(
                "org-1", "a@b.com", Plan.PRO, "https://ok", "https://cancel"
            )

    async def test_uses_existing_customer_id_when_provided(self, service, fake_stripe_module):
        fake_stripe_module.checkout.Session.create.return_value = SimpleNamespace(
            url="https://checkout"
        )
        url = await service.create_checkout_session(
            "org-1",
            "a@b.com",
            Plan.PRO,
            "https://ok",
            "https://cancel",
            existing_customer_id="cus_123",
        )
        assert url == "https://checkout"
        kwargs = fake_stripe_module.checkout.Session.create.call_args.kwargs
        assert kwargs["customer"] == "cus_123"
        assert "customer_email" not in kwargs

    async def test_uses_org_email_when_no_existing_customer(self, service, fake_stripe_module):
        fake_stripe_module.checkout.Session.create.return_value = SimpleNamespace(
            url="https://checkout"
        )
        await service.create_checkout_session(
            "org-1", "a@b.com", Plan.PRO, "https://ok", "https://cancel"
        )
        kwargs = fake_stripe_module.checkout.Session.create.call_args.kwargs
        assert kwargs["customer_email"] == "a@b.com"
        assert "customer" not in kwargs

    async def test_no_customer_field_when_neither_provided(self, service, fake_stripe_module):
        fake_stripe_module.checkout.Session.create.return_value = SimpleNamespace(
            url="https://checkout"
        )
        await service.create_checkout_session(
            "org-1", None, Plan.PRO, "https://ok", "https://cancel"
        )
        kwargs = fake_stripe_module.checkout.Session.create.call_args.kwargs
        assert "customer" not in kwargs
        assert "customer_email" not in kwargs


class TestCreateBillingPortalSession:
    async def test_returns_hosted_url(self, service, fake_stripe_module):
        fake_stripe_module.billing_portal.Session.create.return_value = SimpleNamespace(
            url="https://portal"
        )
        url = await service.create_billing_portal_session("cus_123", "https://return")
        assert url == "https://portal"


class TestVerifyAndParseWebhook:
    def test_raises_when_webhook_secret_missing(self, fake_stripe_module):
        svc = StripeService(secret_key="sk", webhook_secret=None, price_ids={})
        with pytest.raises(StripeBillingError, match="not configured"):
            svc.verify_and_parse_webhook(b"payload", "sig")

    def test_returns_parsed_event_on_success(self, service, fake_stripe_module):
        fake_event = SimpleNamespace(type="checkout.session.completed")
        fake_stripe_module.Webhook.construct_event.return_value = fake_event
        result = service.verify_and_parse_webhook(b"payload", "sig")
        assert result is fake_event

    def test_wraps_signature_verification_failure(self, service, fake_stripe_module):
        fake_stripe_module.Webhook.construct_event.side_effect = ValueError("bad signature")
        with pytest.raises(StripeBillingError, match="Webhook verification failed"):
            service.verify_and_parse_webhook(b"payload", "sig")


def _event(etype: str, data_object) -> SimpleNamespace:
    return SimpleNamespace(type=etype, data=SimpleNamespace(object=data_object))


class TestExtractPlanUpdate:
    def test_none_when_no_data_object(self, service):
        event = SimpleNamespace(type="checkout.session.completed", data=None)
        assert service.extract_plan_update(event) is None

    def test_none_for_unhandled_event_type(self, service):
        event = _event("some.other.event", SimpleNamespace())
        assert service.extract_plan_update(event) is None

    # -- checkout.session.completed --

    def test_checkout_completed_full_mapping(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1", "plan": "PRO"},
            client_reference_id=None,
            customer="cus_1",
            subscription="sub_1",
        )
        result = service.extract_plan_update(_event("checkout.session.completed", obj))
        assert result.org_id == "org-1"
        assert result.plan == Plan.PRO
        assert result.stripe_customer_id == "cus_1"
        assert result.stripe_subscription_id == "sub_1"

    def test_checkout_completed_falls_back_to_client_reference_id(self, service):
        obj = SimpleNamespace(
            metadata={"plan": "PRO"},
            client_reference_id="org-2",
            customer="cus_1",
            subscription=None,
        )
        result = service.extract_plan_update(_event("checkout.session.completed", obj))
        assert result.org_id == "org-2"
        assert result.stripe_subscription_id is None

    def test_checkout_completed_none_when_missing_org_id(self, service):
        obj = SimpleNamespace(metadata={"plan": "PRO"}, client_reference_id=None, customer="cus_1")
        assert service.extract_plan_update(_event("checkout.session.completed", obj)) is None

    def test_checkout_completed_none_when_missing_plan(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1"}, client_reference_id=None, customer="cus_1"
        )
        assert service.extract_plan_update(_event("checkout.session.completed", obj)) is None

    def test_checkout_completed_none_when_missing_customer(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1", "plan": "PRO"}, client_reference_id=None, customer=None
        )
        assert service.extract_plan_update(_event("checkout.session.completed", obj)) is None

    # -- customer.subscription.updated --

    def test_subscription_updated_active_keeps_plan(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1", "plan": "ENTERPRISE"},
            customer="cus_1",
            id="sub_1",
            current_period_end=1893456000,
            status="active",
        )
        result = service.extract_plan_update(_event("customer.subscription.updated", obj))
        assert result.plan == Plan.ENTERPRISE
        assert result.plan_renews_at is not None

    def test_subscription_updated_trialing_keeps_plan(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1", "plan": "PRO"},
            customer="cus_1",
            id="sub_1",
            current_period_end=None,
            status="trialing",
        )
        result = service.extract_plan_update(_event("customer.subscription.updated", obj))
        assert result.plan == Plan.PRO
        assert result.plan_renews_at is None

    def test_subscription_updated_inactive_downgrades_to_free(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1", "plan": "PRO"},
            customer="cus_1",
            id="sub_1",
            current_period_end=None,
            status="canceled",
        )
        result = service.extract_plan_update(_event("customer.subscription.updated", obj))
        assert result.plan == Plan.FREE

    def test_subscription_updated_no_plan_metadata_downgrades_to_free(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1"},
            customer="cus_1",
            id="sub_1",
            current_period_end=None,
            status="active",
        )
        result = service.extract_plan_update(_event("customer.subscription.updated", obj))
        assert result.plan == Plan.FREE

    def test_subscription_updated_none_when_missing_org_id(self, service):
        obj = SimpleNamespace(
            metadata={"plan": "PRO"},
            customer="cus_1",
            id="sub_1",
            current_period_end=None,
            status="active",
        )
        assert service.extract_plan_update(_event("customer.subscription.updated", obj)) is None

    def test_subscription_updated_none_when_missing_customer(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1", "plan": "PRO"},
            customer=None,
            id="sub_1",
            current_period_end=None,
            status="active",
        )
        assert service.extract_plan_update(_event("customer.subscription.updated", obj)) is None

    def test_subscription_updated_no_subscription_id(self, service):
        obj = SimpleNamespace(
            metadata={"org_id": "org-1", "plan": "PRO"},
            customer="cus_1",
            id=None,
            current_period_end=None,
            status="active",
        )
        result = service.extract_plan_update(_event("customer.subscription.updated", obj))
        assert result.stripe_subscription_id is None

    # -- customer.subscription.deleted --

    def test_subscription_deleted_downgrades_to_free(self, service):
        obj = SimpleNamespace(metadata={"org_id": "org-1"}, customer="cus_1")
        result = service.extract_plan_update(_event("customer.subscription.deleted", obj))
        assert result.plan == Plan.FREE
        assert result.stripe_subscription_id is None

    def test_subscription_deleted_none_when_missing_org_id(self, service):
        obj = SimpleNamespace(metadata={}, customer="cus_1")
        assert service.extract_plan_update(_event("customer.subscription.deleted", obj)) is None

    def test_subscription_deleted_none_when_missing_customer(self, service):
        obj = SimpleNamespace(metadata={"org_id": "org-1"}, customer=None)
        assert service.extract_plan_update(_event("customer.subscription.deleted", obj)) is None
