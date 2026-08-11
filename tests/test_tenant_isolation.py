"""Cross-organization data isolation tests against a real, auth-enabled app
instance — see test_mfa_login_flow.py's module docstring for why auth is
forced on by monkeypatching the settings singleton rather than via
os.environ.

`test_governance_api.py` already covers this for the governance evidence
and approval endpoints. This file closes the same gap for the older,
pre-governance-core endpoints (`/api/models`, `/api/cost/summary`,
`/api/audit`) that never had an explicit regression test proving org A's
API key cannot see org B's data — multi-tenancy is a claimed security
property (see ENTERPRISE_SECURITY.md's "Multi-tenancy isolation" section)
and had no direct test enforcing it before this file.
"""

from __future__ import annotations

import asyncio

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, limiter, settings


async def _drain_audit_writes() -> None:
    """The audit-log middleware writes fire-and-forget (see its class
    docstring in app.py) so the row isn't guaranteed persisted the instant
    the HTTP response returns — await the tracked pending tasks before
    querying /api/audit in a test, or the query can race the write."""
    pending = list(app_module._pending_audit_writes)
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


@pytest.fixture(autouse=True)
def _auth_enabled_with_bootstrap_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limiter.reset()
    yield


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as c:
            yield c


async def _new_org_with_analyst_key(client: AsyncClient, slug: str) -> tuple[str, str]:
    r = await client.post("/api/orgs", json={"name": slug, "slug": slug}, headers=BOOTSTRAP_AUTH)
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    r = await client.post(
        f"/api/orgs/{org_id}/keys", json={"name": "analyst-key", "role": "ANALYST"}, headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


class TestModelsIsolation:
    async def test_evaluated_model_not_visible_to_other_org(self, client: AsyncClient) -> None:
        _org_a, key_a = await _new_org_with_analyst_key(client, "tenant-a-models")
        _org_b, key_b = await _new_org_with_analyst_key(client, "tenant-b-models")

        r = await client.post(
            "/api/evaluate",
            json={"model_name": "tenant-a-secret-model", "provider": "openai"},
            headers={"Authorization": f"Bearer {key_a}"},
        )
        assert r.status_code == 200, r.text

        r = await client.get("/api/models", headers={"Authorization": f"Bearer {key_a}"})
        assert r.status_code == 200
        assert any(m["model_name"] == "tenant-a-secret-model" for m in r.json()["models"])

        r = await client.get("/api/models", headers={"Authorization": f"Bearer {key_b}"})
        assert r.status_code == 200
        assert not any(m["model_name"] == "tenant-a-secret-model" for m in r.json()["models"])


class TestCostSummaryIsolation:
    async def test_recorded_usage_not_visible_to_other_org(self, client: AsyncClient) -> None:
        _org_a, key_a = await _new_org_with_analyst_key(client, "tenant-a-cost")
        _org_b, key_b = await _new_org_with_analyst_key(client, "tenant-b-cost")

        r = await client.post(
            "/api/cost/record",
            json={"provider": "openai", "model": "gpt-4o", "input_tokens": 5000, "output_tokens": 2000},
            headers={"Authorization": f"Bearer {key_a}"},
        )
        assert r.status_code == 200, r.text

        r = await client.get("/api/cost/summary", headers={"Authorization": f"Bearer {key_a}"})
        assert r.status_code == 200
        assert r.json()["total_tokens"]["total"] == 7000

        r = await client.get("/api/cost/summary", headers={"Authorization": f"Bearer {key_b}"})
        assert r.status_code == 200
        assert r.json()["total_tokens"]["total"] == 0
        assert r.json()["total_cost_usd"] == 0


class TestAuditLogIsolation:
    async def test_audit_entries_scoped_to_caller_org(self, client: AsyncClient) -> None:
        org_a, key_a = await _new_org_with_analyst_key(client, "tenant-a-audit")
        org_b, key_b = await _new_org_with_analyst_key(client, "tenant-b-audit")

        # Generate an audited request in each org.
        await client.post(
            "/api/scan", json={"text": "hello from org a"}, headers={"Authorization": f"Bearer {key_a}"},
        )
        await client.post(
            "/api/scan", json={"text": "hello from org b"}, headers={"Authorization": f"Bearer {key_b}"},
        )
        await _drain_audit_writes()

        r = await client.get("/api/audit", headers={"Authorization": f"Bearer {key_a}"})
        assert r.status_code == 200
        entries_a = r.json()["entries"]
        assert len(entries_a) >= 1
        assert all(e["org_id"] == org_a for e in entries_a)
        assert not any(e["org_id"] == org_b for e in entries_a)

    async def test_org_scoped_key_cannot_override_org_id_query_param(self, client: AsyncClient) -> None:
        """An org-scoped (non-legacy) key must not be able to read another
        org's audit log by passing ?org_id=<other-org> — the endpoint's own
        comment says org-specific keys are force-scoped regardless of the
        query param; this proves that's actually enforced, not just
        documented."""
        org_a, key_a = await _new_org_with_analyst_key(client, "tenant-a-audit-override")
        org_b, key_b = await _new_org_with_analyst_key(client, "tenant-b-audit-override")

        await client.post(
            "/api/scan", json={"text": "org b only"}, headers={"Authorization": f"Bearer {key_b}"},
        )
        await _drain_audit_writes()

        r = await client.get(
            f"/api/audit?org_id={org_b}", headers={"Authorization": f"Bearer {key_a}"},
        )
        assert r.status_code == 200
        entries = r.json()["entries"]
        assert not any(e["org_id"] == org_b for e in entries)
