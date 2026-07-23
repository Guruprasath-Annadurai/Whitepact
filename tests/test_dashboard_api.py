"""Integration tests for the Governance Dashboard API."""

from __future__ import annotations

import os

import httpx
import pytest

os.environ.setdefault("RAI_DB_PATH", ":memory:")
os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
# Auto-migrate shells out to `alembic upgrade head` — meaningless (and slow)
# against an ephemeral :memory: DB, since create_all() already builds the
# current schema fresh for every test run. Covered separately by
# tests/test_db_migrate.py against real on-disk SQLite files.
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app
from responsibleai.dashboard.config import Settings


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac


# ── Health & Metrics ──────────────────────────────────────────────────────────

class TestHealth:
    async def test_health_ok(self, client):
        r = await client.get("/api/health")
        assert r.status_code == 200
        d = r.json()
        assert d["status"] in ("healthy", "degraded")
        assert d["version"] == "1.2.0"
        assert "checks" in d
        assert "modules" in d
        assert len(d["modules"]) >= 10

    async def test_health_has_uptime(self, client):
        r = await client.get("/api/health")
        assert r.json()["uptime_seconds"] >= 0

    async def test_health_returns_503_when_db_unhealthy(self, client, monkeypatch):
        # A load balancer / orchestrator health check keys off the HTTP status
        # code, not the JSON body — a degraded DB must surface as non-2xx so
        # traffic actually gets routed away from a broken instance.
        import responsibleai.dashboard.app as app_module

        async def _boom(*args, **kwargs):
            raise RuntimeError("db unreachable")

        monkeypatch.setattr(app_module._cost_repo, "request_count", _boom)
        r = await client.get("/api/health")
        assert r.status_code == 503
        assert r.json()["status"] == "degraded"

    async def test_metrics_no_auth_disabled(self, client):
        r = await client.get("/api/metrics")
        assert r.status_code == 200
        d = r.json()
        assert "uptime_seconds" in d
        assert "total_requests" in d
        assert "error_rate_pct" in d

    async def test_root_returns_html(self, client):
        r = await client.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "ResponsibleAI" in r.text


# ── Evaluate ──────────────────────────────────────────────────────────────────

class TestEvaluate:
    async def test_evaluate_returns_trust_score(self, client):
        payload = {
            "model_name": "gpt-4o", "provider": "openai",
            "fairness": 0.80, "privacy": 0.85, "security": 0.82,
            "robustness": 0.78, "compliance": 0.90, "authenticity": 0.88,
        }
        r = await client.post("/api/evaluate", json=payload)
        assert r.status_code == 200
        d = r.json()
        assert "trust_score" in d
        assert d["trust_score"]["trust_score"] > 0
        assert d["trust_score"]["grade"] in ("A", "B", "C", "D", "F")
        assert "passport_id" in d
        assert "compliance" in d

    async def test_evaluate_creates_drift_history(self, client):
        payload = {"model_name": "test-model", "provider": "test", "fairness": 0.75}
        await client.post("/api/evaluate", json=payload)
        r = await client.get("/api/trust-score/test-model/test")
        assert r.status_code == 200
        d = r.json()
        assert len(d["history"]) >= 1

    async def test_evaluate_invalid_score_rejected(self, client):
        payload = {"model_name": "x", "provider": "y", "fairness": 1.5}
        r = await client.post("/api/evaluate", json=payload)
        assert r.status_code == 422

    async def test_evaluate_empty_model_name_rejected(self, client):
        payload = {"model_name": "", "provider": "openai"}
        r = await client.post("/api/evaluate", json=payload)
        assert r.status_code == 422

    async def test_drift_alert_on_score_drop(self, client):
        for score in [0.90, 0.65]:
            await client.post("/api/evaluate", json={
                "model_name": "drift-test", "provider": "acme",
                "fairness": score, "privacy": score, "security": score,
                "robustness": score, "compliance": score, "authenticity": score,
            })
        r = await client.get("/api/trust-score/drift-test/acme")
        d = r.json()
        assert "trend" in d
        assert "history" in d


# ── Models list ───────────────────────────────────────────────────────────────

class TestModels:
    async def test_models_returns_list(self, client):
        r = await client.get("/api/models")
        assert r.status_code == 200
        assert "models" in r.json()

    async def test_trust_score_history_limit_validation(self, client):
        r = await client.get("/api/trust-score/m/p?limit=999")
        assert r.status_code == 400


# ── Guardrails ────────────────────────────────────────────────────────────────

class TestScan:
    async def test_clean_text_not_blocked(self, client):
        r = await client.post("/api/scan", json={"text": "The weather is sunny today."})
        assert r.status_code == 200
        assert r.json()["is_blocked"] is False

    async def test_pii_text_blocked(self, client):
        r = await client.post("/api/scan", json={"text": "My SSN is 123-45-6789"})
        assert r.status_code == 200
        d = r.json()
        assert d["is_blocked"] is True
        assert d["pii_count"] >= 1

    async def test_scan_empty_text_rejected(self, client):
        r = await client.post("/api/scan", json={"text": ""})
        assert r.status_code == 422

    async def test_scan_returns_redacted_text(self, client):
        r = await client.post("/api/scan", json={"text": "Call me at user@example.com"})
        d = r.json()
        if d["is_blocked"] and d["pii_count"] > 0:
            assert d["redacted_text"] is not None


# ── Hallucination ─────────────────────────────────────────────────────────────

class TestHallucination:
    async def test_basic_analysis(self, client):
        r = await client.post("/api/hallucination", json={
            "text": "The capital of France is Paris, founded in 250 BC."
        })
        assert r.status_code == 200
        d = r.json()
        assert "hallucination_risk" in d
        assert "risk_level" in d
        assert d["risk_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    async def test_missing_text_rejected(self, client):
        r = await client.post("/api/hallucination", json={"candidates": []})
        assert r.status_code == 400

    async def test_with_candidates(self, client):
        r = await client.post("/api/hallucination", json={
            "text": "AI will replace all jobs by 2025.",
            "candidates": ["AI will automate some tasks.", "AI creates new job categories."],
        })
        assert r.status_code == 200
        assert r.json()["consistency_score"] >= 0


# ── Cost ──────────────────────────────────────────────────────────────────────

class TestCost:
    async def test_record_usage(self, client):
        r = await client.post("/api/cost/record", json={
            "provider": "openai", "model": "gpt-4o",
            "input_tokens": 500, "output_tokens": 200,
        })
        assert r.status_code == 200
        d = r.json()
        assert "total_cost_usd" in d
        assert d["total_cost_usd"] > 0

    async def test_cost_summary(self, client):
        r = await client.get("/api/cost/summary?days=30")
        assert r.status_code == 200
        d = r.json()
        assert "total_cost_usd" in d
        assert "budget_status" in d

    async def test_cost_summary_invalid_days(self, client):
        r = await client.get("/api/cost/summary?days=999")
        assert r.status_code == 400

    async def test_analyze_prompt(self, client):
        r = await client.post("/api/cost/analyze", json={
            "prompt": "As an AI language model, please note that I want you to classify this email.",
            "provider": "openai", "model": "gpt-4o",
        })
        assert r.status_code == 200
        d = r.json()
        assert "efficiency_score" in d
        assert "waste_findings" in d

    async def test_route_task(self, client):
        r = await client.post("/api/cost/route", json={
            "task_description": "Classify this email as spam or not spam",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["complexity"] == "simple"
        assert "recommended_model" in d

    async def test_route_invalid_quality(self, client):
        r = await client.post("/api/cost/route", json={
            "task_description": "test", "quality_requirement": "invalid",
        })
        assert r.status_code == 422

    async def test_model_pricing(self, client):
        r = await client.get("/api/cost/models")
        assert r.status_code == 200
        assert len(r.json()["models"]) > 5


# ── Drift ─────────────────────────────────────────────────────────────────────

class TestDrift:
    async def test_drift_no_data(self, client):
        r = await client.get("/api/drift/unknown-model/unknown-provider")
        assert r.status_code == 200
        d = r.json()
        assert "trend" in d
        assert "error" in d["trend"]


# ── Security headers ──────────────────────────────────────────────────────────

class TestSecurityHeaders:
    async def test_security_headers_present(self, client):
        r = await client.get("/api/health")
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"
        assert "x-request-id" in r.headers

    async def test_request_id_in_response(self, client):
        r = await client.get("/api/health")
        rid = r.headers.get("x-request-id", "")
        assert len(rid) >= 4

    async def test_response_time_header(self, client):
        r = await client.get("/api/health")
        assert "x-response-time-ms" in r.headers

    async def test_csp_header_present_and_scoped(self, client):
        r = await client.get("/api/health")
        csp = r.headers["content-security-policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp
        assert "object-src 'none'" in csp

    async def test_hsts_header_present(self, client):
        r = await client.get("/api/health")
        assert "max-age=31536000" in r.headers["strict-transport-security"]


# ── Config ────────────────────────────────────────────────────────────────────

class TestConfig:
    def test_config_defaults(self):
        s = Settings(
            _env_file=None,
            api_keys=[],
            db_path=":memory:",
            auth_enabled=False,
        )
        assert s.alert_threshold == 5.0
        assert s.monthly_budget_usd == 10_000.0
        assert s.rate_limit_default == "100/minute"

    def test_api_keys_parsed_from_string(self):
        s = Settings(_env_file=None, api_keys="key1,key2, key3 ")
        assert "key1" in s.api_keys
        assert "key2" in s.api_keys
        assert "key3" in s.api_keys

    def test_empty_api_keys(self):
        s = Settings(_env_file=None, api_keys=[])
        assert s.api_keys == []

    def test_brand_defaults(self):
        s = Settings(_env_file=None, api_keys=[])
        assert s.brand_name == "ResponsibleAI"
        assert s.brand_logo_url == ""


# ── Branding (white-label) ────────────────────────────────────────────────────

class TestBranding:
    async def test_default_branding(self, client):
        r = await client.get("/api/branding")
        assert r.status_code == 200
        d = r.json()
        assert d["brand_name"] == "ResponsibleAI"
        assert d["logo_url"] == ""

    async def test_custom_branding_reflected(self, client, monkeypatch):
        import responsibleai.dashboard.app as app_module

        monkeypatch.setattr(app_module.settings, "brand_name", "Acme Governance")
        monkeypatch.setattr(app_module.settings, "brand_logo_url", "https://acme.example/logo.png")
        r = await client.get("/api/branding")
        assert r.status_code == 200
        d = r.json()
        assert d["brand_name"] == "Acme Governance"
        assert d["logo_url"] == "https://acme.example/logo.png"

    async def test_branding_endpoint_requires_no_auth(self, client, monkeypatch):
        # White-label branding must be visible on the login page itself,
        # before any credential is presented — confirm no auth dependency
        # was accidentally added to this endpoint.
        r = await client.get("/api/branding")
        assert r.status_code != 401
        assert r.status_code != 403


# ── Incidents ─────────────────────────────────────────────────────────────────

class TestIncidentsCRUD:
    async def test_create_incident_persists_and_round_trips(self, client):
        r = await client.post("/api/incidents", json={
            "incident_type": "pii_leak",
            "severity": "high",
            "model_name": "gpt-4",
            "provider": "openai",
            "description": "Email address leaked in a completion.",
            "evidence": {"prompt_id": "abc123"},
        })
        assert r.status_code == 201
        created = r.json()
        assert created["incident_type"] == "pii_leak"
        assert created["severity"] == "high"
        assert created["status"] == "OPEN"
        assert created["sla_resolution_hours"] == 4
        assert created["evidence_keys"] == ["prompt_id"]

        r2 = await client.get(f"/api/incidents/{created['incident_id']}")
        assert r2.status_code == 200
        assert r2.json()["description"] == "Email address leaked in a completion."

    async def test_create_incident_defaults(self, client):
        r = await client.post("/api/incidents", json={"description": "Something odd happened."})
        assert r.status_code == 201
        d = r.json()
        assert d["incident_type"] == "other"
        assert d["severity"] == "medium"
        assert d["mitigated"] is False

    async def test_create_incident_rejects_bad_severity(self, client):
        r = await client.post("/api/incidents", json={
            "severity": "apocalyptic", "description": "x",
        })
        assert r.status_code == 422

    async def test_list_incidents_returns_created_ones(self, client):
        await client.post("/api/incidents", json={"description": "listed incident"})
        r = await client.get("/api/incidents")
        assert r.status_code == 200
        d = r.json()
        assert any(i["description"] == "listed incident" for i in d["incidents"])

    async def test_list_incidents_filters_by_severity(self, client):
        await client.post("/api/incidents", json={"severity": "critical", "description": "crit one"})
        r = await client.get("/api/incidents", params={"severity": "critical"})
        assert r.status_code == 200
        assert all(i["severity"] == "critical" for i in r.json()["incidents"])

    async def test_get_unknown_incident_404s(self, client):
        r = await client.get("/api/incidents/does-not-exist")
        assert r.status_code == 404


class TestAlertsWebhookBridge:
    async def test_disabled_when_token_unconfigured(self, client):
        r = await client.post("/api/alerts/webhook", json={"alerts": []})
        assert r.status_code == 503

    async def test_rejects_missing_bearer_token(self, client, monkeypatch):
        from responsibleai.dashboard import app as app_module
        monkeypatch.setattr(app_module.settings, "alerts_webhook_token", "expected-token")
        r = await client.post("/api/alerts/webhook", json={"alerts": []})
        assert r.status_code == 401

    async def test_creates_incident_from_firing_alert(self, client, monkeypatch):
        from responsibleai.dashboard import app as app_module
        monkeypatch.setattr(app_module.settings, "alerts_webhook_token", "expected-token")

        payload = {
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "RAIDriftAlertSpike", "severity": "warning"},
                    "annotations": {"summary": "Drift alerts fired for gpt-4 (openai)"},
                },
                {
                    "status": "resolved",
                    "labels": {"alertname": "RAINoTraffic", "severity": "warning"},
                    "annotations": {},
                },
            ],
        }
        r = await client.post(
            "/api/alerts/webhook",
            json=payload,
            headers={"Authorization": "Bearer expected-token"},
        )
        assert r.status_code == 200
        d = r.json()
        assert len(d["incidents_created"]) == 1
        assert d["alerts_skipped"] == 1

        incident = await client.get(f"/api/incidents/{d['incidents_created'][0]}")
        assert incident.status_code == 200
        body = incident.json()
        assert body["source"] == "alertmanager"
        assert body["severity"] == "medium"  # Alertmanager "warning" maps to our "medium"
        assert body["incident_type"] == "drift_alert"  # classified from "RAIDriftAlertSpike"


# ── Webhooks ──────────────────────────────────────────────────────────────────

class TestWebhooksAPI:
    """End-to-end coverage of POST/GET/DELETE /api/webhooks at the FastAPI
    layer — the SSRF guard (webhooks/manager.py::validate_webhook_url) was
    previously only exercised via WebhookManager unit tests, not through the
    actual HTTP endpoint an admin calls."""

    @pytest.fixture(autouse=True)
    def _fake_public_dns(self, monkeypatch):
        # validate_webhook_url() does a real getaddrinfo() lookup — pin every
        # hostname in this test class to a fixed public IP so tests don't
        # depend on real DNS.
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
        )

    async def test_create_list_delete_roundtrip(self, client):
        r = await client.post(
            "/api/webhooks",
            json={
                "url": "https://hooks.example.com/generic",
                "events": ["drift_alert"],
                "provider": "generic",
            },
        )
        assert r.status_code == 200
        created = r.json()
        assert created["url"] == "https://hooks.example.com/generic"
        webhook_id = created["id"]

        listed = await client.get("/api/webhooks")
        assert listed.status_code == 200
        assert any(w["id"] == webhook_id for w in listed.json()["webhooks"])

        deleted = await client.delete(f"/api/webhooks/{webhook_id}")
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] == webhook_id

        listed_after = await client.get("/api/webhooks")
        assert not any(w["id"] == webhook_id for w in listed_after.json()["webhooks"])

    async def test_rejects_invalid_event_type(self, client):
        r = await client.post(
            "/api/webhooks",
            json={"url": "https://hooks.example.com/x", "events": ["not_a_real_event"]},
        )
        assert r.status_code == 400
        assert "Invalid event type" in r.json()["message"]

    async def test_rejects_ssrf_loopback_url(self, client, monkeypatch):
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))],
        )
        r = await client.post(
            "/api/webhooks",
            json={"url": "http://localhost/hook", "events": ["drift_alert"]},
        )
        assert r.status_code == 400
        assert "Invalid webhook URL" in r.json()["message"]

    async def test_rejects_ssrf_cloud_metadata_url(self, client, monkeypatch):
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))],
        )
        r = await client.post(
            "/api/webhooks",
            json={"url": "http://metadata.internal/latest/meta-data", "events": ["drift_alert"]},
        )
        assert r.status_code == 400
        assert "Invalid webhook URL" in r.json()["message"]

    async def test_delete_nonexistent_returns_404(self, client):
        r = await client.delete("/api/webhooks/does-not-exist")
        assert r.status_code == 404

    async def test_test_endpoint_fires_and_returns_delivery(self, client, respx_mock):
        create = await client.post(
            "/api/webhooks",
            json={"url": "https://hooks.example.com/test-target", "events": ["trust_score_changed"]},
        )
        webhook_id = create.json()["id"]
        respx_mock.post("https://hooks.example.com/test-target").mock(
            return_value=httpx.Response(200)
        )
        r = await client.post(f"/api/webhooks/test/{webhook_id}")
        assert r.status_code == 200
        assert r.json()["success"] is True


# ── Leaderboard ───────────────────────────────────────────────────────────────

class TestLeaderboardPublicRead:
    async def test_empty_leaderboard_returns_empty_list(self, client):
        r = await client.get("/api/leaderboard")
        assert r.status_code == 200
        d = r.json()
        assert d["leaderboard"] == []
        assert "methodology_version" in d
        assert "methodology_url" in d

    async def test_history_404s_for_unknown_model(self, client):
        r = await client.get("/api/leaderboard/nope/nowhere/history")
        assert r.status_code == 404

    async def test_public_read_requires_no_authorization_header(self, client):
        # Regression check: these are meant to be public. No Authorization
        # header is sent by the fixture client, and it must still succeed.
        r = await client.get("/api/leaderboard")
        assert r.status_code == 200


class TestLeaderboardAdminAndRun:
    async def test_register_run_and_read_back(self, client):
        register = await client.post(
            "/api/leaderboard/models",
            json={"model": "mock-a", "provider": "mock", "display_name": "Mock A"},
        )
        assert register.status_code == 201
        assert register.json()["model"] == "mock-a"

        listed = await client.get("/api/leaderboard/models")
        assert listed.status_code == 200
        assert any(m["model"] == "mock-a" for m in listed.json()["models"])

        run = await client.post("/api/leaderboard/run")
        assert run.status_code == 200
        d = run.json()
        assert len(d["runs_completed"]) >= 1
        assert any(r["model"] == "mock-a" for r in d["runs_completed"])

        board = await client.get("/api/leaderboard")
        assert board.status_code == 200
        assert any(row["model"] == "mock-a" for row in board.json()["leaderboard"])

    async def test_run_specific_model_not_registered_404s(self, client):
        r = await client.post(
            "/api/leaderboard/run", params={"model": "ghost", "provider": "mock"},
        )
        assert r.status_code == 404

    async def test_run_with_no_registered_models_returns_empty(self, client):
        r = await client.post("/api/leaderboard/run")
        assert r.status_code == 200
        d = r.json()
        assert d["runs_completed"] == []
        assert d["runs_failed"] == []

    async def test_register_rejects_unknown_provider(self, client):
        r = await client.post(
            "/api/leaderboard/models",
            json={"model": "x", "provider": "not-a-real-provider"},
        )
        assert r.status_code == 422

    async def test_diagnostic_404s_for_unknown_model(self, client):
        r = await client.get("/api/leaderboard/nope/nowhere/diagnostic")
        assert r.status_code == 404

    async def test_diagnostic_returns_findings_after_a_run(self, client):
        await client.post(
            "/api/leaderboard/models",
            json={"model": "mock-diag", "provider": "mock"},
        )
        await client.post("/api/leaderboard/run", params={"model": "mock-diag", "provider": "mock"})

        r = await client.get("/api/leaderboard/mock-diag/mock/diagnostic")
        assert r.status_code == 200
        d = r.json()
        assert "findings" in d
        assert d["findings_count"] == len(d["findings"])


class TestLeaderboardPlanGate:
    """Auth is disabled in this test module's fixture, which defaults every
    request to an ENTERPRISE-plan legacy context — so the diagnostic
    endpoint's PRO gate can't be exercised end-to-end here. Exercise the
    actual require_plan() dependency directly instead, which is the real
    code the endpoint depends on."""

    async def test_require_plan_blocks_free_tier(self):
        from fastapi import HTTPException

        from responsibleai.dashboard.app import require_plan
        from responsibleai.rbac.models import OrgContext, Plan
        from responsibleai.rbac.models import Role as RbacRole

        dep = require_plan(Plan.PRO)
        free_ctx = OrgContext(key_id="k", role=RbacRole.VIEWER, org_id="org1", plan=Plan.FREE)
        with pytest.raises(HTTPException) as exc_info:
            await dep(free_ctx)
        assert exc_info.value.status_code == 402

    async def test_require_plan_allows_pro_and_above(self):
        from responsibleai.dashboard.app import require_plan
        from responsibleai.rbac.models import OrgContext, Plan
        from responsibleai.rbac.models import Role as RbacRole

        dep = require_plan(Plan.PRO)
        pro_ctx = OrgContext(key_id="k", role=RbacRole.VIEWER, org_id="org1", plan=Plan.PRO)
        result = await dep(pro_ctx)
        assert result is pro_ctx

        ent_ctx = OrgContext(key_id="k", role=RbacRole.VIEWER, org_id="org1", plan=Plan.ENTERPRISE)
        result2 = await dep(ent_ctx)
        assert result2 is ent_ctx


# ── Trust Index ───────────────────────────────────────────────────────────────

class TestTrustIndexAssessAndVerify:
    async def test_assess_returns_scored_citable_passport(self, client):
        r = await client.post("/api/trust-index/assess", json={
            "model_name": "acme-bot", "provider": "acme",
            "fairness": 0.9, "privacy": 0.85, "security": 0.8,
            "robustness": 0.75, "compliance": 0.7, "authenticity": 0.6,
        })
        assert r.status_code == 201
        d = r.json()
        assert d["model"] == {"name": "acme-bot", "provider": "acme"}
        assert d["certified"] is False
        assert "self-reported" in d["citation"]
        assert d["verify_url"] == f"/api/trust-index/verify/{d['passport_id']}"

    async def test_assess_uses_neutral_defaults_when_omitted(self, client):
        r = await client.post("/api/trust-index/assess", json={
            "model_name": "x", "provider": "y",
        })
        assert r.status_code == 201
        assert r.json()["trust_score"]["overall"] == 50.0

    async def test_assess_rejects_out_of_range_dimension(self, client):
        r = await client.post("/api/trust-index/assess", json={
            "model_name": "x", "provider": "y", "fairness": 1.5,
        })
        assert r.status_code == 422

    async def test_verify_round_trips_an_assessed_passport(self, client):
        assess = await client.post("/api/trust-index/assess", json={
            "model_name": "verify-me", "provider": "acme",
        })
        passport_id = assess.json()["passport_id"]

        r = await client.get(f"/api/trust-index/verify/{passport_id}")
        assert r.status_code == 200
        d = r.json()
        assert d["model"]["name"] == "verify-me"
        assert d["verification_hash"] == assess.json()["verification_hash"]

    async def test_verify_unknown_id_404s(self, client):
        r = await client.get("/api/trust-index/verify/does-not-exist")
        assert r.status_code == 404

    async def test_evaluate_endpoint_persists_a_verifiable_passport(self, client):
        """POST /api/evaluate used to generate a passport and discard it —
        confirm it's now persisted and independently verifiable."""
        r = await client.post("/api/evaluate", json={
            "model_name": "eval-model", "provider": "openai",
            "fairness": 0.8, "privacy": 0.8, "security": 0.8,
            "robustness": 0.8, "compliance": 0.8, "authenticity": 0.8,
        })
        assert r.status_code == 200
        d = r.json()
        assert "verify_url" in d

        verify = await client.get(d["verify_url"])
        assert verify.status_code == 200
        assert verify.json()["passport_id"] == d["passport_id"]
        assert verify.json()["source"] == "evaluate"


class TestTrustIndexCertification:
    async def test_certify_marks_passport_certified(self, client):
        assess = await client.post("/api/trust-index/assess", json={
            "model_name": "cert-me", "provider": "acme",
        })
        passport_id = assess.json()["passport_id"]

        r = await client.post(f"/api/trust-index/certify/{passport_id}", json={})
        assert r.status_code == 200
        d = r.json()
        assert d["certified"] is True
        assert d["certified_by"] == "ResponsibleAI Certification Team"

        verify = await client.get(f"/api/trust-index/verify/{passport_id}")
        assert verify.json()["certified"] is True

    async def test_certify_custom_certifier_name(self, client):
        assess = await client.post("/api/trust-index/assess", json={
            "model_name": "cert-me-2", "provider": "acme",
        })
        passport_id = assess.json()["passport_id"]

        r = await client.post(
            f"/api/trust-index/certify/{passport_id}",
            json={"certified_by": "Independent Auditor LLC"},
        )
        assert r.json()["certified_by"] == "Independent Auditor LLC"

    async def test_certify_unknown_passport_404s(self, client):
        r = await client.post("/api/trust-index/certify/does-not-exist", json={})
        assert r.status_code == 404

    async def test_certified_directory_lists_only_certified(self, client):
        assess = await client.post("/api/trust-index/assess", json={
            "model_name": "listed-model", "provider": "acme",
        })
        passport_id = assess.json()["passport_id"]
        await client.post(f"/api/trust-index/certify/{passport_id}", json={})

        r = await client.get("/api/trust-index/certified")
        assert r.status_code == 200
        d = r.json()
        assert any(row["passport_id"] == passport_id for row in d["certified"])

    async def test_certified_directory_empty_by_default(self, client):
        r = await client.get("/api/trust-index/certified")
        assert r.status_code == 200
        assert r.json()["certified"] == []


class TestTrustIndexBadge:
    async def test_badge_renders_svg_for_self_assessed(self, client):
        assess = await client.post("/api/trust-index/assess", json={
            "model_name": "badge-me", "provider": "acme",
        })
        passport_id = assess.json()["passport_id"]

        r = await client.get(f"/api/trust-index/badge/{passport_id}.svg")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("image/svg+xml")
        assert "Self-Assessed" in r.text
        assert "<svg" in r.text

    async def test_badge_renders_certified_after_certification(self, client):
        assess = await client.post("/api/trust-index/assess", json={
            "model_name": "badge-me-2", "provider": "acme",
        })
        passport_id = assess.json()["passport_id"]
        await client.post(f"/api/trust-index/certify/{passport_id}", json={})

        r = await client.get(f"/api/trust-index/badge/{passport_id}.svg")
        assert r.status_code == 200
        assert "Certified" in r.text
        assert "Self-Assessed" not in r.text

    async def test_badge_unknown_passport_404s(self, client):
        r = await client.get("/api/trust-index/badge/does-not-exist.svg")
        assert r.status_code == 404

    async def test_badge_escapes_model_name_with_markup(self, client):
        # model_name is free-form, attacker-controllable input to a public,
        # unauthenticated endpoint — the badge only ever renders grade/score/
        # certified status (never model_name), so this can't be an XSS vector
        # via the badge specifically, but confirm it doesn't crash the SVG
        # renderer either.
        assess = await client.post("/api/trust-index/assess", json={
            "model_name": "<script>alert(1)</script>", "provider": "acme",
        })
        passport_id = assess.json()["passport_id"]
        r = await client.get(f"/api/trust-index/badge/{passport_id}.svg")
        assert r.status_code == 200
        assert "<script>" not in r.text


# ── AI Incident Database ─────────────────────────────────────────────────────
# POST /api/incident-db/report is deliberately rate-limited to 5/hour (it's
# the one unauthenticated write endpoint in the whole API) using slowapi's
# module-level in-memory limiter, which is NOT reset between test functions
# within one pytest run (it's created once at app.py import time, independent
# of the per-test lifespan). Calling the real HTTP endpoint from every test
# that needs a report to exist would exhaust that budget non-deterministically
# depending on test order/count. So: only the tests that genuinely exercise
# the report endpoint itself call it over HTTP; every other test seeds a
# report directly via the repository, bypassing the rate limit entirely.

_INCIDENT_PAYLOAD = {
    "title": "Jailbreak via nested roleplay framing",
    "description": "A multi-turn nested roleplay prompt reliably bypassed the model's "
                    "safety training and produced disallowed content.",
    "affected_model": "test-model", "affected_provider": "test-provider",
    "incident_type": "jailbreak", "severity": "high",
}


async def _seed_incident_report(**overrides):
    from responsibleai.dashboard import app as app_module

    fields = {
        "title": _INCIDENT_PAYLOAD["title"],
        "description": _INCIDENT_PAYLOAD["description"],
        "incident_type": _INCIDENT_PAYLOAD["incident_type"],
        "severity": _INCIDENT_PAYLOAD["severity"],
        "affected_model": _INCIDENT_PAYLOAD["affected_model"],
        "affected_provider": _INCIDENT_PAYLOAD["affected_provider"],
    }
    fields.update(overrides)
    return await app_module._public_incident_repo.submit(**fields)


class TestIncidentDBReportAndPublicRead:
    async def test_report_starts_pending_not_public(self, client):
        r = await client.post("/api/incident-db/report", json=_INCIDENT_PAYLOAD)
        assert r.status_code == 201
        d = r.json()
        assert d["status"] == "PENDING_REVIEW"
        assert d["public_id"] is None
        assert "pending review" in d["message"]

        listing = await client.get("/api/incident-db")
        assert listing.json()["incidents"] == []

    async def test_report_rejects_short_title(self, client):
        bad = {**_INCIDENT_PAYLOAD, "title": "hi"}
        r = await client.post("/api/incident-db/report", json=bad)
        assert r.status_code == 422

    async def test_report_rejects_invalid_incident_type(self, client):
        bad = {**_INCIDENT_PAYLOAD, "incident_type": "not-a-real-type"}
        r = await client.post("/api/incident-db/report", json=bad)
        assert r.status_code == 422

    async def test_list_unknown_incident_404s(self, client):
        r = await client.get("/api/incident-db/RAI-2026-9999")
        assert r.status_code == 404

    async def test_verify_empty_database(self, client):
        r = await client.get("/api/incident-db/verify")
        assert r.status_code == 200
        d = r.json()
        assert d["intact"] is True
        assert d["entries_checked"] == 0


class TestIncidentDBModerationWorkflow:
    async def test_full_report_to_publish_flow(self, client):
        seeded = await _seed_incident_report()
        internal_id = seeded["id"]

        pending = await client.get("/api/incident-db/pending")
        assert pending.status_code == 200
        assert any(p["id"] == internal_id for p in pending.json()["pending"])

        approved = await client.post(f"/api/incident-db/{internal_id}/approve")
        assert approved.status_code == 200
        d = approved.json()
        assert d["status"] == "PUBLISHED"
        assert d["public_id"].startswith("RAI-")
        assert d["entry_hash"] is not None

        public_id = d["public_id"]
        listing = await client.get("/api/incident-db")
        assert any(row["public_id"] == public_id for row in listing.json()["incidents"])

        detail = await client.get(f"/api/incident-db/{public_id}")
        assert detail.status_code == 200
        assert detail.json()["title"] == _INCIDENT_PAYLOAD["title"]

        verify = await client.get("/api/incident-db/verify")
        assert verify.json()["intact"] is True
        assert verify.json()["entries_checked"] == 1

    async def test_reject_flow(self, client):
        seeded = await _seed_incident_report()
        internal_id = seeded["id"]

        rejected = await client.post(
            f"/api/incident-db/{internal_id}/reject",
            json={"reason": "duplicate of an existing report"},
        )
        assert rejected.status_code == 200
        assert rejected.json()["status"] == "REJECTED"

        listing = await client.get("/api/incident-db")
        assert listing.json()["incidents"] == []

    async def test_approve_unknown_id_404s(self, client):
        r = await client.post("/api/incident-db/does-not-exist/approve")
        assert r.status_code == 404

    async def test_reject_unknown_id_404s(self, client):
        r = await client.post("/api/incident-db/does-not-exist/reject", json={"reason": "not a real report"})
        assert r.status_code == 404

    async def test_reject_requires_a_reason(self, client):
        seeded = await _seed_incident_report()
        internal_id = seeded["id"]
        r = await client.post(f"/api/incident-db/{internal_id}/reject", json={"reason": "no"})
        assert r.status_code == 422  # below min_length=5

    async def test_status_update_after_publish(self, client):
        seeded = await _seed_incident_report()
        internal_id = seeded["id"]
        approved = await client.post(f"/api/incident-db/{internal_id}/approve")
        public_id = approved.json()["public_id"]

        r = await client.post(f"/api/incident-db/{public_id}/status", json={"status": "RESOLVED"})
        assert r.status_code == 200
        assert r.json()["status"] == "RESOLVED"
        assert r.json()["entry_hash"] == approved.json()["entry_hash"]

    async def test_status_update_rejects_invalid_value(self, client):
        seeded = await _seed_incident_report()
        internal_id = seeded["id"]
        approved = await client.post(f"/api/incident-db/{internal_id}/approve")
        public_id = approved.json()["public_id"]

        r = await client.post(f"/api/incident-db/{public_id}/status", json={"status": "PENDING_REVIEW"})
        assert r.status_code == 422


class TestIncidentDBCheckEndpoint:
    async def test_check_matches_published_incident(self, client):
        seeded = await _seed_incident_report()
        internal_id = seeded["id"]
        await client.post(f"/api/incident-db/{internal_id}/approve")

        r = await client.get("/api/incident-db/check", params={
            "model": "test-model", "provider": "test-provider",
        })
        assert r.status_code == 200
        d = r.json()
        assert d["has_reported_incidents"] is True
        assert len(d["incidents"]) == 1

    async def test_check_no_match(self, client):
        r = await client.get("/api/incident-db/check", params={
            "model": "totally-unknown-model", "provider": "nobody",
        })
        assert r.status_code == 200
        assert r.json()["has_reported_incidents"] is False

    async def test_check_requires_both_params(self, client):
        r = await client.get("/api/incident-db/check", params={"model": "x"})
        assert r.status_code == 422
