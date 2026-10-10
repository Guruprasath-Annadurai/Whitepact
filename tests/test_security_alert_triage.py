# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests for CodeQL alerts that were open on the default branch (80, 81, 83, 86, 87, 96).

None is a remote-code-execution class defect. Each is the kind of leak or re-issue an auditor would
reasonably ask to be closed rather than explained: a credential fragment in a log line, a request
cookie echoed back as our own, and internal exception text returned to a caller.
"""

from __future__ import annotations

import logging

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import _accepted_oauth_tx_cookie, app, limiter, settings
from responsibleai.dashboard.websocket_manager import ConnectionManager, _key_fingerprint


class _Socket:
    async def accept(self) -> None:
        return None


async def test_websocket_logs_never_contain_any_part_of_the_api_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    key = "wp_test_SECRETSECRETSECRETSECRET1234"
    manager = ConnectionManager()
    socket = _Socket()
    with caplog.at_level(logging.DEBUG):
        await manager.connect(socket, key)  # type: ignore[arg-type]
        manager.disconnect(socket, key)  # type: ignore[arg-type]
    assert caplog.records, "expected connect/disconnect log records"
    for record in caplog.records:
        rendered = f"{record.getMessage()} {record.__dict__}"
        assert key not in rendered
        assert key[:8] not in rendered, "a key prefix is still being logged"
        assert key[-6:] not in rendered
    fingerprints = {getattr(r, "api_key_fingerprint", None) for r in caplog.records}
    assert _key_fingerprint(key) in fingerprints
    assert _key_fingerprint(key) != _key_fingerprint(key + "x")


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "short",
        "a" * 31,
        "a" * 129,
        "x; Path=/; Domain=.evil.example",
        "abc\r\nSet-Cookie: admin=1" + "a" * 40,
        "has space " + "a" * 40,
        "semi;colon" + "a" * 40,
    ],
)
def test_only_a_server_shaped_oauth_tx_cookie_is_reissued(value: str | None) -> None:
    assert _accepted_oauth_tx_cookie(value) is None


@pytest.mark.parametrize("value", ["A" * 43, "a-b_c" * 8, "0" * 64])
def test_a_server_shaped_oauth_tx_cookie_is_kept(value: str) -> None:
    assert _accepted_oauth_tx_cookie(value) == value


async def test_restore_reconcile_does_not_return_internal_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from responsibleai.data_governance import backup_defense

    secret = "/var/lib/whitepact/secret-path stack: Traceback (most recent call last)"

    async def boom(self, reconciled_by: str):  # noqa: ANN001
        raise backup_defense.RestoreReconciliationError(secret)

    monkeypatch.setattr(backup_defense.RestoreReconciliationEngine, "reconcile_post_restore", boom)
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(limiter, "enabled", False)
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            response = await client.post("/api/restore/reconcile", json={})
    assert response.status_code == 500, response.text
    body = response.json()
    assert body["error"] == "reconciliation_failed"
    assert "secret-path" not in response.text and "Traceback" not in response.text


@pytest.fixture
async def oidc_login_client(monkeypatch: pytest.MonkeyPatch):
    from unittest.mock import MagicMock

    import responsibleai.dashboard.app as app_module

    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "oidc_redirect_uri", "https://app.example/cb")
    monkeypatch.setattr(limiter, "enabled", False)
    async with LifespanManager(app) as manager:
        provider = MagicMock()
        provider.authorization_url.return_value = "https://idp.example/authorize?x=1"
        monkeypatch.setattr(app_module, "_oidc_provider", provider)
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


async def test_oidc_login_never_echoes_a_request_supplied_cookie_as_its_own(
    oidc_login_client: AsyncClient,
) -> None:
    hostile = "x; Path=/; Domain=.evil.example" + "a" * 40
    for supplied in (hostile, "short", ""):
        response = await oidc_login_client.get(
            "/api/auth/login/oidc", headers={"Cookie": f"wp_oauth_tx={supplied}"}
        )
        assert response.status_code == 200, response.text
        issued = response.headers.get_list("set-cookie")
        assert len(issued) == 1, issued
        value = issued[0].split(";", 1)[0].split("=", 1)[1]
        assert value != supplied and "evil" not in issued[0]
        assert len(value) >= 32  # a freshly minted server value


async def test_oidc_login_reuses_a_server_shaped_cookie_without_re_issuing_it(
    oidc_login_client: AsyncClient,
) -> None:
    server_shaped = "A" * 43
    response = await oidc_login_client.get(
        "/api/auth/login/oidc", headers={"Cookie": f"wp_oauth_tx={server_shaped}"}
    )
    assert response.status_code == 200, response.text
    assert response.headers.get_list("set-cookie") == []
