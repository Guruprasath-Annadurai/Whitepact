"""API endpoint tests for red team, audit log, and billing endpoints (v1.1.0)."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai import __version__
from responsibleai.dashboard.app import app, settings


@pytest.fixture(autouse=True)
def _default_test_settings(monkeypatch: pytest.MonkeyPatch):
    """See test_dashboard_api.py's `_default_test_settings` docstring
    for the full story: `os.environ.setdefault(...)` at module level
    only reliably takes effect if this file's import is the first
    thing in the whole pytest session to trigger the lazy `settings`
    singleton's construction -- collection-order-dependent and, as
    observed directly, silently broken by an unrelated file (any file
    alphabetically earlier that imports `responsibleai.dashboard.app`)
    winning that race instead. Monkeypatching the shared singleton
    explicitly is deterministic regardless of import order."""
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "log_json", False)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


# ── Red team endpoints ─────────────────────────────────────────────────────────


class TestRedteamPayloadsEndpoint:
    @pytest.mark.asyncio
    async def test_returns_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/redteam/payloads")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_payloads_list(self, client: AsyncClient) -> None:
        r = await client.get("/api/redteam/payloads")
        d = r.json()
        assert "payloads" in d
        assert d["count"] > 0
        assert len(d["payloads"]) == d["count"]

    @pytest.mark.asyncio
    async def test_each_payload_has_required_fields(self, client: AsyncClient) -> None:
        r = await client.get("/api/redteam/payloads")
        for p in r.json()["payloads"]:
            assert "name" in p
            assert "category" in p
            assert "payload" in p
            assert "severity" in p

    @pytest.mark.asyncio
    async def test_filter_by_jailbreak_category(self, client: AsyncClient) -> None:
        r = await client.get("/api/redteam/payloads?categories=jailbreak")
        for p in r.json()["payloads"]:
            assert p["category"] == "jailbreak"

    @pytest.mark.asyncio
    async def test_five_attack_categories_present(self, client: AsyncClient) -> None:
        r = await client.get("/api/redteam/payloads")
        categories = set(r.json()["categories"])
        assert len(categories) == 5

    @pytest.mark.asyncio
    async def test_has_prompt_injection(self, client: AsyncClient) -> None:
        r = await client.get("/api/redteam/payloads")
        categories = set(r.json()["categories"])
        assert "prompt_injection" in categories


class TestRedteamAnalyzeEndpoint:
    @pytest.mark.asyncio
    async def test_analyze_returns_200(self, client: AsyncClient) -> None:
        # Get payloads first
        pr = await client.get("/api/redteam/payloads")
        payloads = pr.json()["payloads"]
        responses = {p["name"]: "I cannot help with that." for p in payloads}
        r = await client.post(
            "/api/redteam/analyze",
            json={
                "model_name": "test-model",
                "provider": "test",
                "responses": responses,
            },
        )
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_analyze_returns_security_score(self, client: AsyncClient) -> None:
        pr = await client.get("/api/redteam/payloads")
        payloads = pr.json()["payloads"]
        responses = {p["name"]: "I refuse that." for p in payloads}
        r = await client.post(
            "/api/redteam/analyze",
            json={
                "model_name": "secure-model",
                "provider": "test",
                "responses": responses,
            },
        )
        d = r.json()
        assert "security_score" in d
        assert 0 <= d["security_score"] <= 100

    @pytest.mark.asyncio
    async def test_analyze_empty_responses(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/redteam/analyze",
            json={
                "model_name": "m",
                "provider": "p",
                "responses": {},
            },
        )
        assert r.status_code == 200
        assert r.json()["total_attacks"] == 0

    @pytest.mark.asyncio
    async def test_analyze_missing_body_returns_422(self, client: AsyncClient) -> None:
        r = await client.post("/api/redteam/analyze", json={})
        assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_report_includes_model_info(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/redteam/analyze",
            json={
                "model_name": "gpt-4o",
                "provider": "openai",
                "responses": {},
            },
        )
        d = r.json()
        assert d["model"] == "gpt-4o"
        assert d["provider"] == "openai"


# ── Audit log endpoints ────────────────────────────────────────────────────────


class TestAuditEndpoints:
    @pytest.mark.asyncio
    async def test_audit_returns_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_response_shape(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit")
        d = r.json()
        assert "entries" in d
        assert "total" in d
        assert "limit" in d
        assert "offset" in d
        assert "days" in d

    @pytest.mark.asyncio
    async def test_audit_default_days(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit")
        assert r.json()["days"] == 30

    @pytest.mark.asyncio
    async def test_audit_custom_days(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit?days=7")
        assert r.json()["days"] == 7

    @pytest.mark.asyncio
    async def test_audit_custom_limit(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit?limit=10")
        assert r.json()["limit"] == 10

    @pytest.mark.asyncio
    async def test_audit_export_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit/export")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_export_csv_content_type(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit/export")
        assert "text/csv" in r.headers["content-type"]

    @pytest.mark.asyncio
    async def test_audit_export_has_csv_headers(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit/export")
        first_line = r.text.splitlines()[0]
        assert "timestamp" in first_line
        assert "endpoint" in first_line

    @pytest.mark.asyncio
    async def test_audit_summary_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit/summary")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_summary_has_endpoints(self, client: AsyncClient) -> None:
        r = await client.get("/api/audit/summary")
        d = r.json()
        assert "endpoints" in d
        assert "days" in d


# ── Billing endpoints ──────────────────────────────────────────────────────────


class TestBillingUsageEndpoint:
    @pytest.mark.asyncio
    async def test_billing_returns_200(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage")
        assert r.status_code == 200

    @pytest.mark.asyncio
    async def test_billing_response_fields(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage")
        d = r.json()
        assert "total_cost_usd" in d
        assert "total_requests" in d
        assert "total_tokens" in d
        assert "cost_by_model" in d
        assert "period_days" in d

    @pytest.mark.asyncio
    async def test_billing_default_30_days(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage")
        assert r.json()["period_days"] == 30

    @pytest.mark.asyncio
    async def test_billing_custom_period(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage?days=7")
        assert r.json()["period_days"] == 7

    @pytest.mark.asyncio
    async def test_billing_cost_is_non_negative(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage")
        assert r.json()["total_cost_usd"] >= 0

    @pytest.mark.asyncio
    async def test_billing_total_tokens_shape(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage")
        tokens = r.json()["total_tokens"]
        assert "input" in tokens
        assert "output" in tokens
        assert "total" in tokens

    @pytest.mark.asyncio
    async def test_billing_timestamp_present(self, client: AsyncClient) -> None:
        r = await client.get("/api/billing/usage")
        assert "timestamp" in r.json()


# ── Version check ──────────────────────────────────────────────────────────────


class TestVersionBump:
    @pytest.mark.asyncio
    async def test_version_matches_package(self, client: AsyncClient) -> None:
        r = await client.get("/api/version")
        assert r.json()["version"] == __version__

    @pytest.mark.asyncio
    async def test_platform_status_version(self, client: AsyncClient) -> None:
        r = await client.get("/api/support/status")
        assert r.json()["version"] == __version__
