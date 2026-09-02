"""Enterprise Readiness Phase 9 — extends the secrets-never-logged
pattern (`tests/test_crypto_activation.py::TestSecretsNeverAppearInLogs`,
previously scoped to crypto root key / DEK activation only) to every
other credential-handling module: API key creation, TOTP MFA
enrollment (secret + backup codes), and webhook signing secrets.

Real requests through the real REST API, with `caplog` capturing
everything structlog/stdlib logging emits at DEBUG level -- the same
proof mechanism the crypto_activation test already established, not a
new invention.
"""

from __future__ import annotations

import logging

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings

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
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


async def _new_org(client: AsyncClient) -> tuple[str, str]:
    r = await client.post(
        "/api/orgs",
        json={"name": "secrets-sweep-co", "slug": "secrets-sweep-co"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    r = await client.post(
        f"/api/orgs/{org_id}/keys",
        json={"name": "owner-key", "role": "OWNER"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


class TestAPIKeySecretsNeverLogged:
    async def test_created_key_material_never_appears_in_logs(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.DEBUG):
            r = await client.post(
                "/api/orgs",
                json={"name": "key-log-sweep", "slug": "key-log-sweep"},
                headers=BOOTSTRAP_AUTH,
            )
            org_id = r.json()["id"]
            r = await client.post(
                f"/api/orgs/{org_id}/keys",
                json={"name": "sweep-key", "role": "ANALYST"},
                headers=BOOTSTRAP_AUTH,
            )
            raw_key = r.json()["key"]

        assert raw_key and len(raw_key) > 10  # sanity: a real key was actually issued
        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert raw_key not in log_text


class TestMFASecretsNeverLogged:
    async def test_totp_secret_and_backup_codes_never_appear_in_logs(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture
    ) -> None:
        import pyotp

        org_id, owner_key = await _new_org(client)
        headers = {"Authorization": f"Bearer {owner_key}"}
        r = await client.get(f"/api/orgs/{org_id}/keys", headers=headers)
        key_id = r.json()["keys"][0]["id"]

        with caplog.at_level(logging.DEBUG):
            r = await client.post(f"/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", headers=headers)
            secret = r.json()["secret"]
            code = pyotp.TOTP(secret).now()
            r = await client.post(
                f"/api/orgs/{org_id}/keys/{key_id}/mfa/verify",
                json={"code": code},
                headers=headers,
            )
            backup_codes = r.json()["backup_codes"]

        assert secret
        assert len(backup_codes) == 10
        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert secret not in log_text
        for backup_code in backup_codes:
            assert backup_code not in log_text


class TestWebhookSecretsNeverLogged:
    async def test_signing_secret_never_appears_in_logs(
        self, client: AsyncClient, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("93.184.216.34", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)
        org_id, owner_key = await _new_org(client)
        headers = {"Authorization": f"Bearer {owner_key}"}
        secret = "a" * 40  # meets the 32-char entropy floor

        with caplog.at_level(logging.DEBUG):
            r = await client.post(
                "/api/webhooks",
                json={
                    "url": "https://hooks.example.com/sweep",
                    "events": ["approval_requested"],
                    "secret": secret,
                },
                headers=headers,
            )
            assert r.status_code == 200, r.text

        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert secret not in log_text
