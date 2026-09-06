# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Security and lifecycle tests for the WhitePact human web platform."""

from __future__ import annotations

import os
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("RAI_DB_PATH", ":memory:")
os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")

import responsibleai.dashboard.app as app_module
from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import (
    DuplicateWebUserError,
    WebIdentityRepository,
    verify_password,
)


@pytest.fixture()
async def repository_pair():
    engine = create_engine(":memory:")
    await engine.init()
    yield WebIdentityRepository(engine), OrgRepository(engine)
    await engine.close()


async def test_identity_requires_verification_and_binds_membership(repository_pair):
    identities, _keys = repository_pair
    user_id, token = await identities.register(
        "Ada Lovelace", "ADA@Example.com", "Correct-Horse-42!"
    )
    assert await identities.authenticate("ada@example.com", "Correct-Horse-42!") is None
    assert await identities.verify_email(token) is True
    assert await identities.verify_email(token) is False
    assert await identities.authenticate("ada@example.com", "Wrong-Horse-99!") is None
    assert await identities.authenticate("ada@example.com", "Correct-Horse-42!") is not None
    assert await identities.primary_org_id(user_id) is None
    unbound_session, _ = await identities.create_session(user_id)
    unbound_principal = await identities.get_principal(unbound_session)
    assert unbound_principal is not None
    assert unbound_principal.org_id is None
    org_id = await identities.attach_organization(user_id, name="Analytical Engines", slug="ae")
    session, csrf = await identities.create_session(user_id, org_id=org_id)
    principal = await identities.get_principal(session)
    assert principal is not None
    assert principal.org_id == org_id
    assert principal.csrf_hash != csrf


def test_password_verifier_rejects_unknown_or_malformed_encodings():
    assert verify_password("irrelevant", "argon2$1$2$3$c2FsdA==$ZGlnZXN0") is False
    assert verify_password("irrelevant", "not-a-password-hash") is False


async def test_unknown_or_revoked_session_has_no_principal(repository_pair):
    identities, _keys = repository_pair
    assert await identities.get_principal("unknown-session") is None
    user_id, token = await identities.register("Ada", "revoked@example.com", "Correct-Horse-42!")
    assert await identities.verify_email(token) is True
    session, _ = await identities.create_session(user_id)
    await identities.revoke_session(session)
    assert await identities.get_principal(session) is None


async def test_password_reset_is_single_use_and_revokes_sessions(repository_pair):
    identities, _keys = repository_pair
    user_id, verification = await identities.register(
        "Katherine Johnson", "kj@example.com", "Orbital-Math-42!"
    )
    assert await identities.verify_email(verification) is True
    session, _ = await identities.create_session(user_id)
    reset = await identities.create_password_reset("KJ@example.com")
    assert reset is not None
    _email, _name, token = reset
    assert await identities.reset_password(token, "Moonflight-Secure-73!") is True
    assert await identities.reset_password(token, "Another-Secure-74!") is False
    assert await identities.get_principal(session) is None
    assert await identities.authenticate("kj@example.com", "Orbital-Math-42!") is None
    assert await identities.authenticate("kj@example.com", "Moonflight-Secure-73!") is not None


async def test_password_reset_unknown_email_is_indistinguishable(repository_pair):
    identities, _keys = repository_pair
    assert await identities.create_password_reset("unknown@example.com") is None


async def test_duplicate_normalized_email_is_rejected(repository_pair):
    identities, _keys = repository_pair
    await identities.register("Ada", "ada@example.com", "Correct-Horse-42!")
    with pytest.raises(DuplicateWebUserError):
        await identities.register("Other", " ADA@example.com ", "Different-Horse-43!")


async def test_atomic_rotation_is_unique_and_tenant_scoped(repository_pair):
    _identities, keys = repository_pair
    first_org = await keys.create_org("First", "first")
    second_org = await keys.create_org("Second", "second")
    original, raw_original = await keys.create_key(
        first_org.id,
        "runtime",
        environment="live",
        scopes=("governance:read",),
    )
    assert await keys.revoke_key(original.id, org_id=second_org.id) is False
    rotated = await keys.rotate_key(first_org.id, original.id)
    assert rotated is not None
    replacement, raw_replacement = rotated
    assert replacement.id != original.id
    assert raw_replacement != raw_original
    assert raw_replacement.startswith("wp_live_")
    assert await keys.authenticate(raw_original) is None
    assert (await keys.authenticate(raw_replacement)).scopes == frozenset({"governance:read"})
    assert await keys.rotate_key(first_org.id, original.id) is None


@pytest.fixture()
async def web_client(monkeypatch):
    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


async def _verified_session(client: AsyncClient) -> str:
    registration = await client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Grace Hopper",
            "email": "grace@example.com",
            "password": "Compiler-Pioneer-42!",
            "accepted_terms": True,
        },
    )
    assert registration.status_code == 202
    token = parse_qs(urlparse(registration.json()["verification_url"]).query)["token"][0]
    assert (await client.post("/api/v1/web/auth/verify", json={"token": token})).status_code == 200
    login = await client.post(
        "/api/v1/web/auth/login",
        json={"email": "grace@example.com", "password": "Compiler-Pioneer-42!"},
    )
    assert login.status_code == 200
    return client.cookies["wp_csrf"]


async def test_csrf_onboarding_and_one_time_key_lifecycle(web_client):
    csrf = await _verified_session(web_client)
    denied = await web_client.post(
        "/api/v1/web/onboarding",
        json={"organization_name": "Compilers Inc", "use_case": "Agent development"},
    )
    assert denied.status_code == 403
    onboarded = await web_client.post(
        "/api/v1/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": "Compilers Inc", "use_case": "Agent development"},
    )
    assert onboarded.status_code == 200
    created = await web_client.post(
        "/api/v1/web/api-keys",
        headers={"X-WP-CSRF": csrf},
        json={
            "name": "test agent",
            "environment": "test",
            "scopes": ["governance:read", "evidence:read"],
        },
    )
    assert created.status_code == 201
    raw = created.json()["api_key"]
    listed = await web_client.get("/api/v1/web/api-keys")
    assert listed.status_code == 200
    assert "api_key" not in listed.json()["keys"][0]
    rotated = await web_client.post(
        f"/api/v1/web/api-keys/{created.json()['id']}/rotate",
        headers={"X-WP-CSRF": csrf},
    )
    assert rotated.status_code == 200
    assert rotated.json()["api_key"] != raw
    revoked = await web_client.delete(
        f"/api/v1/web/api-keys/{rotated.json()['id']}",
        headers={"X-WP-CSRF": csrf},
    )
    assert revoked.status_code == 200
    assert (await web_client.get("/api/v1/web/api-keys")).json()["keys"] == []


async def test_password_reset_api_end_to_end(web_client):
    registration = await web_client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Margaret Hamilton",
            "email": "hamilton@example.com",
            "password": "Apollo-Software-42!",
            "accepted_terms": True,
        },
    )
    verification = parse_qs(urlparse(registration.json()["verification_url"]).query)["token"][0]
    assert (
        await web_client.post("/api/v1/web/auth/verify", json={"token": verification})
    ).status_code == 200
    requested = await web_client.post(
        "/api/v1/web/auth/password-reset", json={"email": "hamilton@example.com"}
    )
    assert requested.status_code == 202
    reset_token = parse_qs(urlparse(requested.json()["reset_url"]).query)["token"][0]
    confirmed = await web_client.post(
        "/api/v1/web/auth/password-reset/confirm",
        json={"token": reset_token, "password": "Apollo-Recovered-73!"},
    )
    assert confirmed.status_code == 200
    assert (
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "hamilton@example.com", "password": "Apollo-Software-42!"},
        )
    ).status_code == 401
    assert (
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "hamilton@example.com", "password": "Apollo-Recovered-73!"},
        )
    ).status_code == 200

    unknown = await web_client.post(
        "/api/v1/web/auth/password-reset", json={"email": "nobody@example.com"}
    )
    assert unknown.status_code == 202
    assert unknown.json() == {"status": "accepted"}

    invalid = await web_client.post(
        "/api/v1/web/auth/password-reset/confirm",
        json={"token": "x" * 32, "password": "Another-Secure-74!"},
    )
    assert invalid.status_code == 400


@respx.mock
async def test_password_reset_delivery_uses_authenticated_https_webhook(monkeypatch):
    delivery = respx.post("https://mailer.example.com/transactional").mock(
        return_value=httpx.Response(202)
    )
    monkeypatch.setattr(
        app_module.settings,
        "web_verification_delivery_url",
        "https://mailer.example.com/transactional",
    )
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_token", "delivery-token")

    await app_module._deliver_password_reset(
        "person@example.com",
        "Person Name",
        "https://whitepact.com/reset-password?token=opaque",
    )

    request = delivery.calls.last.request
    assert request.headers["authorization"] == "Bearer delivery-token"
    assert b'"template":"whitepact-password-reset"' in request.content
