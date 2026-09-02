"""Enterprise Readiness Phase 6 — REST API auth-failure rate limiting.
`00_MASTER_READINESS_AUDIT.md`'s Authentication row named the gap:
`_AuthFailureLimiter` (mcp/server.py) protected the hosted MCP
transport, but the REST dashboard API had no equivalent, and its
existing slowapi-based rate limiting keys by the *presented* Bearer
token when one is present -- meaning a credential-guessing attacker
trying many different candidate tokens gets a fresh, unthrottled
bucket for every guess. `dashboard/middleware.py`'s `AuthFailureLimiter`
closes this: a genuinely IP-keyed failed-attempt counter, independent
of what token was tried.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import _auth_failure_limiter, app, limiter, settings

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


@pytest.fixture(autouse=True)
def _reset_auth_failure_limiter():
    """The limiter is a module-level singleton (like `limiter` itself)
    -- clear its in-memory state so tests don't interfere with each
    other via IP-keyed failure counts left over from a previous test."""
    _auth_failure_limiter._failures.clear()
    yield
    _auth_failure_limiter._failures.clear()


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


class TestAuthFailureLimiter:
    async def test_valid_key_is_never_blocked(self, client: AsyncClient) -> None:
        for _ in range(30):
            r = await client.get("/api/orgs", headers=BOOTSTRAP_AUTH)
            assert r.status_code == 200

    async def test_repeated_invalid_keys_eventually_get_429(self, client: AsyncClient) -> None:
        last_status = None
        for i in range(25):
            r = await client.get("/api/orgs", headers={"Authorization": f"Bearer guess-{i}"})
            last_status = r.status_code
        # 20 distinct wrong guesses is the configured threshold -- by
        # attempt 25 the IP must be blocked, regardless of each guess
        # being a *different* token (the whole point: bucketing must
        # NOT be per-token here).
        assert last_status == 429

    async def test_missing_authorization_header_also_counts_as_a_failure(
        self, client: AsyncClient
    ) -> None:
        for _ in range(25):
            r = await client.get("/api/orgs")
        assert r.status_code == 429

    async def test_blocked_ip_cannot_use_even_a_valid_key(self, client: AsyncClient) -> None:
        for i in range(20):
            await client.get("/api/orgs", headers={"Authorization": f"Bearer guess-{i}"})
        r = await client.get("/api/orgs", headers=BOOTSTRAP_AUTH)
        assert r.status_code == 429

    async def test_dev_mode_auth_disabled_bypasses_the_limiter_entirely(
        self, client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "auth_enabled", False)
        for _ in range(25):
            r = await client.get("/api/orgs")
        assert r.status_code == 200
