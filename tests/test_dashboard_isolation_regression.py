# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests verifying test-boundary isolation for dashboard state.

Prevents order-dependent test contamination where state from an earlier test
remains observable in a subsequent test across separate application lifespans.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, settings


@pytest.fixture()
async def dashboard_client():
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


# ── Cluster 1: Leaderboard Repository Isolation ─────────────────────────────


class TestLeaderboardOrderIsolation:
    """Proves leaderboard registrations and runs in one test do not leak to subsequent tests."""

    async def test_01_contaminating_register_and_run(self, dashboard_client: AsyncClient):
        register = await dashboard_client.post(
            "/api/leaderboard/models",
            json={
                "model": "isolation-model",
                "provider": "mock",
                "display_name": "Isolation Model",
            },
        )
        assert register.status_code == 201

        run = await dashboard_client.post("/api/leaderboard/run")
        assert run.status_code == 200
        assert len(run.json()["runs_completed"]) >= 1

    async def test_02_victim_run_with_no_models_is_empty(self, dashboard_client: AsyncClient):
        run = await dashboard_client.post("/api/leaderboard/run")
        assert run.status_code == 200
        data = run.json()
        assert data["runs_completed"] == []
        assert data["runs_failed"] == []


# ── Cluster 2: Trust Index & Certification Isolation ─────────────────────────


class TestTrustIndexOrderIsolation:
    """Proves trust index passports and certifications do not leak to subsequent tests."""

    async def test_01_contaminating_assess_and_certify(self, dashboard_client: AsyncClient):
        assess = await dashboard_client.post(
            "/api/trust-index/assess",
            json={"model_name": "isolation-cert-model", "provider": "acme"},
        )
        assert assess.status_code == 201
        passport_id = assess.json()["passport_id"]

        certify = await dashboard_client.post(f"/api/trust-index/certify/{passport_id}", json={})
        assert certify.status_code == 200

    async def test_02_victim_registry_empty_by_default(self, dashboard_client: AsyncClient):
        r = await dashboard_client.get("/api/trust-index/registry")
        assert r.status_code == 200
        assert r.json()["registry"] == []

    async def test_03_victim_certified_empty_by_default(self, dashboard_client: AsyncClient):
        r = await dashboard_client.get("/api/trust-index/certified")
        assert r.status_code == 200
        assert r.json()["certified"] == []


# ── Cluster 3: Incident DB Moderation & Check Isolation ─────────────────────


class TestIncidentDBOrderIsolation:
    """Proves incident reports and published incidents do not leak to subsequent tests."""

    async def test_01_contaminating_publish_incident(self, dashboard_client: AsyncClient):
        report = await dashboard_client.post(
            "/api/incident-db/report",
            json={
                "title": "Isolation test incident",
                "description": "A safety failure occurring in an isolated test environment.",
                "affected_model": "isolation-victim-model",
                "affected_provider": "isolation-provider",
                "incident_type": "jailbreak",
                "severity": "high",
            },
        )
        assert report.status_code == 201
        pending = await dashboard_client.get("/api/incident-db/pending")
        assert pending.status_code == 200
        internal_id = pending.json()["pending"][0]["id"]

        approve = await dashboard_client.post(f"/api/incident-db/{internal_id}/approve")
        assert approve.status_code == 200

    async def test_02_victim_reject_flow_empty_listing(self, dashboard_client: AsyncClient):
        report = await dashboard_client.post(
            "/api/incident-db/report",
            json={
                "title": "Another incident to reject",
                "description": "Should be rejected and not leave any published incidents.",
                "affected_model": "isolation-victim-model",
                "affected_provider": "isolation-provider",
                "incident_type": "jailbreak",
                "severity": "high",
            },
        )
        assert report.status_code == 201
        pending = await dashboard_client.get("/api/incident-db/pending")
        internal_id = pending.json()["pending"][0]["id"]

        reject = await dashboard_client.post(
            f"/api/incident-db/{internal_id}/reject",
            json={"reason": "duplicate or invalid report"},
        )
        assert reject.status_code == 200

        listing = await dashboard_client.get("/api/incident-db")
        assert listing.status_code == 200
        assert listing.json()["incidents"] == []

    async def test_03_victim_check_no_published_incident_matches(
        self, dashboard_client: AsyncClient
    ):
        check = await dashboard_client.get(
            "/api/incident-db/check",
            params={
                "model": "isolation-victim-model",
                "provider": "isolation-provider",
            },
        )
        assert check.status_code == 200
        data = check.json()
        assert data["has_reported_incidents"] is False
        assert len(data["incidents"]) == 0
