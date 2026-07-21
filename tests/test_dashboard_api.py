"""Integration tests for the Governance Dashboard API."""

from __future__ import annotations

import os

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
