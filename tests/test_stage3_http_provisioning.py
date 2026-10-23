# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real TCP onboarding plus separate UDS controller; nonproduction identities."""

import httpx
import pytest
from scripts.engineering.m13i1_customer_journey import serve
from sqlalchemy import text

import responsibleai.dashboard.app as dashboard
from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.db.org_repository import OrgRepository
from tests.stage3_controller_helpers import controller_process
from tests.test_stage3_controller_postgres import controller as controller
from tests.test_v1_exactly_one_effect import _prepare_org


@pytest.mark.asyncio
async def test_real_http_onboarding_and_three_creation_paths(
    controller, monkeypatch, seed_runtime_authority
):
    service, _, _, _, _ = controller
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(
        RestoreReadinessGate(provider=service.provider, db_engine=service.engine)
    )
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(service.provider.path))
    monkeypatch.setenv("WHITEPACT_STORE_B_KEY", service.provider._secret_key)
    for name, value in {
        "database_url": service.engine.raw.url.render_as_string(hide_password=False),
        "auto_migrate": False,
        "auth_enabled": True,
        "api_keys": [],
        "web_auth_dev_tokens": True,
        "web_session_secure": False,
        "web_verification_delivery_url": None,
        "environment": "development",
    }.items():
        monkeypatch.setattr(dashboard.settings, name, value)
    monkeypatch.setattr(dashboard.limiter, "enabled", False)
    try:
        async with controller_process(service, monkeypatch):
            async with serve(dashboard.app) as origin:
                async with httpx.AsyncClient(base_url=origin, timeout=30) as browser:
                    tenant, key = await _prepare_org(
                        browser,
                        monkeypatch,
                        seed_runtime_authority,
                        service.engine.raw.url.render_as_string(hide_password=False),
                    )
                    assert service.ledger.completion(tenant) is not None
                    # A DEVELOPER key must not pass the OWNER-only API boundary,
                    # even when accompanied by a valid human session.
                    response = await browser.post(
                        "/api/v1/orgs",
                        headers={
                            "Authorization": f"Bearer {key}",
                            "X-WP-CSRF": browser.cookies["wp_csrf"],
                        },
                        json={"name": "Second Tenant", "slug": "second-tenant"},
                    )
                    assert response.status_code == 403
                    second_org = await OrgRepository(service.engine).create_org(
                        "Second Tenant",
                        "second-tenant",
                        session_token=browser.cookies["wp_session"],
                        csrf=browser.cookies["wp_csrf"],
                    )
                    second = second_org.id
                    assert service.ledger.completion(second) is not None
                    response = await browser.post(
                        "/api/enterprise/workspaces",
                        headers={
                            "X-WP-CSRF": browser.cookies["wp_csrf"],
                        },
                        json={
                            "name": "Third Tenant",
                            "slug": "third-tenant",
                            "kind": "ORGANIZATION",
                        },
                    )
                    assert response.status_code == 200, response.status_code
                    third = response.json()["organization"]["id"]
                    assert service.ledger.completion(third) is not None
                    async with service.engine.raw.connect() as connection:
                        assert (
                            await connection.scalar(
                                text(
                                    "SELECT count(*) FROM tenant_provisioning_records WHERE state='COMPLETE'"
                                )
                            )
                            == 3
                        )
                        assert (
                            await connection.scalar(
                                text("SELECT count(*) FROM tenant_provisioning_outbox")
                            )
                            == 3
                        )
                    assert (
                        len(
                            {
                                service.provider.get_state(item).generation_id
                                for item in (tenant, second, third)
                            }
                        )
                        == 3
                    )
    finally:
        set_restore_readiness_gate(previous)
