# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Protected HTTP replacement, with reference identity and scoped test authority.

Requires real disposable PG16/controller fixtures; not canonical identity
acceptance. Three tests mock isolation; one requires actual Docker.
No production authority or bypass is introduced.
"""

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import httpx
import pytest
from sqlalchemy import func, select

import responsibleai.dashboard.app as dashboard
from responsibleai.db import ApprovalRepository, PolicyRepository
from responsibleai.db.engine import governance_approvals, governance_execution_nonces
from responsibleai.db.org_repository import OrgRepository
from responsibleai.governance.execution import InternalToolExecutor
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.isolation.errors import IsolationFilesystemPermissionError
from tests.test_customer_real_approval_journey import (
    PURPOSE,
    _execute,
    _resolve,
)


@pytest.fixture
async def option_a_live(monkeypatch, seed_runtime_authority):
    from scripts.engineering.m13_stage3_customer_fixture import isolated_provisioning_controller
    from scripts.engineering.m13i1_customer_journey import serve
    from scripts.engineering.m13i2_customer_journey import (
        configured_settings,
        isolated_startup_store_b,
    )
    from sdk.python.rai_client.governance import GovernanceRuntimeClient

    from responsibleai.dashboard.signup_guard import SignupRateWindow
    from tests.pg_test_url import isolated_pg_url
    from tests.test_v1_customer_journey import _upgrade_head
    from tests.test_v1_exactly_one_effect import _prepare_org

    # Fixture account setup is not a signup-abuse qualification target.
    monkeypatch.setattr(dashboard.limiter, "enabled", False)
    monkeypatch.setattr(
        dashboard, "_signup_window", SignupRateWindow(max_per_window=1000, window_seconds=3600)
    )

    async for database in isolated_pg_url("wp_option_a_http"):
        await _upgrade_head(database)
        settings = {
            "database_url": database,
            "auto_migrate": False,
            "auth_enabled": True,
            "api_keys": [],
            "environment": "development",
            "web_auth_dev_tokens": True,
            "web_session_secure": False,
            "web_verification_delivery_url": None,
        }
        # Existing explicit disposable installation/controller, bound to this
        # exact empty database and fresh Store B. Never seed/reset READY.
        with isolated_startup_store_b(), configured_settings(settings):
            async with (
                isolated_provisioning_controller(database, authorized_bootstrap=True),
                serve(dashboard.app) as origin,
            ):
                async with httpx.AsyncClient(base_url=origin, timeout=30) as browser:
                    org_id, key = await _prepare_org(
                        browser, monkeypatch, seed_runtime_authority, database
                    )
                    yield browser, GovernanceRuntimeClient(key, base_url=origin), org_id, key


@pytest.fixture
async def replacement_customer(option_a_live, seed_runtime_authority, monkeypatch):
    browser, sdk, org_id, key = option_a_live
    principal = await OrgRepository(dashboard._db_engine).authenticate(key)
    assert principal is not None
    # Existing explicit TEST authority fixture; not legitimate provider enrollment.
    await seed_runtime_authority(
        dashboard._db_engine,
        organization_id=org_id,
        principal_id=principal.key_id,
        action_types=("rai_health",),
        targets=("rai_health",),
        purpose=PURPOSE,
    )
    await PolicyRepository(dashboard._db_engine).add_rule(
        org_id,
        PolicyRule(
            rule_id="option-a-health-review",
            reason_code="OPTION_A_REQUIRES_HUMAN_REVIEW",
            effect=GovernanceDecision.REQUIRE_APPROVAL,
            action_types=frozenset({"rai_health"}),
        ),
    )
    backend = SimpleNamespace(
        preflight=Mock(side_effect=IsolationFilesystemPermissionError("private host diagnostic")),
        execute=AsyncMock(return_value={"status": "ok"}),
    )
    # Inject only the isolation boundary. Normal HTTP identity, tenant, authority,
    # policy, approval and durable nonce repositories remain in the real path.
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.InternalToolExecutor",
        lambda *, nonce_repo=None, **kwargs: InternalToolExecutor(
            nonce_repo=nonce_repo, broker=backend
        ),
    )
    return browser, sdk, org_id, key, backend


async def nonce_count(org_id):
    async with dashboard._db_engine.raw.connect() as conn:
        return await conn.scalar(
            select(func.count())
            .select_from(governance_execution_nonces)
            .where(governance_execution_nonces.c.organization_id == org_id)
        )


async def prove_blocked(customer):
    browser, sdk, org_id, _, backend = customer
    original = await sdk.call_tool("rai_health", purpose=PURPOSE)
    assert original.requires_approval and original.approval_id
    approved = await _resolve(browser, original.approval_id, "APPROVED")
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"
    refused = await _execute(browser, original.approval_id)
    assert refused.status_code == 503 and refused.json()["execution_status"] == "BLOCKED"
    assert "private host" not in refused.text
    assert await nonce_count(org_id) == 0
    repo = ApprovalRepository(dashboard._db_engine)
    assert (await repo.get(original.approval_id)).status.value == "CONSUMED"
    assert (await _execute(browser, original.approval_id)).status_code == 409
    backend.execute.assert_not_awaited()
    return original.approval_id


async def test_fresh_request_uses_protected_http_and_requires_new_approval(replacement_customer):
    browser, sdk, org_id, _, backend = replacement_customer
    original_id = await prove_blocked(replacement_customer)
    fresh = await sdk.call_tool("rai_health", purpose=PURPOSE)
    assert fresh.requires_approval and fresh.approval_id != original_id
    # Neither the previous human vote nor repaired infrastructure authorizes it.
    backend.preflight.side_effect = None
    assert (await _execute(browser, fresh.approval_id)).status_code == 409
    no_csrf = await browser.post(
        f"/api/v1/web/approvals/{fresh.approval_id}/resolve", json={"outcome": "APPROVED"}
    )
    assert no_csrf.status_code == 403
    assert (await _resolve(browser, fresh.approval_id, "APPROVED")).status_code == 200
    executed = await _execute(browser, fresh.approval_id)
    assert executed.status_code == 200 and executed.json()["execution_status"] == "SUCCEEDED"
    assert await nonce_count(org_id) == 1
    backend.execute.assert_awaited_once()
    repo = ApprovalRepository(dashboard._db_engine)
    for identifier in (original_id, fresh.approval_id):
        saved = await repo.get(identifier)
        assert saved.status.value == "CONSUMED" and saved.organization_id == org_id
        assert saved.authentication_method and saved.authority_version
        assert saved.revocation_epoch is not None
        evidence = await dashboard._evidence_repo.get_latest_for_approval(org_id, identifier)
        assert evidence is not None
        outcome = await dashboard._outcome_repo.get_for_org(evidence.evidence_id, org_id)
        assert outcome.status.value == ("BLOCKED" if identifier == original_id else "SUCCEEDED")
    assert (await _execute(browser, original_id)).status_code == 409


async def test_outcome_write_failure_returns_unknown_http_without_fabricated_record(
    replacement_customer, monkeypatch
):
    """Actual PG/HTTP accounting failure, simulated isolation refusal and failed write."""
    browser, sdk, org_id, _, backend = replacement_customer
    pending = await sdk.call_tool("rai_health", purpose=PURPOSE)
    assert pending.requires_approval and pending.approval_id
    approved = await _resolve(browser, pending.approval_id, "APPROVED")
    assert approved.status_code == 200 and approved.json()["status"] == "APPROVED"
    failed_write = AsyncMock(side_effect=OSError("/srv/private credential=must-not-leak"))
    monkeypatch.setattr(dashboard._outcome_repo, "record", failed_write)
    response = await _execute(browser, pending.approval_id)
    assert response.status_code == 503
    assert response.json()["code"] == "ISOLATION_RUNTIME_UNAVAILABLE"
    assert response.json()["execution_status"] == "UNKNOWN"
    assert "Reconcile" in response.json()["message"]
    for diagnostic in ("/srv/private", "credential", "must-not-leak", "private host"):
        assert diagnostic not in response.text
    failed_write.assert_awaited_once()
    backend.execute.assert_not_awaited()
    saved = await ApprovalRepository(dashboard._db_engine).get(pending.approval_id)
    assert saved.status.value == "CONSUMED" and saved.organization_id == org_id
    assert await nonce_count(org_id) == 0
    evidence = await dashboard._evidence_repo.get_latest_for_approval(org_id, pending.approval_id)
    assert evidence is not None
    # Query the real database through the unchanged read path: no outcome was saved.
    assert await dashboard._outcome_repo.get_for_org(evidence.evidence_id, org_id) is None
    assert (await _execute(browser, pending.approval_id)).status_code == 409


async def test_replacement_rejects_revoked_credential_without_new_approval(replacement_customer):
    from sdk.python.rai_client.governance import GovernanceRequestError

    browser, sdk, org_id, key, backend = replacement_customer
    original_id = await prove_blocked(replacement_customer)
    principal = await OrgRepository(dashboard._db_engine).authenticate(key)
    revoked = await browser.delete(
        f"/api/v1/web/api-keys/{principal.key_id}",
        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
    )
    assert revoked.status_code == 200
    with pytest.raises(GovernanceRequestError) as denied:
        await sdk.call_tool("rai_health", purpose=PURPOSE)
    assert denied.value.status_code == 401
    async with dashboard._db_engine.raw.connect() as conn:
        count = await conn.scalar(
            select(func.count())
            .select_from(governance_approvals)
            .where(
                governance_approvals.c.org_id == org_id,
                governance_approvals.c.action_type == "rai_health",
            )
        )
    assert count == 1
    assert (
        await ApprovalRepository(dashboard._db_engine).get(original_id)
    ).status.value == "CONSUMED"
    backend.execute.assert_not_awaited()


@pytest.mark.usefixtures("real_container_host")
async def test_fresh_approved_http_request_executes_in_real_docker(
    replacement_customer, monkeypatch
):
    """Full HTTP-to-container component path; reference assurance is not canonical IDV."""
    from responsibleai.isolation.broker import IsolationBroker
    from responsibleai.isolation.container_backend import DockerContainerBackend

    image = os.environ.get("WHITEPACT_TEST_RUNTIME_IMAGE")
    assert image, "Approved native runtime image must be provisioned"
    browser, sdk, org_id, _, backend = replacement_customer
    original_id = await prove_blocked(replacement_customer)
    # Use actual Docker for the fresh attempt. No same-process fallback or tool mock.
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    actual = IsolationBroker(backend=DockerContainerBackend(image_name=image))
    backend.preflight.side_effect = actual.preflight
    backend.execute.side_effect = actual.execute
    fresh = await sdk.call_tool("rai_health", purpose=PURPOSE)
    assert fresh.requires_approval and fresh.approval_id != original_id
    assert (await _execute(browser, fresh.approval_id)).status_code == 409
    assert (await _resolve(browser, fresh.approval_id, "APPROVED")).status_code == 200
    result = await _execute(browser, fresh.approval_id)
    assert result.status_code == 200 and result.json()["execution_status"] == "SUCCEEDED"
    assert await nonce_count(org_id) == 1
    backend.execute.assert_awaited_once()
    assert (await _execute(browser, fresh.approval_id)).status_code == 409
    assert (await _execute(browser, original_id)).status_code == 409
