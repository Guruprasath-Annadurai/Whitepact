# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-campaign HTTP tests for uncovered /api/* routes and fail-closed paths in
``dashboard/app.py``. Uses the same in-memory LifespanManager client pattern as
``test_dashboard_api.py`` (auth disabled by default); auth-on cases use a local
fixture to exercise 401/403/legacy-deny without changing the default client."""

from __future__ import annotations

import os
import time

import pytest

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai import __version__
from responsibleai.dashboard.app import _auth_failure_limiter, app, limiter, settings
from responsibleai.rbac.models import Role
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


class TestOpsAndApiVersioning:
    async def test_v1_restore_status_alias(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/restore/status")
        assert r.status_code == 200
        body = r.json()
        assert "is_admitted" in body
        assert "status" in body

    async def test_restore_reconcile_returns_json(self, client: AsyncClient) -> None:
        r = await client.post("/api/restore/reconcile", json={})
        assert r.status_code in (200, 500)
        assert "status" in r.json() or "error" in r.json()

    async def test_k8s_readiness_probe(self, client: AsyncClient) -> None:
        r = await client.get("/readyz")
        assert r.status_code in (200, 503)
        assert "database" in r.json()

    async def test_k8s_liveness_probe(self, client: AsyncClient) -> None:
        r = await client.get("/livez")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    async def test_api_version_headers_on_health(self, client: AsyncClient) -> None:
        r = await client.get("/api/health")
        assert r.headers.get("X-API-Version") == __version__
        assert r.headers.get("X-API-Min-Version") == "1.0.0"

    async def test_v1_prefix_rewrites_to_core_route(self, client: AsyncClient) -> None:
        r = await client.get("/api/v1/billing/plans")
        assert r.status_code == 200
        assert "FREE" in r.json()

    async def test_robots_txt_is_public(self, client: AsyncClient) -> None:
        r = await client.get("/robots.txt")
        assert r.status_code == 200
        assert "User-agent" in r.text or "Disallow" in r.text


class TestValidationEnvelope:
    async def test_governed_tool_call_missing_purpose_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/governance/tools/call",
            json={"name": "rai_health", "arguments": {}},
        )
        assert r.status_code == 422
        body = r.json()
        assert body["error"] == "validation_error"
        assert "detail" in body

    async def test_eval_compare_empty_prompts_rejected(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/eval/compare",
            json={
                "model_a": "a",
                "model_b": "b",
                "prompts": [],
                "responses_a": [{"prompt_id": "p1", "response": "x"}],
                "responses_b": [{"prompt_id": "p1", "response": "y"}],
            },
        )
        assert r.status_code == 422

    async def test_eval_benchmark_unknown_suite_pattern_rejected(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/eval/benchmark",
            json={
                "model": "m",
                "suite": "not-a-suite",
                "responses": {"p1": "answer"},
            },
        )
        assert r.status_code == 422

    async def test_eval_dataset_scan_requires_nonempty_texts(self, client: AsyncClient) -> None:
        r = await client.post("/api/eval/dataset-scan", json={"texts": []})
        assert r.status_code == 422

    async def test_audit_log_limit_out_of_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit-log", params={"limit": 0})
        assert r.status_code == 422

    async def test_governance_evidence_limit_out_of_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/evidence", params={"limit": 0})
        assert r.status_code == 422


class TestLegacyAnonFailClosed:
    """Auth disabled → legacy anon context with no org_id; org-scoped routes fail closed."""

    async def test_governance_evidence_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/evidence")
        assert r.status_code == 400
        assert "org-scoped" in r.json()["message"].lower()

    async def test_governance_approvals_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/approvals")
        assert r.status_code == 400

    async def test_governance_policy_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/policy")
        assert r.status_code == 400

    async def test_governance_tool_call_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/governance/tools/call",
            json={"name": "rai_health", "arguments": {}, "purpose": "health check"},
        )
        assert r.status_code == 400

    async def test_billing_checkout_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/billing/checkout",
            json={"plan": "PRO", "org_email": "billing@example.com"},
        )
        assert r.status_code in (400, 503)

    async def test_mcp_usage_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage/mcp")
        assert r.status_code == 400

    async def test_stripe_webhook_unconfigured_is_503(self, client: AsyncClient) -> None:
        r = await client.post("/api/billing/webhook", content=b"{}", headers={})
        assert r.status_code == 503

    async def test_paddle_webhook_unconfigured_is_503(self, client: AsyncClient) -> None:
        r = await client.post("/api/billing/paddle/webhook", content=b"{}", headers={})
        assert r.status_code == 503


class TestAuthEnabledFailClosed:
    async def test_missing_bearer_on_protected_route_is_401(self, auth_client: AsyncClient) -> None:
        r = await auth_client.get("/api/orgs")
        assert r.status_code == 401

    async def test_invalid_bearer_is_401(self, auth_client: AsyncClient) -> None:
        r = await auth_client.get(
            "/api/orgs", headers={"Authorization": "Bearer definitely-not-valid"}
        )
        assert r.status_code == 401

    async def test_legacy_bootstrap_key_blocked_from_governance_read(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.get(
            "/api/governance/policy",
            headers={"Authorization": "Bearer bootstrap-test-key"},
        )
        assert r.status_code == 403
        assert r.json()["error"] == "LEGACY_CREDENTIAL_FORBIDDEN"

    async def test_analyst_cannot_add_policy_rule(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Branch Campaign Co",
            slug="branch-campaign-co",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/governance/policy/rules",
            json={
                "rule_id": "deny-all",
                "reason_code": "TEST",
                "effect": "DENY",
            },
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 403

    async def test_scoped_key_missing_governance_write_scope(
        self, auth_client: AsyncClient
    ) -> None:
        from responsibleai.dashboard import app as app_module

        org_id, _kid, _ = await seed_org_with_key(
            name="Scope Co",
            slug="scope-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped_raw = await app_module._org_repo.create_key(
            org_id,
            "read-only-governance",
            Role.ADMIN,
            scopes=("governance:read",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.post(
            "/api/governance/policy/rules",
            json={
                "rule_id": "scope-test",
                "reason_code": "TEST",
                "effect": "ALLOW",
            },
            headers={"Authorization": f"Bearer {scoped_raw}"},
        )
        assert r.status_code == 403
        assert "scope" in r.json()["message"].lower()


class TestGovernanceOrgScopedErrors:
    async def test_unknown_governed_tool_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Tool Co",
            slug="tool-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/tools/call",
            json={"name": "not_a_real_tool", "arguments": {}, "purpose": "probe"},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 404

    async def test_invalid_policy_effect_is_422(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Policy Co",
            slug="policy-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/policy/rules",
            json={
                "rule_id": "bad-effect",
                "reason_code": "TEST",
                "effect": "MAYBE",
            },
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 422

    async def test_remove_missing_policy_rule_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Policy Co 2",
            slug="policy-co-2",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.delete(
            "/api/governance/policy/rules/does-not-exist",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 404

    async def test_eval_benchmark_prompts_unknown_suite_is_400(self, client: AsyncClient) -> None:
        r = await client.get("/api/eval/benchmark/prompts/not-real")
        assert r.status_code == 400
        assert "Unknown suite" in r.json()["message"]

    async def test_governance_bundle_verify_rejects_empty_bundle(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Bundle Co",
            slug="bundle-co",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/governance/evidence/bundle/verify",
            json={},
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["valid"] is False


class TestSignupAndOrgValidation:
    async def test_signup_honeypot_rejected(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/signup",
            json={
                "name": "Bot Inc",
                "slug": "bot-inc-signup",
                "email": "founder@example.com",
                "website": "http://spam.example",
                "page_loaded_at_ms": int(time.time() * 1000) - 5000,
            },
        )
        assert r.status_code == 400

    async def test_signup_invalid_slug_pattern_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/signup",
            json={
                "name": "Bad Slug",
                "slug": "NOT lower case",
                "email": "founder@example.com",
                "website": "",
                "page_loaded_at_ms": 0,
            },
        )
        assert r.status_code == 422

    async def test_create_org_invalid_slug_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/orgs",
            json={"name": "X", "slug": "INVALID SLUG"},
        )
        assert r.status_code == 422

    async def test_cross_tenant_org_path_returns_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Tenant A",
            slug="tenant-a-bc",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get(
            "/api/orgs/other-org-id",
            headers={"Authorization": f"Bearer {raw}"},
        )
        assert r.status_code == 404


class TestPaddleWebhookSignatureGate:
    async def test_paddle_webhook_missing_signature_header(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paddle_webhook_secret", "test-secret-for-branch-campaign")
        r = await client.post("/api/billing/paddle/webhook", content=b"{}", headers={})
        assert r.status_code == 400
        assert "Paddle-Signature" in r.json()["message"]
