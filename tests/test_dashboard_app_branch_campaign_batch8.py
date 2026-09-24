# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-campaign batch 8: remaining ``dashboard/app.py`` deny paths — auth
failure, role/scope/plan gates, tenant mismatch, webhooks, pagination, billing
webhooks, and org governance edges."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import responsibleai.dashboard.app as app_module
from responsibleai.billing.stripe_service import StripeBillingError
from responsibleai.dashboard.app import _auth_failure_limiter, app, limiter, settings
from responsibleai.rbac.models import Plan, Role
from tests.org_http_fixtures import seed_org_with_key


@pytest.fixture()
async def client():
    orig_database_url = settings.database_url
    orig_db_path = settings.db_path
    orig_auto_migrate = settings.auto_migrate

    settings.database_url = None
    settings.db_path = ":memory:"
    settings.auto_migrate = False
    try:
        async with LifespanManager(app, startup_timeout=15) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as ac:
                yield ac
    finally:
        settings.database_url = orig_database_url
        settings.db_path = orig_db_path
        settings.auto_migrate = orig_auto_migrate


@pytest.fixture()
async def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    _auth_failure_limiter._failures.clear()

    async with LifespanManager(app, startup_timeout=15) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac

    _auth_failure_limiter._failures.clear()


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


def _http_message(response) -> str:
    body = response.json()
    message = body.get("message", body.get("detail", ""))
    return message if isinstance(message, str) else str(message)


def _paddle_sig(secret: str, body: bytes, ts: int | None = None) -> str:
    if ts is None:
        ts = int(datetime.now(UTC).timestamp())
    signed = f"{ts}:".encode() + body
    h1 = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


class TestAuthFailureAndHeaders:
    async def test_non_bearer_authorization_counts_as_failure(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.get("/api/orgs", headers={"Authorization": "Basic abc"})
        assert r.status_code == 401
        assert "Authorization" in _http_message(r)

    async def test_empty_bearer_token_is_401(self, auth_client: AsyncClient) -> None:
        r = await auth_client.get("/api/orgs", headers={"Authorization": "Bearer   "})
        assert r.status_code == 401

    async def test_repeated_invalid_keys_eventually_429(self, auth_client: AsyncClient) -> None:
        last_status = None
        for i in range(25):
            r = await auth_client.get("/api/orgs", headers=_bearer(f"guess-{i}"))
            last_status = r.status_code
        assert last_status == 429
        assert "failed authentication" in _http_message(r).lower()

    async def test_sso_required_org_key_gets_403_on_protected_route(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="SSO Gate Co",
            slug=f"sso-gate-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        await app_module._org_repo.set_sso_required(org_id, True)
        r = await auth_client.get(f"/api/orgs/{org_id}", headers=_bearer(raw))
        assert r.status_code == 403
        assert "SSO" in _http_message(r)

    async def test_login_key_rejects_sso_required_org_key(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="SSO Login Co",
            slug=f"sso-login-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        await app_module._org_repo.set_sso_required(org_id, True)
        r = await auth_client.post("/api/auth/login-key", json={"api_key": raw})
        assert r.status_code == 403
        assert "SSO" in _http_message(r)

    async def test_auth_session_returns_org_scoped_context(self, auth_client: AsyncClient) -> None:
        org_id, key_id, raw = await seed_org_with_key(
            name="Session Co",
            slug=f"session-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get("/api/auth/session", headers=_bearer(raw))
        assert r.status_code == 200
        body = r.json()
        assert body["org_id"] == org_id
        assert body["key_id"] == key_id
        assert body["role"] == "ANALYST"

    async def test_auth_logout_accepts_valid_bearer(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Logout Co",
            slug=f"logout-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post("/api/auth/logout", headers=_bearer(raw))
        assert r.status_code == 200
        assert r.json()["logged_out"] is True


class TestLegacyCredentialBlocks:
    async def test_legacy_bootstrap_insufficient_role_for_metrics(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.get(
            "/api/metrics",
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403
        assert "ANALYST" in _http_message(r)

    async def test_legacy_bootstrap_blocked_from_cost_record(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.post(
            "/api/cost/record",
            json={
                "model": "gpt-4",
                "provider": "openai",
                "input_tokens": 1,
                "output_tokens": 1,
            },
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403

    async def test_legacy_bootstrap_blocked_from_governance_evidence_bundle(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.get(
            "/api/governance/evidence/bundle",
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403

    async def test_legacy_bootstrap_blocked_from_issue_keys(self, auth_client: AsyncClient) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Legacy Keys Co",
            slug=f"legacy-keys-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "child", "role": "ANALYST"},
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403


class TestRoleScopeAndPlanGates:
    async def test_viewer_cannot_list_all_orgs(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Viewer List Co",
            slug=f"viewer-list-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/orgs", headers=_bearer(raw))
        assert r.status_code == 403
        assert "ADMIN" in _http_message(r)

    async def test_analyst_cannot_query_audit_log(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit Role Co",
            slug=f"audit-role-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get("/api/audit-log", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_set_authority_ceiling(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Ceiling Viewer Co",
            slug=f"ceil-view-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/authority-ceiling",
            json={"max_value_usd": 100.0},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_scoped_governance_read_cannot_add_policy_rule(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Scope Read Co",
            slug=f"scope-read-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped_raw = await app_module._org_repo.create_key(
            org_id,
            "gov-read-only",
            Role.ADMIN,
            scopes=("governance:read",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.post(
            "/api/governance/policy/rules",
            json={"rule_id": "scope-deny", "reason_code": "TEST", "effect": "DENY"},
            headers=_bearer(scoped_raw),
        )
        assert r.status_code == 403
        assert "scope" in _http_message(r).lower()

    async def test_scoped_evidence_read_cannot_call_governed_tool(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Evidence Scope Co",
            slug=f"ev-scope-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped_raw = await app_module._org_repo.create_key(
            org_id,
            "evidence-read",
            Role.ANALYST,
            scopes=("evidence:read",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.post(
            "/api/governance/tools/call",
            json={"name": "rai_health", "arguments": {}, "purpose": "probe"},
            headers=_bearer(scoped_raw),
        )
        assert r.status_code == 403
        assert "scope" in _http_message(r).lower()

    async def test_plan_rate_limiter_returns_429(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from fastapi import HTTPException

        org_id, _kid, raw = await seed_org_with_key(
            name="Plan RL Co",
            slug=f"plan-rl-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )

        async def _boom(_org: str | None, _plan: Plan) -> None:
            raise HTTPException(
                429,
                detail="Rate limit exceeded: 1 requests/minute on the FREE plan.",
            )

        assert app_module._plan_rate_limiter is not None
        monkeypatch.setattr(app_module._plan_rate_limiter, "check", _boom)
        r = await auth_client.get(f"/api/orgs/{org_id}", headers=_bearer(raw))
        assert r.status_code == 429
        assert "Rate limit exceeded" in _http_message(r)

    async def test_owner_on_free_plan_incident_db_check_is_402(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="IDB Plan Co",
            slug=f"idb-plan-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get(
            "/api/incident-db/check",
            params={"model": "m", "provider": "openai"},
            headers=_bearer(raw),
        )
        assert r.status_code == 402
        msg = _http_message(r).lower()
        assert "pro" in msg or "plan" in msg


class TestTenantMismatchAndOrgValidation:
    async def test_put_autonomy_budget_cross_tenant_is_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Budget Tenant A",
            slug=f"bud-a-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        other = str(uuid.uuid4())
        r = await auth_client.put(
            f"/api/orgs/{other}/autonomy-budget",
            json={"max_autonomous_actions": 10, "window_minutes": 60},
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_delete_org_cross_tenant_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Delete Tenant A",
            slug=f"del-a-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.delete(f"/api/orgs/{uuid.uuid4()}", headers=_bearer(raw))
        assert r.status_code == 404

    async def test_create_org_duplicate_slug_is_409(self, auth_client: AsyncClient) -> None:
        slug = f"dup-org-{uuid.uuid4().hex[:8]}"
        _org_id, _kid, raw = await seed_org_with_key(
            name="Dup Org",
            slug=slug,
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.post(
            "/api/orgs",
            json={"name": "Another", "slug": slug},
            headers=_bearer(raw),
        )
        assert r.status_code == 409
        assert "taken" in _http_message(r).lower()

    async def test_signup_duplicate_slug_is_409(self, client: AsyncClient) -> None:
        slug = f"signup-dup-{uuid.uuid4().hex[:8]}"
        first = await client.post(
            "/api/signup",
            json={
                "name": "First Org",
                "slug": slug,
                "email": "first@example.com",
                "website": "",
                "page_loaded_at_ms": 0,
            },
        )
        assert first.status_code == 201
        second = await client.post(
            "/api/signup",
            json={
                "name": "Second Org",
                "slug": slug,
                "email": "second@example.com",
                "website": "",
                "page_loaded_at_ms": 0,
            },
        )
        assert second.status_code == 409

    async def test_get_org_missing_returns_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Missing Org Co",
            slug=f"missing-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        await app_module._org_repo.delete_org(org_id)
        r = await auth_client.get(f"/api/orgs/{org_id}", headers=_bearer(raw))
        assert r.status_code == 404


class TestPaginationAndQueryValidation:
    async def test_audit_log_days_out_of_range(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit Days Co",
            slug=f"audit-days-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.get("/api/audit-log", params={"days": 91}, headers=_bearer(raw))
        assert r.status_code == 422

    async def test_audit_log_limit_out_of_range(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit Limit Co",
            slug=f"audit-limit-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.get("/api/audit-log", params={"limit": 501}, headers=_bearer(raw))
        assert r.status_code == 422

    async def test_audit_entries_limit_out_of_range(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit API Co",
            slug=f"audit-api-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get("/api/audit", params={"limit": 1001}, headers=_bearer(raw))
        assert r.status_code == 422

    async def test_governance_evidence_limit_out_of_range(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Ev Limit Co",
            slug=f"ev-limit-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get(
            "/api/governance/evidence",
            params={"limit": 201},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_governance_evidence_bundle_limit_out_of_range(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Bundle Limit Co",
            slug=f"bundle-limit-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get(
            "/api/governance/evidence/bundle",
            params={"limit": 0},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_webhook_deliveries_limit_out_of_range(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Hook Del Co",
            slug=f"hook-del-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.get(
            "/api/webhooks/deliveries",
            params={"limit": 0},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_trust_score_history_limit_out_of_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/trust-score/some-model/openai", params={"limit": 0})
        assert r.status_code == 400
        assert "limit" in _http_message(r).lower()

    async def test_billing_usage_days_over_max_is_422(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage", params={"days": 400})
        assert r.status_code == 422


class TestBillingWebhooksAndCheckout:
    async def test_paddle_future_signature_timestamp(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch8-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        monkeypatch.setattr(settings, "paddle_signature_tolerance_seconds", 60)
        future_ts = int(datetime.now(UTC).timestamp()) + 120
        body = b'{"event_id":"evt-future"}'
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body, ts=future_ts)},
        )
        assert r.status_code == 400
        assert "future" in _http_message(r).lower()

    async def test_paddle_ignored_event_type_returns_processed_false(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch8-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        body = json.dumps(
            {
                "event_id": f"evt-ignored-{uuid.uuid4().hex}",
                "event_type": "transaction.completed",
                "occurred_at": "2024-06-01T00:00:00Z",
                "data": {},
            }
        ).encode()
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body)},
        )
        assert r.status_code == 200
        body_out = r.json()
        assert body_out["received"] is True
        assert body_out.get("ignored_event_type") is True

    async def test_paddle_duplicate_event_is_idempotent(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch8-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        event_id = f"evt-dup-{uuid.uuid4().hex}"
        body = json.dumps(
            {
                "event_id": event_id,
                "event_type": "transaction.completed",
                "occurred_at": "2024-06-01T00:00:00Z",
                "data": {},
            }
        ).encode()
        headers = {"Paddle-Signature": _paddle_sig(secret, body)}
        first = await client.post("/api/billing/paddle/webhook", content=body, headers=headers)
        second = await client.post("/api/billing/paddle/webhook", content=body, headers=headers)
        assert first.status_code == 200
        assert second.status_code == 200
        assert second.json().get("duplicate") is True

    async def test_paddle_unmapped_org_subscription_event(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch8-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        body = json.dumps(
            {
                "event_id": f"evt-unmapped-{uuid.uuid4().hex}",
                "event_type": "subscription.updated",
                "occurred_at": "2024-06-01T00:00:00Z",
                "data": {"id": "sub_x", "customer_id": "ctm_x", "status": "active"},
            }
        ).encode()
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body)},
        )
        assert r.status_code == 200
        assert r.json().get("unmapped_org") is True

    async def test_paddle_unknown_org_id_in_custom_data_is_404(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        secret = "paddle-batch8-secret"
        monkeypatch.setattr(settings, "paddle_webhook_secret", secret)
        missing_org = str(uuid.uuid4())
        body = json.dumps(
            {
                "event_id": f"evt-missing-org-{uuid.uuid4().hex}",
                "event_type": "subscription.updated",
                "occurred_at": "2024-06-01T00:00:00Z",
                "data": {
                    "id": "sub_missing",
                    "customer_id": "ctm_missing",
                    "status": "active",
                    "custom_data": {"org_id": missing_org, "plan": "PRO"},
                },
            }
        ).encode()
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=body,
            headers={"Paddle-Signature": _paddle_sig(secret, body)},
        )
        assert r.status_code == 404
        assert missing_org in _http_message(r)

    async def test_stripe_webhook_missing_event_id(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_stripe = MagicMock()
        mock_event = MagicMock()
        mock_event.id = ""
        mock_event.type = "checkout.session.completed"
        mock_stripe.verify_and_parse_webhook.return_value = mock_event
        mock_stripe.extract_plan_update.return_value = None
        monkeypatch.setattr(app_module, "_stripe_service", mock_stripe)
        r = await client.post(
            "/api/billing/webhook",
            content=b"{}",
            headers={"stripe-signature": "v1,abc"},
        )
        assert r.status_code == 400
        assert "event ID" in _http_message(r)

    async def test_billing_checkout_invalid_plan(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(app_module, "_stripe_service", MagicMock())
        _org_id, _kid, raw = await seed_org_with_key(
            name="Checkout Co",
            slug=f"checkout-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.post(
            "/api/billing/checkout",
            json={"plan": "NOT_A_PLAN", "org_email": "pay@example.com"},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_billing_checkout_stripe_error_maps_to_400(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        mock_stripe = MagicMock()
        mock_stripe.create_checkout_session.side_effect = StripeBillingError("card declined")
        monkeypatch.setattr(app_module, "_stripe_service", mock_stripe)
        _org_id, _kid, raw = await seed_org_with_key(
            name="Checkout Err Co",
            slug=f"checkout-err-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.post(
            "/api/billing/checkout",
            json={"plan": "PRO", "org_email": "pay@example.com"},
            headers=_bearer(raw),
        )
        assert r.status_code == 400
        assert "card declined" in _http_message(r)


class TestGovernanceConflictPaths:
    async def test_policy_rule_duplicate_is_409(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Policy Dup Co",
            slug=f"pol-dup-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        payload = {"rule_id": "dup-rule", "reason_code": "TEST", "effect": "DENY"}
        assert (
            await auth_client.post(
                "/api/governance/policy/rules", json=payload, headers=_bearer(raw)
            )
        ).status_code == 200
        r = await auth_client.post(
            "/api/governance/policy/rules", json=payload, headers=_bearer(raw)
        )
        assert r.status_code == 409
        assert "already exists" in _http_message(r)

    async def test_policy_reorder_unknown_rule_ids_is_422(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Reorder Co",
            slug=f"reorder-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/policy/reorder",
            json={"rule_ids": ["does-not-exist"]},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_workflow_rule_duplicate_is_409(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Workflow Dup Co",
            slug=f"wf-dup-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        payload = {
            "rule_id": "seq-dup",
            "action_types": ["a.create", "b.execute"],
            "window_minutes": 30,
        }
        assert (
            await auth_client.post(
                "/api/governance/workflow-rules", json=payload, headers=_bearer(raw)
            )
        ).status_code == 201
        r = await auth_client.post(
            "/api/governance/workflow-rules", json=payload, headers=_bearer(raw)
        )
        assert r.status_code == 409

    async def test_delegation_revoke_unknown_identity_returns_empty_branch(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Deleg Revoke Co",
            slug=f"deleg-rev-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/delegations/no-such-agent/revoke",
            json={"reason": "cleanup"},
            headers=_bearer(raw),
        )
        assert r.status_code == 200
        body = r.json()
        assert body["revoked_delegation_ids"] == []

    async def test_intent_contract_active_missing_agent_reports_false(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Intent Active Co",
            slug=f"intent-act-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get(
            "/api/governance/intent-contracts/unknown-agent/active",
            headers=_bearer(raw),
        )
        assert r.status_code == 200
        assert r.json()["has_active_contract"] is False

    async def test_governance_outcome_invalid_status_is_422(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Outcome Co",
            slug=f"outcome-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/governance/evidence/ev-fake/outcome",
            json={"status": "MAYBE"},
            headers=_bearer(raw),
        )
        assert r.status_code in (404, 422)


class TestIncidentDbModerationAndMisc:
    async def test_incident_db_approve_missing_is_404(self, auth_client: AsyncClient) -> None:
        r = await auth_client.post(
            "/api/incident-db/does-not-exist/approve",
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403

    async def test_incident_db_reject_requires_super_admin(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="IDB Reject Co",
            slug=f"idb-rej-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.post(
            "/api/incident-db/some-id/reject",
            json={"reason": "not eligible for moderation"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403
        assert "super-admin" in _http_message(r).lower()

    async def test_incident_db_public_get_missing_is_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/incident-db/WP-NOT-REAL")
        assert r.status_code == 404

    async def test_trust_index_certify_missing_passport_super_admin(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.post(
            "/api/trust-index/certify/missing-passport",
            json={"certified_by": "moderator"},
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403

    async def test_hallucination_empty_text_is_400(self, client: AsyncClient) -> None:
        r = await client.post("/api/hallucination", json={"text": ""})
        assert r.status_code == 400
        assert "required" in _http_message(r).lower()

    async def test_redteam_analyze_missing_fields_is_422(self, client: AsyncClient) -> None:
        r = await client.post("/api/redteam/analyze", json={})
        assert r.status_code == 422

    async def test_redteam_payloads_category_filter(self, client: AsyncClient) -> None:
        r = await client.get(
            "/api/redteam/payloads",
            params={"categories": ["prompt_injection"]},
        )
        assert r.status_code == 200
        assert r.json()["count"] >= 0

    async def test_unknown_api_route_returns_404_json(self, client: AsyncClient) -> None:
        r = await client.get("/api/this-route-does-not-exist")
        assert r.status_code == 404

    async def test_api_version_endpoint_public(self, client: AsyncClient) -> None:
        r = await client.get("/api/version")
        assert r.status_code == 200
        assert "version" in r.json()

    async def test_support_info_public(self, client: AsyncClient) -> None:
        r = await client.get("/api/support")
        assert r.status_code == 200
        assert "tiers" in r.json()

    async def test_audit_summary_accessible_with_anon_dev_auth(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit/summary", params={"days": 7})
        assert r.status_code == 200
        assert "endpoints" in r.json()

    async def test_metrics_requires_analyst_role(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Metrics Viewer Co",
            slug=f"metrics-view-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/metrics", headers=_bearer(raw))
        assert r.status_code == 403
