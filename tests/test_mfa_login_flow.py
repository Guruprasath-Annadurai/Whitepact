"""End-to-end HTTP test of the TOTP MFA login flow (enroll -> verify ->
login-with-code -> backup-code fallback -> disable), against a real
auth-enabled app instance rather than the repo layer directly.

Deliberately does NOT configure auth via os.environ.setdefault(...) at
module level, unlike some older test files in this suite. `responsibleai
.dashboard.app` imports a single process-wide `settings` singleton
(get_settings() caches it) the first time *any* test module imports the
app — by the time this file's module body runs, some other test file
(collected first, alphabetically or otherwise) has already imported it
with whatever env was present then, and further os.environ changes here
have zero effect on that already-constructed object. Directly
monkeypatching the settings singleton's attributes per-test sidesteps
that entirely and is the actually-reliable way to flip auth on for one
test file without depending on collection order across the whole suite.
"""

from __future__ import annotations

import pyotp
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


@pytest.fixture(autouse=True)
def _auth_enabled_with_bootstrap_key(monkeypatch: pytest.MonkeyPatch):
    """Force auth on with one legacy bootstrap key for this file only,
    regardless of what any other already-imported test module left the
    shared settings singleton set to. Reverts automatically after each test."""
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    """Each test hits /api/orgs, /api/orgs/.../keys, and the mfa/* endpoints
    fresh — without this, slowapi's shared in-memory counters (keyed by the
    bootstrap Bearer token, same across every test in this file) trip their
    per-minute limits partway through the suite and fail tests with 429s
    that have nothing to do with what's actually being tested."""
    limiter.reset()
    yield


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as c:
            yield c


@pytest.fixture()
async def org_and_key(client: AsyncClient):
    """Bootstrap an org + an ADMIN-role key via the legacy flat key,
    the same way a fresh self-hosted deployment would."""
    r = await client.post(
        "/api/orgs", json={"name": "MFA Test Co", "slug": "mfa-test-co"}, headers=BOOTSTRAP_AUTH
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]

    r = await client.post(
        f"/api/orgs/{org_id}/keys",
        json={"name": "jane-dashboard", "role": "ADMIN"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    key_body = r.json()
    return org_id, key_body["id"], key_body["key"]


class TestLoginWithoutMFA:
    async def test_login_succeeds_with_valid_key(self, client: AsyncClient, org_and_key) -> None:
        _, _, raw_key = org_and_key
        r = await client.post("/api/auth/login-key", json={"api_key": raw_key})
        assert r.status_code == 200
        assert r.json() == {"ok": True, "mfa_required": False}

    async def test_login_rejects_invalid_key(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/login-key", json={"api_key": "rai_not_a_real_key"})
        assert r.status_code == 401


class TestMFAEnrollment:
    async def test_enroll_returns_secret_and_uri(self, client: AsyncClient, org_and_key) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        r = await client.post(f"/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert "secret" in body
        assert body["provisioning_uri"].startswith("otpauth://totp/")

    async def test_verify_with_correct_code_enrolls(self, client: AsyncClient, org_and_key) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        enroll = await client.post(f"/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", headers=auth)
        secret = enroll.json()["secret"]
        code = pyotp.TOTP(secret).now()

        r = await client.post(
            f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify", json={"code": code}, headers=auth
        )
        assert r.status_code == 200
        body = r.json()
        assert body["enrolled"] is True
        assert len(body["backup_codes"]) == 10

    async def test_verify_with_wrong_code_rejected(self, client: AsyncClient, org_and_key) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        await client.post(f"/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", headers=auth)
        r = await client.post(
            f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify", json={"code": "000000"}, headers=auth
        )
        assert r.status_code == 400

    async def test_verify_without_enrolling_first_rejected(
        self, client: AsyncClient, org_and_key
    ) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        r = await client.post(
            f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify", json={"code": "123456"}, headers=auth
        )
        assert r.status_code == 400


class TestOrgMFAEnforcement:
    async def _enroll(self, client: AsyncClient, org_id: str, key_id: str, auth: dict) -> str:
        enroll = await client.post(f"/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", headers=auth)
        secret = enroll.json()["secret"]
        code = pyotp.TOTP(secret).now()
        r = await client.post(
            f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify", json={"code": code}, headers=auth
        )
        return secret if r.status_code == 200 else ""

    async def test_login_without_code_reports_mfa_required(
        self, client: AsyncClient, org_and_key
    ) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        secret = await self._enroll(client, org_id, key_id, auth)
        assert secret

        await client.put(f"/api/orgs/{org_id}/mfa", json={"mfa_required": True}, headers=BOOTSTRAP_AUTH)

        r = await client.post("/api/auth/login-key", json={"api_key": raw_key})
        assert r.status_code == 200
        assert r.json() == {"ok": False, "mfa_required": True}

    async def test_login_with_correct_totp_code_succeeds(
        self, client: AsyncClient, org_and_key
    ) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        secret = await self._enroll(client, org_id, key_id, auth)
        await client.put(f"/api/orgs/{org_id}/mfa", json={"mfa_required": True}, headers=BOOTSTRAP_AUTH)

        code = pyotp.TOTP(secret).now()
        r = await client.post("/api/auth/login-key", json={"api_key": raw_key, "mfa_code": code})
        assert r.status_code == 200
        assert r.json()["ok"] is True

    async def test_login_with_wrong_totp_code_rejected(
        self, client: AsyncClient, org_and_key
    ) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        await self._enroll(client, org_id, key_id, auth)
        await client.put(f"/api/orgs/{org_id}/mfa", json={"mfa_required": True}, headers=BOOTSTRAP_AUTH)

        r = await client.post(
            "/api/auth/login-key", json={"api_key": raw_key, "mfa_code": "000000"}
        )
        assert r.status_code == 401

    async def test_unenrolled_key_blocked_when_org_requires_mfa(
        self, client: AsyncClient, org_and_key
    ) -> None:
        org_id, key_id, raw_key = org_and_key
        await client.put(f"/api/orgs/{org_id}/mfa", json={"mfa_required": True}, headers=BOOTSTRAP_AUTH)
        r = await client.post("/api/auth/login-key", json={"api_key": raw_key})
        assert r.status_code == 403

    async def test_login_with_backup_code_succeeds_and_is_single_use(
        self, client: AsyncClient, org_and_key
    ) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        enroll = await client.post(f"/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", headers=auth)
        secret = enroll.json()["secret"]
        code = pyotp.TOTP(secret).now()
        verify = await client.post(
            f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify", json={"code": code}, headers=auth
        )
        backup_code = verify.json()["backup_codes"][0]
        await client.put(f"/api/orgs/{org_id}/mfa", json={"mfa_required": True}, headers=BOOTSTRAP_AUTH)

        r = await client.post(
            "/api/auth/login-key", json={"api_key": raw_key, "mfa_code": backup_code}
        )
        assert r.status_code == 200
        assert r.json()["backup_code_used"] is True

        # Same backup code cannot be used a second time.
        r2 = await client.post(
            "/api/auth/login-key", json={"api_key": raw_key, "mfa_code": backup_code}
        )
        assert r2.status_code == 401


class TestDisableMFA:
    async def test_disable_clears_enrollment(self, client: AsyncClient, org_and_key) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        enroll = await client.post(f"/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", headers=auth)
        secret = enroll.json()["secret"]
        code = pyotp.TOTP(secret).now()
        await client.post(
            f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify", json={"code": code}, headers=auth
        )

        r = await client.delete(f"/api/orgs/{org_id}/keys/{key_id}/mfa", headers=auth)
        assert r.status_code == 200
        assert r.json()["mfa_enrolled"] is False


class TestAuthSession:
    async def test_session_reports_key_name_and_mfa_status(
        self, client: AsyncClient, org_and_key
    ) -> None:
        org_id, key_id, raw_key = org_and_key
        auth = {"Authorization": f"Bearer {raw_key}"}
        r = await client.get("/api/auth/session", headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert body["key_name"] == "jane-dashboard"
        assert body["org_id"] == org_id
        assert body["mfa_enrolled"] is False
