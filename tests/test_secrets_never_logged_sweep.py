# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""PR #93 secret-log redaction on the RC tree."""

from __future__ import annotations

import logging

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.rbac.models import Role


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    yield


@pytest.mark.asyncio
async def test_created_key_material_never_appears_in_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async with LifespanManager(app, startup_timeout=15):
        with caplog.at_level(logging.DEBUG):
            org = await app_module._org_repo.create_org("key-log-sweep", "key-log-sweep")
            _record, raw_key = await app_module._org_repo.create_key(
                org.id, "sweep-key", Role.ANALYST
            )
        assert raw_key and len(raw_key) > 10
        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert raw_key not in log_text


@pytest.mark.asyncio
async def test_totp_secret_and_backup_codes_never_appear_in_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    import pyotp

    async with LifespanManager(app, startup_timeout=15):
        org = await app_module._org_repo.create_org("mfa-log-sweep", "mfa-log-sweep")
        key, raw = await app_module._org_repo.create_key(org.id, "owner", Role.OWNER)
        headers = {"Authorization": f"Bearer {raw}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with caplog.at_level(logging.DEBUG):
                response = await client.post(
                    f"/api/orgs/{org.id}/keys/{key.id}/mfa/enroll", headers=headers
                )
                assert response.status_code == 200, response.text
                secret = response.json()["secret"]
                code = pyotp.TOTP(secret).now()
                response = await client.post(
                    f"/api/orgs/{org.id}/keys/{key.id}/mfa/verify",
                    json={"code": code},
                    headers=headers,
                )
                assert response.status_code == 200, response.text
                backup_codes = response.json()["backup_codes"]
        assert secret
        assert len(backup_codes) == 10
        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert secret not in log_text
        for backup_code in backup_codes:
            assert backup_code not in log_text


@pytest.mark.asyncio
async def test_signing_secret_never_appears_in_logs(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _fake_getaddrinfo(host, *args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)
    async with LifespanManager(app, startup_timeout=15):
        org = await app_module._org_repo.create_org("hook-log-sweep", "hook-log-sweep")
        _key, raw = await app_module._org_repo.create_key(org.id, "owner", Role.OWNER)
        headers = {"Authorization": f"Bearer {raw}"}
        secret = "a" * 40
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with caplog.at_level(logging.DEBUG):
                response = await client.post(
                    "/api/webhooks",
                    json={
                        "url": "https://hooks.example.com/sweep",
                        "events": ["approval_requested"],
                        "secret": secret,
                    },
                    headers=headers,
                )
                assert response.status_code == 200, response.text
        log_text = "\n".join(record.getMessage() for record in caplog.records)
        assert secret not in log_text


def test_database_driver_loggers_are_not_debug() -> None:
    from responsibleai.dashboard.logging_config import configure_logging

    configure_logging(level="DEBUG", json_logs=False)
    assert logging.getLogger("aiosqlite").level >= logging.INFO
    assert logging.getLogger("asyncpg").level >= logging.INFO
