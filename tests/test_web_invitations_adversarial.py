# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-4 M3 — adversarial web invitation and membership lifecycle (P1-02)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

from responsibleai.dashboard import app as app_module
from responsibleai.db.engine import web_invitations


@pytest.fixture()
async def web_client(monkeypatch: pytest.MonkeyPatch):
    from responsibleai.dashboard.signup_guard import SignupRateWindow

    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=30, window_seconds=3600.0)
    )
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


async def _register_verify_login(
    client: AsyncClient, *, email: str, password: str, full_name: str
) -> str:
    reg = await client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": full_name,
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202, reg.text
    token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    assert (await client.post("/api/v1/web/auth/verify", json={"token": token})).status_code == 200
    login = await client.post(
        "/api/v1/web/auth/login",
        json={"email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return client.cookies["wp_csrf"]


def _unique_email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


async def _onboard_owner(client: AsyncClient, email: str | None = None) -> str:
    owner_email = email or _unique_email("owner-inv")
    csrf = await _register_verify_login(
        client,
        email=owner_email,
        password="Owner-Invite-42!",
        full_name="Invite Owner",
    )
    onboard = await client.post(
        "/api/v1/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": f"Invite Org {owner_email[:12]}", "use_case": "Testing"},
    )
    assert onboard.status_code == 200, onboard.text
    return client.cookies["wp_csrf"]


def _invite_token(invite_body: dict) -> str:
    return parse_qs(urlparse(invite_body["invitation_url"]).query)["token"][0]


@pytest.mark.asyncio
async def test_invitation_create_requires_admin(web_client: AsyncClient) -> None:
    owner_csrf = await _onboard_owner(web_client)
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": "member@example.com", "role": "VIEWER"},
    )
    assert invite.status_code == 202
    token = _invite_token(invite.json())
    member_csrf = await _register_verify_login(
        web_client,
        email="member@example.com",
        password="Member-Invite-42!",
        full_name="Member",
    )
    accept = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": member_csrf},
        json={"token": token},
    )
    assert accept.status_code == 200
    member_csrf = web_client.cookies["wp_csrf"]
    denied = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": member_csrf},
        json={"email": "other@example.com", "role": "VIEWER"},
    )
    assert denied.status_code == 403


@pytest.mark.asyncio
async def test_invitation_wrong_email_and_replay(web_client: AsyncClient) -> None:
    owner_csrf = await _onboard_owner(web_client, "owner-replay@example.com")
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": "intended@example.com", "role": "ANALYST"},
    )
    assert invite.status_code == 202
    token = _invite_token(invite.json())
    wrong_csrf = await _register_verify_login(
        web_client,
        email="wrong@example.com",
        password="Wrong-Invite-42!",
        full_name="Wrong User",
    )
    wrong = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": wrong_csrf},
        json={"token": token},
    )
    assert wrong.status_code == 400
    intended_csrf = await _register_verify_login(
        web_client,
        email="intended@example.com",
        password="Intended-Invite-42!",
        full_name="Intended User",
    )
    first = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": intended_csrf},
        json={"token": token},
    )
    assert first.status_code == 200
    replay_csrf = web_client.cookies["wp_csrf"]
    replay = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": replay_csrf},
        json={"token": token},
    )
    assert replay.status_code == 400


@pytest.mark.asyncio
async def test_invitation_revoke_before_accept(web_client: AsyncClient) -> None:
    owner_csrf = await _onboard_owner(web_client, "owner-revoke@example.com")
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": "revoked@example.com", "role": "VIEWER"},
    )
    assert invite.status_code == 202
    invite_id = invite.json()["id"]
    token = _invite_token(invite.json())
    revoked = await web_client.delete(
        f"/api/v1/web/invitations/{invite_id}",
        headers={"X-WP-CSRF": owner_csrf},
    )
    assert revoked.status_code == 200
    member_csrf = await _register_verify_login(
        web_client,
        email="revoked@example.com",
        password="Revoked-Invite-42!",
        full_name="Revoked User",
    )
    accept = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": member_csrf},
        json={"token": token},
    )
    assert accept.status_code == 400


@pytest.mark.asyncio
async def test_invitation_expired_token_rejected(web_client: AsyncClient) -> None:
    owner_csrf = await _onboard_owner(web_client, "owner-expire@example.com")
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": "expired@example.com", "role": "VIEWER"},
    )
    assert invite.status_code == 202
    invite_id = invite.json()["id"]
    token = _invite_token(invite.json())
    engine = app_module._ready(app_module._db_engine)
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_invitations).where(web_invitations.c.id == invite_id).values(expires_at=past)
        )
    member_csrf = await _register_verify_login(
        web_client,
        email="expired@example.com",
        password="Expired-Invite-42!",
        full_name="Expired User",
    )
    accept = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": member_csrf},
        json={"token": token},
    )
    assert accept.status_code == 400


@pytest.mark.asyncio
async def test_role_downgrade_revokes_member_session(web_client: AsyncClient) -> None:
    owner_csrf = await _onboard_owner(web_client, "owner-downgrade@example.com")
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": "admin-down@example.com", "role": "ADMIN"},
    )
    assert invite.status_code == 202
    token = _invite_token(invite.json())
    admin_csrf = await _register_verify_login(
        web_client,
        email="admin-down@example.com",
        password="Admin-Down-42!",
        full_name="Admin Down",
    )
    accept = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": admin_csrf},
        json={"token": token},
    )
    assert accept.status_code == 200
    admin_session_token = web_client.cookies["wp_session"]
    admin_csrf_stored = web_client.cookies["wp_csrf"]
    admin_session = await web_client.get("/api/v1/web/session")
    assert admin_session.status_code == 200
    admin_user_id = admin_session.json()["user"]["id"]

    await web_client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": admin_csrf_stored})
    owner_login = await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": "owner-downgrade@example.com", "password": "Owner-Invite-42!"},
    )
    assert owner_login.status_code == 200
    owner_csrf = web_client.cookies["wp_csrf"]
    downgrade = await web_client.patch(
        f"/api/v1/web/members/{admin_user_id}",
        headers={"X-WP-CSRF": owner_csrf},
        json={"role": "VIEWER"},
    )
    assert downgrade.status_code == 200

    stale = AsyncClient(
        transport=ASGITransport(app=web_client._transport.app),
        base_url="http://test",
        cookies={"wp_session": admin_session_token, "wp_csrf": admin_csrf_stored},
    )
    async with stale:
        stale_session = await stale.get("/api/v1/web/session")
        assert stale_session.status_code == 401


@pytest.mark.asyncio
async def test_member_removal_revokes_session(web_client: AsyncClient) -> None:
    owner_csrf = await _onboard_owner(web_client, "owner-remove@example.com")
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": "remove-me@example.com", "role": "VIEWER"},
    )
    token = _invite_token(invite.json())
    member_csrf = await _register_verify_login(
        web_client,
        email="remove-me@example.com",
        password="Remove-Me-42!",
        full_name="Remove Me",
    )
    await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": member_csrf},
        json={"token": token},
    )
    member_session_token = web_client.cookies["wp_session"]
    member_csrf_stored = web_client.cookies["wp_csrf"]
    member_id = (await web_client.get("/api/v1/web/session")).json()["user"]["id"]

    await web_client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": member_csrf_stored})
    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": "owner-remove@example.com", "password": "Owner-Invite-42!"},
    )
    owner_csrf = web_client.cookies["wp_csrf"]
    removed = await web_client.delete(
        f"/api/v1/web/members/{member_id}",
        headers={"X-WP-CSRF": owner_csrf},
    )
    assert removed.status_code == 200

    stale = AsyncClient(
        transport=ASGITransport(app=web_client._transport.app),
        base_url="http://test",
        cookies={"wp_session": member_session_token, "wp_csrf": member_csrf_stored},
    )
    async with stale:
        assert (await stale.get("/api/v1/web/session")).status_code == 401


@pytest.mark.asyncio
async def test_cross_tenant_cannot_revoke_foreign_invitation(web_client: AsyncClient) -> None:
    owner_a = _unique_email("owner-a")
    owner_b = _unique_email("owner-b")
    csrf_a = await _onboard_owner(web_client, owner_a)
    invite_a = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": csrf_a},
        json={"email": _unique_email("member-a"), "role": "VIEWER"},
    )
    invite_id_a = invite_a.json()["id"]
    await web_client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": csrf_a})
    csrf_b = await _onboard_owner(web_client, owner_b)
    foreign = await web_client.delete(
        f"/api/v1/web/invitations/{invite_id_a}",
        headers={"X-WP-CSRF": csrf_b},
    )
    assert foreign.status_code == 404


@pytest.mark.asyncio
async def test_duplicate_invite_supersedes_pending(web_client: AsyncClient) -> None:
    owner_email = _unique_email("dup-owner")
    owner_csrf = await _onboard_owner(web_client, owner_email)
    member_email = _unique_email("dup-member")
    first = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": member_email, "role": "VIEWER"},
    )
    first_id = first.json()["id"]
    first_token = parse_qs(urlparse(first.json()["invitation_url"]).query)["token"][0]
    second = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": member_email, "role": "ANALYST"},
    )
    second_token = parse_qs(urlparse(second.json()["invitation_url"]).query)["token"][0]
    assert first_token != second_token
    member_csrf = await _register_verify_login(
        web_client,
        email=member_email,
        password="Member-Invite-42!",
        full_name="Dup Member",
    )
    stale_accept = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": member_csrf},
        json={"token": first_token},
    )
    assert stale_accept.status_code == 400
    fresh_accept = await web_client.post(
        "/api/v1/web/invitations/accept",
        headers={"X-WP-CSRF": member_csrf},
        json={"token": second_token},
    )
    assert fresh_accept.status_code == 200
    await web_client.post(
        "/api/v1/web/auth/logout", headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]}
    )
    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": owner_email, "password": "Owner-Invite-42!"},
    )
    owner_csrf = web_client.cookies["wp_csrf"]
    listing = await web_client.get("/api/v1/web/invitations", headers={"X-WP-CSRF": owner_csrf})
    statuses = {item["id"]: item["status"] for item in listing.json()["invitations"]}
    assert statuses.get(first_id) == "REVOKED"
