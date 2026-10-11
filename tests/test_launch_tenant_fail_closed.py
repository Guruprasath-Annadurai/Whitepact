# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tenant reads fail closed when the caller has no organization."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.db.engine import create_engine
from responsibleai.db.repositories import CostRepository, TrustRepository
from responsibleai.enterprise.preflight import (
    HostedEnterpriseSecurityError,
    assert_production_authentication_required,
)
from responsibleai.trust.score import TrustScoreEngine
from responsibleai.webhooks.manager import WebhookManager
from responsibleai.webhooks.models import WebhookConfig, WebhookEvent


def _score():
    return TrustScoreEngine().compute(
        fairness=0.8,
        privacy=0.8,
        security=0.8,
        robustness=0.8,
        compliance=0.8,
        authenticity=0.8,
    )


def test_production_refuses_disabled_authentication() -> None:
    settings = SimpleNamespace(environment="production", is_production=True, auth_enabled=False)
    with pytest.raises(HostedEnterpriseSecurityError, match="cannot be disabled"):
        assert_production_authentication_required(settings)


def test_development_may_disable_authentication() -> None:
    settings = SimpleNamespace(environment="development", is_production=False, auth_enabled=False)
    assert_production_authentication_required(settings)


@pytest.mark.asyncio
async def test_missing_org_does_not_read_another_tenants_trust_or_cost() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    try:
        trust = TrustRepository(engine, alert_threshold=5.0)
        await trust.record("model", "openai", _score(), org_id="org-a")
        history = await trust.history("model", "openai", org_id=None)
        assert history == []
        models = await trust.all_models(org_id=None)
        assert models == []
        own = await trust.history("model", "openai", org_id="org-a")
        assert len(own) == 1

        cost = CostRepository(engine, policy=BudgetPolicy(monthly_limit_usd=1000.0))
        await cost.record(
            TokenUsage.create(
                provider="openai",
                model="gpt-4o",
                input_tokens=10,
                output_tokens=10,
                org_id="org-a",
            )
        )
        assert await cost.total_cost(org_id=None) == 0.0
        assert await cost.total_cost(org_id="org-a") > 0
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_webhook_tenant_bound_cannot_list_or_delete_another_org() -> None:
    manager = WebhookManager()
    foreign = manager.register(
        WebhookConfig(
            url="https://example.com/hook", events=[WebhookEvent.DRIFT_ALERT], org_id="org-a"
        )
    )
    local = manager.register(
        WebhookConfig(
            url="https://example.com/local", events=[WebhookEvent.DRIFT_ALERT], org_id=None
        )
    )

    visible = manager.list_webhooks(org_id=None, tenant_bound=True)
    assert [item.id for item in visible] == [local.id]
    assert await manager.remove_and_persist(foreign.id, org_id=None, tenant_bound=True) is False
    assert manager.get(foreign.id) is not None
    assert await manager.remove_and_persist(local.id, org_id=None, tenant_bound=True) is True
