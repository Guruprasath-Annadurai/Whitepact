# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Web account lifecycle (P1-07)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.iam.enums import StepUpMethod
from responsibleai.iam.models import StepUpProof
from responsibleai.iam.step_up import StepUpVerifier


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


def _email(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10]}@example.com"


async def _onboard(web_client: AsyncClient) -> tuple[str, str, str]:
    email = _email("lifecycle-owner")
    password = "Lifecycle-Owner-42!"
    reg = await web_client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Lifecycle Owner",
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    await web_client.post("/api/v1/web/auth/verify", json={"token": token})
    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": email, "password": password},
    )
    csrf = web_client.cookies["wp_csrf"]
    onboard = await web_client.post(
        "/api/v1/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": "Lifecycle Org", "use_case": "Testing"},
    )
    assert onboard.status_code == 200
    session = (await web_client.get("/api/v1/web/session")).json()
    user_id = session["user"]["id"]
    org_id = session["organization"]["id"]
    return email, password, user_id, org_id


async def _step_up_proof(org_id: str, user_id: str, *, action: str = "DESTROY_TENANT") -> dict:
    engine = app_module._ready(app_module._db_engine)
    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id=org_id,
        principal_id=user_id,
        action=action,
    )
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=datetime.now(UTC).isoformat(),
        token_or_code="123456",
    )
    return {
        "nonce": proof.nonce,
        "method": proof.method.value,
        "auth_time": proof.auth_time,
        "token_or_code": proof.token_or_code,
    }


@pytest.mark.asyncio
async def test_account_delete_requires_password_and_clears_session(web_client: AsyncClient) -> None:
    email, password, user_id, org_id = await _onboard(web_client)
    csrf = web_client.cookies["wp_csrf"]

    def _delete_headers(proof: dict) -> dict[str, str]:
        return {
            "X-WP-CSRF": csrf,
            "X-Step-Up-Nonce": proof["nonce"],
            "X-Step-Up-Method": proof["method"],
            "X-Step-Up-Auth-Time": proof["auth_time"],
            "X-Step-Up-Token": proof["token_or_code"],
        }

    step_up = await _step_up_proof(org_id, user_id)
    bad = await web_client.request(
        "DELETE",
        "/api/v1/web/account",
        headers=_delete_headers(step_up),
        json={"password": "wrong-password-!", "confirmation": "DELETE MY ACCOUNT"},
    )
    assert bad.status_code == 403
    step_up = await _step_up_proof(org_id, user_id)
    blocked = await web_client.request(
        "DELETE",
        "/api/v1/web/account",
        headers=_delete_headers(step_up),
        json={"password": password, "confirmation": "DELETE MY ACCOUNT"},
    )
    assert blocked.status_code == 409
    assert "sole owner" in blocked.text.lower()


@pytest.mark.asyncio
async def test_account_delete_after_ownership_transfer(web_client: AsyncClient) -> None:
    _owner_email, owner_password, owner_id, org_id = await _onboard(web_client)
    owner_csrf = web_client.cookies["wp_csrf"]
    member_email = _email("lifecycle-member")
    member_password = "Lifecycle-Member-42!"
    invite = await web_client.post(
        "/api/v1/web/invitations",
        headers={"X-WP-CSRF": owner_csrf},
        json={"email": member_email, "role": "ADMIN"},
    )
    assert invite.status_code == 202
    token = parse_qs(urlparse(invite.json()["invitation_url"]).query)["token"][0]
    reg = await web_client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": "Lifecycle Member",
            "email": member_email,
            "password": member_password,
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    verify_token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    await web_client.post("/api/v1/web/auth/verify", json={"token": verify_token})
    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": member_email, "password": member_password},
    )
    member_csrf = web_client.cookies["wp_csrf"]
    assert (
        await web_client.post(
            "/api/v1/web/invitations/accept",
            headers={"X-WP-CSRF": member_csrf},
            json={"token": token},
        )
    ).status_code == 200
    session = (await web_client.get("/api/v1/web/session")).json()
    new_owner_id = session["user"]["id"]

    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": _owner_email, "password": owner_password},
    )
    owner_csrf = web_client.cookies["wp_csrf"]
    transfer_proof = await _step_up_proof(org_id, owner_id, action="TRANSFER_ROOT_AUTHORITY")
    transfer = await web_client.post(
        "/api/web/organizations/transfer-ownership",
        headers={
            "X-WP-CSRF": owner_csrf,
            "X-Step-Up-Nonce": transfer_proof["nonce"],
            "X-Step-Up-Method": transfer_proof["method"],
            "X-Step-Up-Auth-Time": transfer_proof["auth_time"],
            "X-Step-Up-Token": transfer_proof["token_or_code"],
        },
        json={"new_owner_user_id": new_owner_id, "confirmation": "TRANSFER OWNERSHIP"},
    )
    assert transfer.status_code == 200

    await web_client.post(
        "/api/v1/web/auth/login",
        json={"email": _owner_email, "password": owner_password},
    )
    owner_csrf = web_client.cookies["wp_csrf"]
    delete_proof = await _step_up_proof(org_id, owner_id, action="DESTROY_TENANT")
    deleted = await web_client.request(
        "DELETE",
        "/api/v1/web/account",
        headers={
            "X-WP-CSRF": owner_csrf,
            "X-Step-Up-Nonce": delete_proof["nonce"],
            "X-Step-Up-Method": delete_proof["method"],
            "X-Step-Up-Auth-Time": delete_proof["auth_time"],
            "X-Step-Up-Token": delete_proof["token_or_code"],
        },
        json={"password": owner_password, "confirmation": "DELETE MY ACCOUNT"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "account_disabled"
    assert "wp_session" not in web_client.cookies
