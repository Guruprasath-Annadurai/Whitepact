# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-X WebAuthn origin binding and resolution tests."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import responsibleai.dashboard.app as app_module
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.service import EnterpriseIAM


@pytest.fixture
async def webauthn_client(monkeypatch, tmp_path):
    db_file = tmp_path / "webauthn-origin.db"
    monkeypatch.setattr(app_module.settings, "database_url", f"sqlite+aiosqlite:///{db_file}")
    monkeypatch.setattr(app_module.settings, "db_path", str(db_file))
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "auth_enabled", True)
    monkeypatch.setattr(app_module.settings, "api_keys", [])
    monkeypatch.setattr(app_module.settings, "environment", "development")
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://localhost:59999"
        ) as c:
            yield c


async def create_user_session(email: str) -> tuple[str, str, str]:
    engine = get_enterprise_engine()
    identities = WebIdentityRepository(engine)
    user_id, verification = await identities.register("Passkey User", email, "SecurePasskey123!@#")
    await identities.verify_email(verification)
    slug = f"passkey-org-{email.split('@')[0]}"
    org = await EnterpriseIAM(engine).create_workspace(
        actor_user_id=user_id, name="Passkey Org", slug=slug, kind="ORGANIZATION"
    )
    token, csrf = await identities.create_session(user_id, org_id=org["id"])
    return user_id, token, csrf


@pytest.mark.asyncio
async def test_dynamic_origin_binding_in_development(webauthn_client):
    _, token, csrf = await create_user_session("dev.passkey@example.com")
    webauthn_client.cookies.set("wp_session", token)
    webauthn_client.cookies.set("wp_csrf", csrf)

    # 1. Client at loopback port 59999
    res = await webauthn_client.post(
        "/api/enterprise/passkeys/register/begin",
        headers={"X-WhitePact-CSRF": csrf, "Origin": "http://localhost:59999"},
    )
    assert res.status_code == 200, res.text
    challenge = res.json()
    assert challenge["origin"] == "http://localhost:59999"
    assert challenge["rpId"] == "localhost"

    # 2. Client at 127.0.0.1 with dynamic port
    res_127 = await webauthn_client.post(
        "/api/enterprise/passkeys/register/begin",
        headers={"X-WhitePact-CSRF": csrf, "Origin": "http://127.0.0.1:43210"},
    )
    assert res_127.status_code == 200, res_127.text
    challenge_127 = res_127.json()
    assert challenge_127["origin"] == "http://127.0.0.1:43210"
    assert challenge_127["rpId"] == "localhost"


@pytest.mark.asyncio
async def test_configured_origin_takes_precedence(webauthn_client, monkeypatch):
    monkeypatch.setattr(
        app_module.settings, "webauthn_origin", "https://auth.whitepact.example.com"
    )
    monkeypatch.setattr(app_module.settings, "webauthn_rp_id", "whitepact.example.com")

    _, token, csrf = await create_user_session("pinned.passkey@example.com")
    webauthn_client.cookies.set("wp_session", token)
    webauthn_client.cookies.set("wp_csrf", csrf)

    res = await webauthn_client.post(
        "/api/enterprise/passkeys/register/begin",
        headers={"X-WhitePact-CSRF": csrf, "Origin": "http://localhost:59999"},
    )
    assert res.status_code == 200
    challenge = res.json()
    # Explicitly configured origin overrides client header
    assert challenge["origin"] == "https://auth.whitepact.example.com"
    assert challenge["rpId"] == "whitepact.example.com"


@pytest.mark.asyncio
async def test_non_production_rejects_untrusted_external_origin_header(webauthn_client):
    _, token, csrf = await create_user_session("hostile.origin@example.com")
    webauthn_client.cookies.set("wp_session", token)
    webauthn_client.cookies.set("wp_csrf", csrf)

    res = await webauthn_client.post(
        "/api/enterprise/passkeys/register/begin",
        headers={"X-WhitePact-CSRF": csrf, "Origin": "https://evil.attacker.example"},
    )
    assert res.status_code == 400
    assert res.json()["code"] == "WEBAUTHN_INVALID"


@pytest.mark.asyncio
async def test_production_ignores_forwarded_and_hostile_headers_and_enforces_rp_id(
    webauthn_client, monkeypatch
):
    from responsibleai.enterprise.errors import EnterpriseError
    from responsibleai.enterprise.security import router as sec_router

    monkeypatch.setattr(app_module.settings, "environment", "production")
    monkeypatch.setattr(app_module.settings, "allowed_origins", ["https://evil.example.com"])
    monkeypatch.setattr(app_module.settings, "web_public_url", "https://evil.example.com")

    # 1. Missing configured origin fails closed even when allowed_origins / web_public_url exist
    monkeypatch.setattr(app_module.settings, "webauthn_origin", "")
    monkeypatch.setattr(app_module.settings, "webauthn_rp_id", "app.example.com")
    with pytest.raises(EnterpriseError):
        sec_router._svc()

    # 2. RP-ID mismatch with origin host fails closed
    monkeypatch.setattr(app_module.settings, "webauthn_origin", "https://app.example.com")
    monkeypatch.setattr(app_module.settings, "webauthn_rp_id", "other.example.com")
    with pytest.raises(EnterpriseError):
        sec_router._svc()

    # 3. Loopback HTTPS or IP literal fails closed in production
    monkeypatch.setattr(app_module.settings, "webauthn_origin", "https://localhost:3000")
    monkeypatch.setattr(app_module.settings, "webauthn_rp_id", "localhost")
    with pytest.raises(EnterpriseError):
        sec_router._svc()

    # 4. Path or query in configured origin fails closed
    monkeypatch.setattr(app_module.settings, "webauthn_origin", "https://app.example.com/subpath")
    monkeypatch.setattr(app_module.settings, "webauthn_rp_id", "app.example.com")
    with pytest.raises(EnterpriseError):
        sec_router._svc()
