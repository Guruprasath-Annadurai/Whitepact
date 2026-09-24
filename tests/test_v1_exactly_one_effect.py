# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exactly-one consequential effect through the governed execution path."""

from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import responsibleai.dashboard.app as app_module
from responsibleai.dashboard.signup_guard import SignupRateWindow
from responsibleai.db import PolicyRepository, create_engine
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.outcome import OutcomeStatus
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from tests.test_v1_customer_journey import (
    PURPOSE,
    _apply_idv,
    _invite_and_accept_admin,
    _onboard,
    _pg_url,
    _quorum_approve_and_execute,
    _register,
    _token_from_url,
    _upgrade_head,
    _verify_login,
)

OWNER_EMAIL = "effect.owner@example.com"
ADMIN_EMAIL = "effect.admin@example.com"


@pytest.fixture()
async def pg_url() -> AsyncIterator[str]:
    async for url in _pg_url("wp_effect"):
        yield url


@pytest.fixture()
async def journey_client(monkeypatch: pytest.MonkeyPatch, pg_url: str):
    await _upgrade_head(pg_url)
    monkeypatch.setattr(app_module.settings, "database_url", pg_url)
    monkeypatch.setattr(app_module.settings, "db_path", ":memory:")
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(app_module.settings, "paddle_webhook_secret", "paddle-test-placeholder")
    monkeypatch.setattr(app_module.settings, "environment", "development")
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=1000, window_seconds=3600.0)
    )
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client, pg_url


async def _prepare_org(client: AsyncClient, monkeypatch, seed_runtime_authority, pg_url: str):
    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    _, body = await _register(client, name="Effect Owner", email=OWNER_EMAIL)
    csrf = await _verify_login(client, OWNER_EMAIL, _token_from_url(body["verification_url"]))
    sess = await _onboard(client, csrf, "Effect Org")
    org_id = sess["organization"]["id"]
    user_id = sess["user"]["id"]
    await _apply_idv(client, user_id, "evt-effect")
    created = await client.post(
        "/api/v1/web/api-keys",
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
        json={
            "name": "effect-agent",
            "environment": "test",
            "scopes": ["governance:read", "governance:write", "evidence:read"],
        },
    )
    assert created.status_code == 201, created.text
    raw = created.json()["api_key"]
    await _invite_and_accept_admin(
        client, owner_email=OWNER_EMAIL, admin_email=ADMIN_EMAIL, admin_name="Effect Admin"
    )
    engine = create_engine(pg_url)
    await engine.init(auto_create_tables=False)
    from responsibleai.db.org_repository import OrgRepository

    ctx = await OrgRepository(engine).authenticate(raw)
    assert ctx is not None
    await seed_runtime_authority(
        engine,
        organization_id=org_id,
        principal_id=ctx.key_id,
        action_types=(SYNTHETIC_COUNTER_TOOL,),
        targets=(SYNTHETIC_COUNTER_TOOL,),
        purpose=PURPOSE,
    )
    await PolicyRepository(engine).add_rule(
        org_id,
        PolicyRule(
            rule_id="require-test-counter",
            reason_code="TEST_COUNTER_REQUIRES_APPROVAL",
            effect=GovernanceDecision.REQUIRE_APPROVAL,
            action_types=frozenset({SYNTHETIC_COUNTER_TOOL}),
        ),
    )
    await engine.close()
    return org_id, raw


async def _call(client: AsyncClient, raw: str, fail_after: bool = False):
    return await client.post(
        "/api/v1/governance/tools/call",
        headers={"Authorization": f"Bearer {raw}"},
        json={
            "name": SYNTHETIC_COUNTER_TOOL,
            "arguments": {"fail_after_effect": fail_after},
            "purpose": PURPOSE,
        },
    )


async def test_exactly_one_effect_approve_replay_deny_unknown(
    journey_client, monkeypatch, seed_runtime_authority
) -> None:
    client, pg_url = journey_client
    org_id, raw = await _prepare_org(client, monkeypatch, seed_runtime_authority, pg_url)

    before = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert before.status_code == 200
    assert before.json()["counter"] == 0
    assert before.json()["downstream_call_count"] == 0

    pending = await _call(client, raw)
    assert pending.status_code == 200, pending.text
    body = pending.json()
    assert body["error"] == "governance_approval_required"
    approval_id = body["approval_id"]
    mid = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert mid.json()["counter"] == 0
    assert mid.json()["downstream_call_count"] == 0

    await _quorum_approve_and_execute(
        client, approval_id, owner_email=OWNER_EMAIL, admin_email=ADMIN_EMAIL
    )
    csrf = client.cookies["wp_csrf"]
    after = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert after.json()["counter"] == 1
    assert after.json()["downstream_call_count"] == 1

    replay_resolve = await client.post(
        f"/api/v1/web/approvals/{approval_id}/resolve",
        headers={"X-WP-CSRF": csrf},
        json={"outcome": "APPROVED"},
    )
    assert replay_resolve.status_code == 409
    replay_execute = await client.post(
        f"/api/v1/web/approvals/{approval_id}/execute",
        headers={"X-WP-CSRF": csrf},
        json={},
    )
    assert replay_execute.status_code == 409
    engine = create_engine(pg_url)
    await engine.init(auto_create_tables=False)
    from sqlalchemy import select

    from responsibleai.db.engine import governance_execution_nonces
    from responsibleai.db.execution_nonce_repository import (
        ExecutionNonceRepository,
        NonceAlreadyConsumedError,
    )
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

    async with engine.raw.connect() as conn:
        nonce_row = (await conn.execute(select(governance_execution_nonces))).fetchone()
    assert nonce_row is not None
    epoch = (await RevocationEpochRepository(engine).current(org_id)).epoch
    try:
        await ExecutionNonceRepository(engine).consume(
            nonce_row.nonce,
            authorization_id=nonce_row.authorization_id,
            organization_id=org_id,
            expected_epoch=epoch,
        )
        raise AssertionError("nonce replay must be rejected")
    except NonceAlreadyConsumedError:
        pass
    await engine.close()
    still = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert still.json()["counter"] == 1
    assert still.json()["downstream_call_count"] == 1

    repeat = await _call(client, raw)
    assert repeat.json()["error"] == "governance_approval_required"
    still2 = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert still2.json()["counter"] == 1

    deny_id = repeat.json()["approval_id"]
    denied = await client.post(
        f"/api/v1/web/approvals/{deny_id}/resolve",
        headers={"X-WP-CSRF": csrf},
        json={"outcome": "DENIED"},
    )
    assert denied.status_code == 200
    deny_exec = await client.post(
        f"/api/v1/web/approvals/{deny_id}/execute",
        headers={"X-WP-CSRF": csrf},
        json={},
    )
    assert deny_exec.status_code == 409
    after_deny = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert after_deny.json()["counter"] == 1
    assert after_deny.json()["downstream_call_count"] == 1

    lost = await _call(client, raw, fail_after=True)
    unknown_id = lost.json()["approval_id"]
    payload = await _quorum_approve_and_execute(
        client, unknown_id, owner_email=OWNER_EMAIL, admin_email=ADMIN_EMAIL
    )
    csrf = client.cookies["wp_csrf"]
    assert payload["execution_status"] == OutcomeStatus.UNKNOWN.value
    assert payload["reconciliation_required"] is True
    assert payload.get("evidence_id")
    assert payload.get("outcome_id")
    assert "will not retry automatically" in payload["message"]
    unknown_state = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert unknown_state.json()["counter"] == 2
    assert unknown_state.json()["downstream_call_count"] == 2
    retry_unknown = await client.post(
        f"/api/v1/web/approvals/{unknown_id}/execute",
        headers={"X-WP-CSRF": csrf},
        json={},
    )
    assert retry_unknown.status_code == 409
    final = await client.get(
        "/api/v1/governance/test-counter", headers={"Authorization": f"Bearer {raw}"}
    )
    assert final.json()["counter"] == 2
    assert final.json()["downstream_call_count"] == 2

    engine = create_engine(pg_url)
    await engine.init(auto_create_tables=False)
    outcomes = []
    from sqlalchemy import select

    from responsibleai.db.engine import governance_outcomes

    async with engine.raw.connect() as conn:
        rows = (await conn.execute(select(governance_outcomes))).fetchall()
        outcomes = [row.status for row in rows]
    assert OutcomeStatus.UNKNOWN.value in outcomes
    await engine.close()
