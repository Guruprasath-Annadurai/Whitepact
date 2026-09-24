# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-campaign batch 2: enterprise identity, MCP billing, governance workflows,
upstream, webhooks, evaluations, and incidents — error and deny paths in ``dashboard/app.py``."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from datetime import UTC, datetime

import pytest

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import _auth_failure_limiter, app, limiter, settings
from responsibleai.enterprise.preflight import DEV_IDENTITY_WEBHOOK_SECRET
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


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


def _sign_idv(payload: bytes, timestamp: str, secret: str = DEV_IDENTITY_WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), payload + timestamp.encode(), hashlib.sha256).hexdigest()


class TestEnterpriseIdentityDenyPaths:
    async def test_identity_verification_without_session_is_401(self, client: AsyncClient) -> None:
        r = await client.get("/api/enterprise/identity/verification")
        assert r.status_code == 401
        assert r.json()["error"] == "UNAUTHENTICATED"

    async def test_identity_verification_start_without_session_is_401(
        self, client: AsyncClient
    ) -> None:
        r = await client.post("/api/enterprise/identity/verification/start")
        assert r.status_code == 401

    async def test_org_verification_without_session_is_401(self, client: AsyncClient) -> None:
        r = await client.get("/api/enterprise/organizations/some-org/verification")
        assert r.status_code == 401

    async def test_enterprise_passkeys_list_without_session_is_401(
        self, client: AsyncClient
    ) -> None:
        r = await client.get("/api/enterprise/passkeys")
        assert r.status_code == 401

    async def test_enterprise_totp_start_without_session_is_401(self, client: AsyncClient) -> None:
        r = await client.post("/api/enterprise/mfa/totp/start")
        assert r.status_code == 401

    async def test_identity_webhook_invalid_signature_is_403(self, client: AsyncClient) -> None:
        ts = datetime.now(UTC).isoformat()
        payload = b'{"event_id":"evt-1","subject_id":"user-1","outcome":"VERIFIED"}'
        r = await client.post(
            "/api/enterprise/identity/verification/webhook",
            content=payload,
            headers={
                "X-Identity-Signature": "not-a-valid-signature",
                "X-Identity-Timestamp": ts,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 403
        assert r.json()["error"] == "PROVIDER_SIGNATURE_INVALID"

    async def test_identity_webhook_stale_timestamp_is_403(self, client: AsyncClient) -> None:
        ts = "2000-01-01T00:00:00+00:00"
        payload = json.dumps(
            {"event_id": "evt-stale", "subject_id": "user-1", "outcome": "VERIFIED"},
            separators=(",", ":"),
        ).encode()
        r = await client.post(
            "/api/enterprise/identity/verification/webhook",
            content=payload,
            headers={
                "X-Identity-Signature": _sign_idv(payload, ts),
                "X-Identity-Timestamp": ts,
                "Content-Type": "application/json",
            },
        )
        assert r.status_code == 403
        assert r.json()["error"] == "PROVIDER_SIGNATURE_INVALID"


class TestMcpBillingDenyPaths:
    async def test_mcp_usage_top_rejects_org_scoped_owner(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="MCP Top Co",
            slug="mcp-top-co",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get("/api/billing/usage/mcp/top", headers=_bearer(raw))
        assert r.status_code == 403
        assert "super-admin" in r.json()["message"].lower()

    async def test_mcp_usage_top_days_out_of_range_is_422(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage/mcp/top", params={"days": 0})
        assert r.status_code == 422

    async def test_mcp_usage_top_rejects_analyst_org_key(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="MCP Analyst Co",
            slug="mcp-analyst-co",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get("/api/billing/usage/mcp/top", headers=_bearer(raw))
        assert r.status_code == 403


class TestGovernanceWorkflowAndDelegationDeny:
    async def test_workflow_rules_require_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/workflow-rules")
        assert r.status_code == 400
        assert "org-scoped" in r.json()["message"].lower()

    async def test_workflow_rule_create_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/governance/workflow-rules",
            json={
                "rule_id": "seq-1",
                "action_types": ["a.create", "b.execute"],
                "window_minutes": 60,
            },
        )
        assert r.status_code == 400

    async def test_workflow_rule_create_rejects_short_sequence(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Workflow Co",
            slug="workflow-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/workflow-rules",
            json={"rule_id": "bad-seq", "action_types": ["only-one"], "window_minutes": 10},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_workflow_rule_delete_missing_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Workflow Co 2",
            slug="workflow-co-2",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.delete(
            "/api/governance/workflow-rules/does-not-exist",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_policy_reorder_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.post("/api/governance/policy/reorder", json={"rule_ids": ["r1"]})
        assert r.status_code == 400

    async def test_delegations_grant_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/governance/delegations",
            json={
                "to_identity_id": "agent-1",
                "granted_action_types": ["read"],
                "purpose": "probe",
            },
        )
        assert r.status_code == 400

    async def test_delegation_chain_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/delegations/some-id/chain")
        assert r.status_code == 400

    async def test_governance_resolve_invalid_outcome_is_422(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Approval Co",
            slug="approval-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/approvals/does-not-exist/resolve",
            json={"outcome": "MAYBE"},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_governance_resolve_missing_approval_is_404(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Approval Co 2",
            slug="approval-co-2",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/approvals/missing-id/resolve",
            json={"outcome": "APPROVED"},
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_governance_execute_missing_approval_is_404(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Execute Co",
            slug="execute-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/approvals/missing-id/execute",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_governance_evidence_outcome_missing_record_is_404(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Outcome Co",
            slug="outcome-co",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/governance/evidence/ev-missing/outcome",
            json={"status": "SUCCEEDED"},
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_supplychain_scan_rejects_empty_server_name(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/governance/supplychain/scan",
            json={"server_name": "", "tools": []},
        )
        assert r.status_code == 422


class TestUpstreamGovernanceDeny:
    async def test_upstream_list_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/upstream/servers")
        assert r.status_code == 400

    async def test_upstream_tools_requires_org_scoped_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/upstream/tools")
        assert r.status_code == 400

    async def test_upstream_register_rejects_loopback_url(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Upstream Co",
            slug="upstream-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers",
            json={"name": "local", "url": "http://127.0.0.1:9999/mcp"},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_upstream_call_unknown_server_is_governance_blocked(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Upstream Co 2",
            slug="upstream-co-2",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers/unknown-server/call",
            json={"tool_name": "probe", "arguments": {}, "purpose": "branch campaign"},
            headers=_bearer(raw),
        )
        assert r.status_code == 200
        body = r.json()
        assert body.get("error") == "governance_denied"
        assert "UNAPPROVED_MCP_SERVER" in str(body.get("reason_codes", []))

    async def test_upstream_delete_unknown_server_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Upstream Co 3",
            slug="upstream-co-3",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.delete(
            "/api/governance/upstream/servers/unknown-server",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_upstream_trust_unknown_server_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Trust Co",
            slug="trust-co",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get(
            "/api/governance/upstream/servers/does-not-exist/trust",
            headers=_bearer(raw),
        )
        assert r.status_code == 404


class TestWebhooksDenyPaths:
    async def test_create_webhook_invalid_event_type(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Webhook Co",
            slug="webhook-co",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["not_a_real_event"],
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 400
        assert "Invalid event" in r.json()["message"]

    async def test_create_webhook_unsafe_url(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Webhook Co 2",
            slug="webhook-co-2",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/webhooks",
            json={
                "url": "http://127.0.0.1/internal",
                "events": ["trust_score_changed"],
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 400
        assert "Invalid webhook URL" in r.json()["message"]

    async def test_create_webhook_weak_secret_is_422(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Webhook Co 3",
            slug="webhook-co-3",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["trust_score_changed"],
                "secret": "short",
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_delete_webhook_missing_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Webhook Co 4",
            slug="webhook-co-4",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.delete("/api/webhooks/missing-hook-id", headers=_bearer(raw))
        assert r.status_code == 404

    async def test_test_webhook_missing_is_404(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Webhook Co 5",
            slug="webhook-co-5",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/webhooks/test/missing-hook-id",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_viewer_cannot_create_webhook(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Webhook Viewer Co",
            slug="webhook-viewer-co",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/webhooks",
            json={
                "url": "https://example.com/hook",
                "events": ["trust_score_changed"],
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 403


class TestEvalAndIncidentsDeny:
    async def test_eval_results_limit_out_of_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/eval/results", params={"limit": 0})
        assert r.status_code == 422

    async def test_eval_compare_missing_model_fields_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/eval/compare",
            json={
                "model_a": "",
                "model_b": "b",
                "prompts": [{"id": "p1", "prompt": "hi"}],
                "responses_a": [{"prompt_id": "p1", "response": "a"}],
                "responses_b": [{"prompt_id": "p1", "response": "b"}],
            },
        )
        assert r.status_code == 422

    async def test_eval_benchmark_missing_model_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/eval/benchmark",
            json={"model": "", "suite": "truthfulqa", "responses": {"p1": "x"}},
        )
        assert r.status_code == 422

    async def test_incidents_create_invalid_type_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/incidents",
            json={
                "incident_type": "not_real",
                "severity": "medium",
                "description": "probe incident validation",
            },
        )
        assert r.status_code == 422

    async def test_incidents_create_empty_description_is_422(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/incidents",
            json={"incident_type": "other", "severity": "low", "description": ""},
        )
        assert r.status_code == 422

    async def test_incidents_get_missing_is_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/incidents/does-not-exist")
        assert r.status_code == 404

    async def test_incidents_list_days_out_of_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/incidents", params={"days": 0})
        assert r.status_code == 422

    async def test_viewer_cannot_create_incident(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Incident Viewer Co",
            slug="incident-viewer-co",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/incidents",
            json={
                "incident_type": "other",
                "severity": "low",
                "description": "viewer should not create",
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_incident_db_report_title_too_short(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/incident-db/report",
            json={
                "title": "hi",
                "description": "x" * 25,
                "affected_model": "m",
                "affected_provider": "openai",
            },
        )
        assert r.status_code == 422

    async def test_incident_db_pending_requires_super_admin(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Incident Mod Co",
            slug="incident-mod-co",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.get("/api/incident-db/pending", headers=_bearer(raw))
        assert r.status_code == 403
        assert "super-admin" in r.json()["message"].lower()


class TestAlertsAndBillingWebhooks:
    async def test_alerts_webhook_unconfigured_is_503(self, client: AsyncClient) -> None:
        r = await client.post("/api/alerts/webhook", json={"alerts": []})
        assert r.status_code == 503

    async def test_alerts_webhook_missing_bearer_is_401(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "alerts_webhook_token", "alerts-test-token")
        r = await client.post("/api/alerts/webhook", json={"alerts": []})
        assert r.status_code == 401

    async def test_alerts_webhook_invalid_bearer_is_401(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "alerts_webhook_token", "alerts-test-token")
        r = await client.post(
            "/api/alerts/webhook",
            json={"alerts": []},
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert r.status_code == 401

    async def test_paddle_webhook_malformed_signature_header(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "paddle_webhook_secret", "paddle-branch-campaign-secret")
        r = await client.post(
            "/api/billing/paddle/webhook",
            content=b"{}",
            headers={"Paddle-Signature": "not-key=value"},
        )
        assert r.status_code == 400
        assert "Malformed" in r.json()["message"]
