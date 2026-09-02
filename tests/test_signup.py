"""Tests for the self-serve signup wizard (`POST /api/signup`) and its
anti-abuse guard (`dashboard/signup_guard.py`).

`POST /api/signup` is rate-limited to 5/hour per source IP via slowapi's
module-level in-memory limiter, which (per the same precedent
`tests/test_dashboard_api.py` documents above its incident-db tests) is
NOT reset between test functions within one pytest run. This file makes
exactly 4 real HTTP calls to the endpoint across its whole run, staying
under that budget with margin — every other check (rate window, dwell
time, disposable-email detection) is a pure unit test against
signup_guard.py directly, spending no HTTP budget at all.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, settings
from responsibleai.dashboard.signup_guard import (
    DISPOSABLE_EMAIL_DOMAINS,
    SignupRateWindow,
    dwell_time_ok,
    is_disposable_email_domain,
)
from responsibleai.rbac.models import Role


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
    monkeypatch.setattr(settings, "allow_all_origins", True)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac


def _signup_payload(**overrides):
    payload = {
        "name": "Acme Corp",
        "slug": "acme-signup-test",
        "email": "founder@acme-example.com",
        "website": "",
        "page_loaded_at_ms": 0,
    }
    payload.update(overrides)
    return payload


class TestDwellTimeCheck:
    def test_instant_submit_fails(self):
        loaded_at = 1_000_000
        assert dwell_time_ok(loaded_at, now_ms=loaded_at + 100) is False

    def test_after_minimum_passes(self):
        loaded_at = 1_000_000
        assert dwell_time_ok(loaded_at, now_ms=loaded_at + 2000) is True

    def test_exactly_at_boundary_passes(self):
        loaded_at = 1_000_000
        assert dwell_time_ok(loaded_at, now_ms=loaded_at + 2000, minimum_ms=2000) is True

    def test_custom_minimum_respected(self):
        loaded_at = 1_000_000
        assert dwell_time_ok(loaded_at, now_ms=loaded_at + 500, minimum_ms=1000) is False
        assert dwell_time_ok(loaded_at, now_ms=loaded_at + 1500, minimum_ms=1000) is True


class TestDisposableEmailDetection:
    def test_known_disposable_domain_detected(self):
        assert is_disposable_email_domain("bot@mailinator.com") is True

    def test_case_insensitive(self):
        assert is_disposable_email_domain("bot@MAILINATOR.COM") is True

    def test_real_domain_not_flagged(self):
        assert is_disposable_email_domain("founder@acme-example.com") is False

    def test_malformed_email_not_flagged(self):
        # EmailStr validation rejects this before it ever reaches here —
        # this just confirms the function itself doesn't crash on bad input.
        assert is_disposable_email_domain("not-an-email") is False

    def test_blocklist_is_non_empty(self):
        assert len(DISPOSABLE_EMAIL_DOMAINS) > 10


class TestSignupRateWindow:
    def test_allows_up_to_max(self):
        window = SignupRateWindow(max_per_window=3, window_seconds=60.0)
        assert window.allow() is True
        assert window.allow() is True
        assert window.allow() is True

    def test_denies_over_max(self):
        window = SignupRateWindow(max_per_window=2, window_seconds=60.0)
        assert window.allow() is True
        assert window.allow() is True
        assert window.allow() is False

    def test_events_expire_out_of_window(self):
        window = SignupRateWindow(max_per_window=1, window_seconds=0.05)
        assert window.allow() is True
        assert window.allow() is False
        import time

        time.sleep(0.06)
        assert window.allow() is True


class TestSignupEndpoint:
    """Exactly 4 real HTTP calls total across this class — see module
    docstring for why that budget matters."""

    async def test_successful_signup_issues_a_working_owner_key_and_slug_collides(self, client):
        r = await client.post("/api/signup", json=_signup_payload(page_loaded_at_ms=0))
        assert r.status_code == 201
        body = r.json()
        assert body["org"]["slug"] == "acme-signup-test"
        assert body["org"]["name"] == "Acme Corp"
        assert body["api_key"]
        assert body["key_id"]

        # Confirm the issued key is real and OWNER-scoped -- verified
        # directly against the repository (not a second HTTP round trip,
        # to stay within the endpoint's own rate-limit budget).
        from responsibleai.dashboard import app as app_module

        ctx = await app_module._org_repo.authenticate(body["api_key"])
        assert ctx is not None
        assert ctx.role == Role.OWNER
        assert ctx.org_id == body["org"]["id"]

        # A second signup against the same slug, in the same lifespan
        # (each `client` fixture spins its own fresh :memory: DB, so
        # the collision check only means something within one test).
        r2 = await client.post(
            "/api/signup", json=_signup_payload(page_loaded_at_ms=0, name="Different Name")
        )
        assert r2.status_code == 409

    async def test_honeypot_field_rejects_without_creating_org(self, client):
        r = await client.post(
            "/api/signup",
            json=_signup_payload(
                slug="acme-honeypot-test", website="http://spam.example", page_loaded_at_ms=0
            ),
        )
        assert r.status_code == 400

        from responsibleai.dashboard import app as app_module

        assert await app_module._org_repo.get_org_by_slug("acme-honeypot-test") is None

    async def test_disposable_email_rejects_without_creating_org(self, client):
        r = await client.post(
            "/api/signup",
            json=_signup_payload(
                slug="acme-disposable-test", email="bot@mailinator.com", page_loaded_at_ms=0
            ),
        )
        assert r.status_code == 400

        from responsibleai.dashboard import app as app_module

        assert await app_module._org_repo.get_org_by_slug("acme-disposable-test") is None
