# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Browser-origin binding at actual passkey challenge issuance and persistence."""

import pytest
from sqlalchemy import select
from starlette.requests import Request

import responsibleai.dashboard.app as dashboard
from responsibleai.db.engine import create_engine, metadata, webauthn_challenges
from responsibleai.enterprise.security import router


@pytest.fixture
async def origin_engine(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'origin.db'}")
    async with engine.raw.begin() as connection:
        await connection.run_sync(metadata.create_all)
    monkeypatch.setattr(router, "get_enterprise_engine", lambda: engine)
    monkeypatch.setattr(dashboard.settings, "environment", "development")
    for key in ("WHITEPACT_WEBAUTHN_ORIGIN", "WHITEPACT_WEBAUTHN_RP_ID", "WP_ORIGIN", "WP_RP_ID"):
        monkeypatch.delenv(key, raising=False)
    yield engine
    await engine.raw.dispose()


def browser_request(origin="http://localhost:32123"):
    return Request(
        {
            "type": "http",
            "scheme": "http",
            "server": ("localhost", 32123),
            "method": "POST",
            "path": "/api/enterprise/passkeys/authenticate/begin",
            "headers": [(b"host", b"localhost:32123"), (b"origin", origin.encode())],
        }
    )


@pytest.mark.asyncio
async def test_challenge_and_storage_bind_actual_loopback_origin(origin_engine):
    result = await router.passkey_auth_begin(browser_request())
    assert isinstance(result, dict)
    assert result["origin"] == "http://localhost:32123"
    assert result["rpId"] == "localhost"
    async with origin_engine.raw.connect() as connection:
        row = (await connection.execute(select(webauthn_challenges))).one()
        assert row.origin == result["origin"]
        assert row.rp_id == result["rpId"]


@pytest.mark.asyncio
async def test_forwarded_headers_cannot_replace_browser_origin(origin_engine):
    request = browser_request()
    request.scope["headers"] += [
        (b"x-forwarded-host", b"evil.example"),
        (b"x-forwarded-proto", b"https"),
    ]
    result = await router.passkey_auth_begin(request)
    assert result["origin"] == "http://localhost:32123"
    assert result["rpId"] == "localhost"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://localhost.evil.example",
        "http://user@localhost:32123",
        "http://localhost:32123/path",
    ],
)
async def test_untrusted_browser_origin_does_not_issue_challenge(origin_engine, origin):
    result = await router.passkey_auth_begin(browser_request(origin))
    assert result.status_code == 400
    async with origin_engine.raw.connect() as connection:
        assert (await connection.execute(select(webauthn_challenges))).first() is None


@pytest.mark.asyncio
async def test_production_uses_configured_https_not_request_origin(origin_engine, monkeypatch):
    monkeypatch.setattr(dashboard.settings, "environment", "production")
    monkeypatch.setenv("WHITEPACT_WEBAUTHN_ORIGIN", "https://app.example.com")
    monkeypatch.setenv("WHITEPACT_WEBAUTHN_RP_ID", "app.example.com")
    result = await router.passkey_auth_begin(browser_request("https://evil.example"))
    assert result["origin"] == "https://app.example.com"
    assert result["rpId"] == "app.example.com"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "origin,rp_id",
    [
        ("", "app.example.com"),
        ("http://app.example.com", "app.example.com"),
        ("https://app.example.com", "evil.example"),
    ],
)
async def test_invalid_production_configuration_does_not_issue_challenge(
    origin_engine, monkeypatch, origin, rp_id
):
    monkeypatch.setattr(dashboard.settings, "environment", "production")
    monkeypatch.setenv("WHITEPACT_WEBAUTHN_ORIGIN", origin)
    monkeypatch.setenv("WHITEPACT_WEBAUTHN_RP_ID", rp_id)
    result = await router.passkey_auth_begin(browser_request())
    assert result.status_code == 500
    async with origin_engine.raw.connect() as connection:
        assert (await connection.execute(select(webauthn_challenges))).first() is None
