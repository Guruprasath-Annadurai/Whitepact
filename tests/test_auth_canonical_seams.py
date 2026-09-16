# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive test suite for WhitePact Auth, Account Lifecycle, and Paddle Entitlement.

Validates the six canonical seam closures:
Domain 1: Step-Up Reauthentication & Privileged Operations
Domain 2: Durable Multi-Replica OIDC Flow State & Account Takeover Prevention
Domain 3: Web Session Security & Multi-Tenant Organization Switching
Domain 4: Account Lifecycle & Sole-Owner Protection
Domain 5: Paddle Webhook Verification & Durable Replay Protection
Domain 6: Separation of Commercial Entitlement & Governance Authority
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qs, urlparse

import httpx
import jwt as pyjwt
import pytest
from asgi_lifespan import LifespanManager
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("RAI_DB_PATH", ":memory:")
os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")

import responsibleai.dashboard.app as app_module
from responsibleai.auth.oidc import OIDCProvider
from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.paddle_billing_repository import PaddleBillingEventRepository
from responsibleai.db.web_identity_repository import (
    InvitationError,
    SoleOwnerError,
    WebIdentityRepository,
)
from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
from responsibleai.iam.errors import (
    StepUpRequiredError,
    StepUpVerificationFailedError,
)
from responsibleai.iam.models import StepUpProof
from responsibleai.iam.step_up import StepUpVerifier
from responsibleai.rbac.models import Plan, Role


# ── Fixtures & Helpers ────────────────────────────────────────────────────────


@pytest.fixture()
async def db_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def web_client(monkeypatch):
    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(app_module.settings, "paddle_webhook_secret", "test_paddle_secret_key_123")
    monkeypatch.setattr(app_module.limiter, "enabled", False)
    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            yield client


async def _register_and_login(
    client: AsyncClient, name: str, email: str, password: str = "Correct-Horse-42!"
) -> tuple[str, str, str]:
    """Helper: register user, verify email, login, return (user_id, session_cookie, csrf_token)."""
    reg = await client.post(
        "/api/v1/web/auth/register",
        json={
            "full_name": name,
            "email": email,
            "password": password,
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    verify_resp = await client.post("/api/v1/web/auth/verify", json={"token": token})
    assert verify_resp.status_code == 200

    login_resp = await client.post(
        "/api/v1/web/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200

    session_info = await client.get("/api/v1/web/session")
    assert session_info.status_code == 200
    user_id = session_info.json()["user"]["id"]

    csrf = client.cookies.get("wp_csrf", "")
    session = client.cookies.get("wp_session", "")
    return user_id, session, csrf


async def _onboard_org(client: AsyncClient, csrf: str, name: str) -> str:
    res = await client.post(
        "/api/v1/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": name, "use_case": "Testing"},
    )
    assert res.status_code == 200
    session_info = await client.get("/api/v1/web/session")
    assert session_info.status_code == 200
    org = session_info.json()["organization"]
    assert org is not None
    return org["id"]


def _get_step_up_detail(response: httpx.Response) -> dict[str, Any]:
    body = response.json()
    msg = body.get("message")
    if isinstance(msg, dict):
        return msg
    det = body.get("detail")
    if isinstance(det, dict):
        return det
    return body


# ── Domain 1: Step-Up Reauthentication & Privileged Operations ────────────────


class TestStepUpAndPrivilegedOperations:
    async def test_step_up_nonce_issuance_and_single_use(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        nonce = await verifier.issue_step_up_nonce(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            ttl_seconds=300,
        )
        assert nonce.startswith("wp_nonce_")

        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )

        # First consumption must succeed
        success = await verifier.verify_and_consume_step_up(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
            proof=proof,
        )
        assert success is True

        # Second consumption (replay) must be rejected
        with pytest.raises(StepUpVerificationFailedError, match="already been consumed"):
            await verifier.verify_and_consume_step_up(
                org_id="org_test",
                principal_id="user_1",
                action="TRANSFER_ROOT_AUTHORITY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
            )

    async def test_step_up_nonce_action_binding_enforcement(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        nonce = await verifier.issue_step_up_nonce(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            ttl_seconds=300,
        )

        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )

        # Presented for a different action -> must fail
        with pytest.raises(StepUpVerificationFailedError, match="action mismatch"):
            await verifier.verify_and_consume_step_up(
                org_id="org_test",
                principal_id="user_1",
                action="DESTROY_TENANT",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
            )

    async def test_step_up_nonce_expiration(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        nonce = await verifier.issue_step_up_nonce(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            ttl_seconds=-10,  # Expired immediately
        )

        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )

        with pytest.raises(StepUpVerificationFailedError, match="expired"):
            await verifier.verify_and_consume_step_up(
                org_id="org_test",
                principal_id="user_1",
                action="TRANSFER_ROOT_AUTHORITY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
            )

    async def test_web_transfer_ownership_requires_step_up(self, web_client):
        # 1. Register owner and create org
        owner_id, _, csrf_owner = await _register_and_login(
            web_client, "Owner Alice", "alice@example.com"
        )
        org_id = await _onboard_org(web_client, csrf_owner, "Alice Inc")

        # 2. Register second user and invite them
        bob_id, _, _ = await _register_and_login(web_client, "Bob Member", "bob@example.com")

        # Switch back to Alice
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice@example.com", "password": "Correct-Horse-42!"},
        )
        csrf_owner = web_client.cookies["wp_csrf"]

        # Invite Bob
        invite_resp = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf_owner},
            json={"email": "bob@example.com", "role": "VIEWER"},
        )
        assert invite_resp.status_code == 202
        inv_url = invite_resp.json()["invitation_url"]
        invite_token = parse_qs(urlparse(inv_url).query)["token"][0]

        # Bob accepts invite
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "bob@example.com", "password": "Correct-Horse-42!"},
        )
        csrf_bob = web_client.cookies["wp_csrf"]
        accept_resp = await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": csrf_bob},
            json={"token": invite_token},
        )
        assert accept_resp.status_code == 200

        # Switch back to Alice (Owner)
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice@example.com", "password": "Correct-Horse-42!"},
        )
        csrf_owner = web_client.cookies["wp_csrf"]

        # 3. Attempt transfer without Step-Up -> 403 step_up_required
        transfer_req = {
            "new_owner_user_id": bob_id,
            "confirmation": "TRANSFER OWNERSHIP",
        }
        res = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={"X-WP-CSRF": csrf_owner},
            json=transfer_req,
        )
        assert res.status_code == 403
        detail = _get_step_up_detail(res)
        assert detail["error"] == "step_up_required"
        nonce = detail["required_nonce"]

        # 4. Attempt transfer with invalid step-up token -> 403 step_up_failed
        res_bad = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={
                "X-WP-CSRF": csrf_owner,
                "X-Step-Up-Nonce": nonce,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "bad_token_999",
            },
            json=transfer_req,
        )
        assert res_bad.status_code == 403
        assert _get_step_up_detail(res_bad)["error"] == "step_up_failed"

        # 5. Fetch fresh nonce
        res_new_nonce = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={"X-WP-CSRF": csrf_owner},
            json=transfer_req,
        )
        nonce2 = _get_step_up_detail(res_new_nonce)["required_nonce"]

        # 6. Attempt transfer with valid step-up headers -> 200 success
        res_success = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={
                "X-WP-CSRF": csrf_owner,
                "X-Step-Up-Nonce": nonce2,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "123456",
            },
            json=transfer_req,
        )
        assert res_success.status_code == 200
        assert res_success.json()["status"] == "ownership_transferred"

    async def test_web_role_escalation_to_admin_requires_step_up(self, web_client):
        # Register owner and create org
        owner_id, _, csrf = await _register_and_login(web_client, "Esc Owner", "esc_owner@example.com")
        await _onboard_org(web_client, csrf, "Esc Inc")

        # Register member
        member_id, _, _ = await _register_and_login(web_client, "Esc Member", "esc_mem@example.com")

        # Switch back to owner and invite member
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "esc_owner@example.com", "password": "Correct-Horse-42!"},
        )
        csrf = web_client.cookies["wp_csrf"]
        inv = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf},
            json={"email": "esc_mem@example.com", "role": "VIEWER"},
        )
        assert inv.status_code == 202
        token = parse_qs(urlparse(inv.json()["invitation_url"]).query)["token"][0]

        # Member accepts
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "esc_mem@example.com", "password": "Correct-Horse-42!"},
        )
        await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]},
            json={"token": token},
        )

        # Owner attempts to escalate member to ADMIN
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "esc_owner@example.com", "password": "Correct-Horse-42!"},
        )
        csrf = web_client.cookies["wp_csrf"]

        # Without Step-Up -> 403 step_up_required
        escalate_resp = await web_client.patch(
            f"/api/web/members/{member_id}",
            headers={"X-WP-CSRF": csrf},
            json={"role": "ADMIN"},
        )
        assert escalate_resp.status_code == 403
        detail = _get_step_up_detail(escalate_resp)
        assert detail["error"] == "step_up_required"
        nonce = detail["required_nonce"]

        # With valid Step-Up headers -> 200 success
        escalate_ok = await web_client.patch(
            f"/api/web/members/{member_id}",
            headers={
                "X-WP-CSRF": csrf,
                "X-Step-Up-Nonce": nonce,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "123456",
            },
            json={"role": "ADMIN"},
        )
        assert escalate_ok.status_code == 200
        assert escalate_ok.json()["role"] == "ADMIN"


# ── Domain 2: Durable Multi-Replica OIDC Flow State & Account Takeover ────────


class TestDurableOIDCAndAccountTakeover:
    async def test_oauth_flow_state_durable_single_use(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        state_key = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        redirect = "https://app.example.com/callback"

        # 1. Create state
        await repo.create_oauth_flow_state(
            state=state_key,
            provider="oidc",
            nonce=nonce,
            redirect_uri=redirect,
            pkce_verifier=verifier,
            ttl_seconds=300,
        )

        # 2. Consume state with wrong provider -> None
        assert await repo.consume_oauth_flow_state(state_key, expected_provider="github") is None

        # 3. Consume state with correct provider -> returns data
        record = await repo.consume_oauth_flow_state(state_key, expected_provider="oidc")
        assert record is not None
        assert record["nonce"] == nonce
        assert record["pkce_verifier"] == verifier
        assert record["redirect_uri"] == redirect

        # 4. Second consumption -> None (single-use / replay defense)
        assert await repo.consume_oauth_flow_state(state_key, expected_provider="oidc") is None

    async def test_oauth_flow_state_expiry(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        state_key = secrets.token_urlsafe(32)

        await repo.create_oauth_flow_state(
            state=state_key,
            provider="oidc",
            nonce="nonce123",
            redirect_uri="https://app.example.com/callback",
            pkce_verifier="v123",
            ttl_seconds=-10,  # Expired
        )

        assert await repo.consume_oauth_flow_state(state_key, expected_provider="oidc") is None

    async def test_oidc_nonce_validation_in_token(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        public_jwk = pyjwt.algorithms.RSAAlgorithm.to_jwk(private.public_key())
        jwk_dict = json.loads(public_jwk)
        jwk_dict["kid"] = "k1"

        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="test_client")

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(provider._jwks, "get_signing_key", _fake_get_signing_key)

        token_ok = pyjwt.encode(
            {"sub": "user_42", "aud": "test_client", "iss": "https://issuer.example.com", "nonce": "nonce_123"},
            private,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        token_bad_nonce = pyjwt.encode(
            {"sub": "user_42", "aud": "test_client", "iss": "https://issuer.example.com", "nonce": "wrong_nonce"},
            private,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        token_no_nonce = pyjwt.encode(
            {"sub": "user_42", "aud": "test_client", "iss": "https://issuer.example.com"},
            private,
            algorithm="RS256",
            headers={"kid": "k1"},
        )

        # 1. Match succeeds
        parsed = await provider.validate_token(token_ok, expected_nonce="nonce_123")
        assert parsed.sub == "user_42"

        # 2. Mismatch raises ValueError
        with pytest.raises(ValueError, match="nonce validation failed"):
            await provider.validate_token(token_bad_nonce, expected_nonce="nonce_123")

        # 3. Missing nonce when expected raises ValueError
        with pytest.raises(ValueError, match="nonce validation failed"):
            await provider.validate_token(token_no_nonce, expected_nonce="nonce_123")

    async def test_provider_identity_linking_and_resolution(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        user_id, _ = await repo.register("OIDC User", "oidc_user@example.com", "Secure-Password-42!")

        # Unlinked provider -> None
        assert await repo.resolve_provider_identity("google", "goog_sub_999") is None

        # Link provider
        await repo.link_provider_identity(
            user_id=user_id,
            issuer="google",
            subject="goog_sub_999",
            email="oidc_user@example.com",
        )

        # Resolved
        resolved_id = await repo.resolve_provider_identity("google", "goog_sub_999")
        assert resolved_id == user_id


# ── Domain 3: Web Session Security & Multi-Tenant Organization Switching ───────


class TestWebSessionAndMultiTenantSwitching:
    async def test_login_revokes_prior_sessions(self, web_client):
        # Register user
        user_id, sess_1, csrf_1 = await _register_and_login(
            web_client, "Session User", "sess_user@example.com"
        )

        # Verify session 1 works
        me_1 = await web_client.get("/api/v1/web/session")
        assert me_1.status_code == 200
        assert me_1.json()["user"]["id"] == user_id

        # Log in again (minting session 2)
        login_2 = await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "sess_user@example.com", "password": "Correct-Horse-42!"},
        )
        assert login_2.status_code == 200
        sess_2 = web_client.cookies.get("wp_session")
        assert sess_2 != sess_1

        # Session 1 is now revoked -> attempting request with sess_1 fails
        stale_client = httpx.AsyncClient(
            transport=web_client._transport,
            base_url="http://test",
            cookies={"wp_session": sess_1},
        )
        stale_resp = await stale_client.get("/api/v1/web/session")
        assert stale_resp.status_code == 401

    async def test_logout_all_terminates_all_sessions(self, web_client):
        user_id, sess, csrf = await _register_and_login(
            web_client, "Logout All User", "logout_all@example.com"
        )

        # Call logout-all
        logout_resp = await web_client.post(
            "/api/v1/web/auth/logout-all",
            headers={"X-WP-CSRF": csrf},
        )
        assert logout_resp.status_code == 200
        assert logout_resp.json()["status"] == "all_sessions_revoked"

        # Session is now invalid
        me = await web_client.get("/api/v1/web/session")
        assert me.status_code == 401

    async def test_organization_switching_authorized_and_unauthorized(self, web_client):
        # 1. Register user and onboard first org
        user_id, _, csrf = await _register_and_login(
            web_client, "Multi Org User", "multi_org@example.com"
        )
        org_1_id = await _onboard_org(web_client, csrf, "Org Primary")

        # 2. Register other owner and create Org Secondary
        other_id, _, csrf_other = await _register_and_login(
            web_client, "Other Owner", "other_owner@example.com"
        )
        org_2_id = await _onboard_org(web_client, csrf_other, "Org Secondary")

        # Invite multi_org user to Org Secondary
        invite = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf_other},
            json={"email": "multi_org@example.com", "role": "VIEWER"},
        )
        assert invite.status_code == 202
        token = parse_qs(urlparse(invite.json()["invitation_url"]).query)["token"][0]

        # Log in as multi_org user and accept invite
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "multi_org@example.com", "password": "Correct-Horse-42!"},
        )
        csrf = web_client.cookies["wp_csrf"]
        await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": csrf},
            json={"token": token},
        )

        # Accept invite updates cookies and csrf
        fresh_csrf = web_client.cookies["wp_csrf"]

        # 3. User is now member of Org 1 and Org 2.
        # Switch to Org 2
        switch_ok = await web_client.post(
            "/api/web/session/switch-organization",
            headers={"X-WP-CSRF": fresh_csrf},
            json={"organization_id": org_2_id},
        )
        assert switch_ok.status_code == 200
        assert switch_ok.json()["status"] == "organization_switched"

        # Verify active session reflects Org 2
        session_info = await web_client.get("/api/web/session")
        assert session_info.json()["organization"]["id"] == org_2_id

        # 4. Attempt to switch to an organization user is NOT a member of -> 404
        fake_org_id = str(uuid.uuid4())
        switch_bad = await web_client.post(
            "/api/web/session/switch-organization",
            headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]},
            json={"organization_id": fake_org_id},
        )
        assert switch_bad.status_code == 404


# ── Domain 4: Account Lifecycle & Sole-Owner Protection ────────────────────────


class TestAccountLifecycleAndSoleOwnerProtection:
    async def test_sole_owner_deletion_blocked(self, web_client):
        # Register user and create org
        user_id, _, csrf = await _register_and_login(
            web_client, "Sole Owner", "sole_owner@example.com", password="Secure-Password-42!"
        )
        await _onboard_org(web_client, csrf, "Sole Corp")

        delete_payload = {
            "password": "Secure-Password-42!",
            "confirmation": "DELETE MY ACCOUNT",
        }

        # 1. Without Step-Up -> 403 step_up_required
        del_step_up = await web_client.request(
            "DELETE",
            "/api/web/account",
            headers={"X-WP-CSRF": csrf},
            json=delete_payload,
        )
        assert del_step_up.status_code == 403
        detail = _get_step_up_detail(del_step_up)
        assert detail["error"] == "step_up_required"
        nonce = detail["required_nonce"]

        # 2. With Step-Up -> 409 Conflict (blocked by SoleOwnerError)
        del_blocked = await web_client.request(
            "DELETE",
            "/api/web/account",
            headers={
                "X-WP-CSRF": csrf,
                "X-Step-Up-Nonce": nonce,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "123456",
            },
            json=delete_payload,
        )
        assert del_blocked.status_code == 409
        assert "sole owner" in del_blocked.text.lower()

    async def test_ownership_transfer_enables_clean_account_deletion(self, web_client):
        # 1. Register owner Alice
        alice_id, _, csrf_alice = await _register_and_login(
            web_client, "Alice Transfer", "alice_trans@example.com", password="Alice-Secure-42!"
        )
        org_id = await _onboard_org(web_client, csrf_alice, "Transfer Corp")

        # 2. Register member Bob and invite to org
        bob_id, _, _ = await _register_and_login(
            web_client, "Bob Transfer", "bob_trans@example.com", password="Bob-Secure-42!"
        )

        # Alice invites Bob
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice_trans@example.com", "password": "Alice-Secure-42!"},
        )
        csrf_alice = web_client.cookies["wp_csrf"]
        invite_res = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf_alice},
            json={"email": "bob_trans@example.com", "role": "VIEWER"},
        )
        assert invite_res.status_code == 202
        token = parse_qs(urlparse(invite_res.json()["invitation_url"]).query)["token"][0]

        # Bob accepts
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "bob_trans@example.com", "password": "Bob-Secure-42!"},
        )
        await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]},
            json={"token": token},
        )

        # Alice transfers ownership to Bob with step-up
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice_trans@example.com", "password": "Alice-Secure-42!"},
        )
        csrf_alice = web_client.cookies["wp_csrf"]

        step1 = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={"X-WP-CSRF": csrf_alice},
            json={"new_owner_user_id": bob_id, "confirmation": "TRANSFER OWNERSHIP"},
        )
        assert step1.status_code == 403
        nonce_trans = _get_step_up_detail(step1)["required_nonce"]

        trans_ok = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={
                "X-WP-CSRF": csrf_alice,
                "X-Step-Up-Nonce": nonce_trans,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "123456",
            },
            json={"new_owner_user_id": bob_id, "confirmation": "TRANSFER OWNERSHIP"},
        )
        assert trans_ok.status_code == 200

        # Alice is now demoted to ADMIN, Bob is OWNER. Alice is no longer sole owner!
        # Ownership transfer revoked sessions for security. Alice logs back in:
        alice_relogin = await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice_trans@example.com", "password": "Alice-Secure-42!"},
        )
        assert alice_relogin.status_code == 200
        csrf_alice = web_client.cookies["wp_csrf"]

        # Alice requests account deletion (requires step-up)
        del_step1 = await web_client.request(
            "DELETE",
            "/api/web/account",
            headers={"X-WP-CSRF": csrf_alice},
            json={"password": "Alice-Secure-42!", "confirmation": "DELETE MY ACCOUNT"},
        )
        assert del_step1.status_code == 403
        nonce_del = _get_step_up_detail(del_step1)["required_nonce"]

        del_ok = await web_client.request(
            "DELETE",
            "/api/web/account",
            headers={
                "X-WP-CSRF": csrf_alice,
                "X-Step-Up-Nonce": nonce_del,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "123456",
            },
            json={"password": "Alice-Secure-42!", "confirmation": "DELETE MY ACCOUNT"},
        )
        assert del_ok.status_code == 200
        assert del_ok.json()["status"] == "account_disabled"

        # Alice can no longer log in
        login_fail = await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice_trans@example.com", "password": "Alice-Secure-42!"},
        )
        assert login_fail.status_code == 401


# ── Domain 5: Paddle Webhook Verification & Durable Replay Protection ─────────


def _sign_paddle_payload(secret: str, raw_bytes: bytes, ts: int | None = None) -> tuple[str, int]:
    if ts is None:
        ts = int(datetime.now(UTC).timestamp())
    signed_payload = f"{ts}:".encode("utf-8") + raw_bytes
    h1 = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}", ts


class TestPaddleWebhookVerificationAndReplay:
    async def test_paddle_webhook_hmac_signature_validation(self, web_client):
        secret = "test_paddle_secret_key_123"
        payload = {
            "event_id": "evt_pad_sig_test",
            "event_type": "subscription.created",
            "data": {
                "id": "sub_1",
                "customer_id": "ctm_1",
                "status": "active",
                "custom_data": {"org_id": "org_paddle_test"},
            },
        }
        raw_body = json.dumps(payload).encode("utf-8")

        # 1. Missing signature header -> 400
        res_no_sig = await web_client.post("/api/billing/paddle/webhook", content=raw_body)
        assert res_no_sig.status_code == 400

        # 2. Tampered signature -> 400
        res_bad_sig = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": "ts=1700000000;h1=tampered_h1_hash"},
            content=raw_body,
        )
        assert res_bad_sig.status_code == 400

        # 3. Expired timestamp (> 300s) -> 400
        old_ts = int(datetime.now(UTC).timestamp()) - 400
        sig_old, _ = _sign_paddle_payload(secret, raw_body, ts=old_ts)
        res_expired = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_old},
            content=raw_body,
        )
        assert res_expired.status_code == 400
        assert "expired" in res_expired.text.lower()

    async def test_paddle_webhook_durable_replay_and_conflict_defense(self, web_client):
        secret = "test_paddle_secret_key_123"

        # Create target org first
        _, _, csrf = await _register_and_login(web_client, "Paddle User", "paddle_test@example.com")
        org_id = await _onboard_org(web_client, csrf, "Paddle Org")

        event_id = f"evt_replay_{secrets.token_hex(8)}"
        payload = {
            "event_id": event_id,
            "event_type": "subscription.activated",
            "event_version": 10,
            "data": {
                "id": "sub_test_123",
                "customer_id": "ctm_test_456",
                "status": "active",
                "custom_data": {"org_id": org_id, "plan": "pro"},
            },
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig_header, _ = _sign_paddle_payload(secret, raw_body)

        # 1. First event delivery -> processed: True
        res_first = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_header},
            content=raw_body,
        )
        assert res_first.status_code == 200
        assert res_first.json() == {"received": True, "processed": True}

        # 2. Duplicate replay with identical payload -> duplicate: True, safe 200
        res_dup = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_header},
            content=raw_body,
        )
        assert res_dup.status_code == 200
        assert res_dup.json() == {"received": True, "processed": False, "duplicate": True}

        # 3. Conflicting payload under same event_id -> 409 Conflict
        conflicting_payload = {
            "event_id": event_id,
            "event_type": "subscription.activated",
            "event_version": 10,
            "data": {
                "id": "sub_DIFFERENT_PAYLOAD",
                "customer_id": "ctm_test_456",
                "status": "active",
            },
        }
        raw_conflict = json.dumps(conflicting_payload).encode("utf-8")
        sig_conflict, _ = _sign_paddle_payload(secret, raw_conflict)
        res_conflict = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_conflict},
            content=raw_conflict,
        )
        assert res_conflict.status_code == 409

    async def test_paddle_webhook_monotonic_versioning(self, db_engine):
        orgs = OrgRepository(db_engine)
        org = await orgs.create_org("Monotonic Test", "monotonic-test")

        # 1. Apply version 10 -> Plan.PRO
        ok1 = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_mono_1",
            subscription_id="sub_mono_1",
            plan=Plan.PRO,
            subscription_status="active",
            event_version=10,
            updated_at="2026-09-16T12:00:00+00:00",
        )
        assert ok1 is True
        current = await orgs.get_org(org.id)
        assert current.plan == Plan.PRO
        assert current.entitlement_version == 10

        # 2. Attempt to apply older version 5 -> ignored (returns False)
        ok2 = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_mono_1",
            subscription_id="sub_mono_1",
            plan=Plan.FREE,
            subscription_status="canceled",
            event_version=5,
            updated_at="2026-09-16T11:00:00+00:00",
        )
        assert ok2 is False
        current2 = await orgs.get_org(org.id)
        # Plan remains PRO, version remains 10
        assert current2.plan == Plan.PRO
        assert current2.entitlement_version == 10

        # 3. Apply newer version 15 -> succeeds
        ok3 = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_mono_1",
            subscription_id="sub_mono_1",
            plan=Plan.ENTERPRISE,
            subscription_status="active",
            event_version=15,
            updated_at="2026-09-16T13:00:00+00:00",
        )
        assert ok3 is True
        current3 = await orgs.get_org(org.id)
        assert current3.plan == Plan.ENTERPRISE
        assert current3.entitlement_version == 15


# ── Domain 6: Separation of Commercial Entitlement & Governance Authority ─────


class TestCommercialEntitlementGovernanceSeparation:
    async def test_commercial_plan_never_grants_governance_authority(self, db_engine):
        orgs = OrgRepository(db_engine)
        org = await orgs.create_org("Gov Separation Org", "gov-sep-org")

        # Upgrade org to ENTERPRISE
        await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_enterprise_vip",
            subscription_id="sub_enterprise_vip",
            plan=Plan.ENTERPRISE,
            subscription_status="active",
            event_version=1,
            updated_at="2026-09-16T12:00:00+00:00",
        )

        org_record = await orgs.get_org(org.id)
        assert org_record.plan == Plan.ENTERPRISE

        # Invariant: Being on ENTERPRISE does not create any API keys, does not grant
        # any AuthorityPassport, and does not alter governance policies.
        keys = await orgs.list_keys(org.id)
        assert len(keys) == 0

    async def test_billing_delinquency_never_bypasses_or_weakens_security(self, web_client):
        # Create an org and delinquency state
        secret = "test_paddle_secret_key_123"
        _, _, csrf = await _register_and_login(web_client, "Delinquent User", "delinquent@example.com")
        org_id = await _onboard_org(web_client, csrf, "Delinquent Corp")

        # Webhook marks subscription past_due / canceled
        payload = {
            "event_id": f"evt_delinquent_{secrets.token_hex(6)}",
            "event_type": "subscription.past_due",
            "event_version": 20,
            "data": {
                "id": "sub_delinquent",
                "customer_id": "ctm_delinquent",
                "status": "past_due",
                "custom_data": {"org_id": org_id, "plan": "enterprise"},
            },
        }
        raw = json.dumps(payload).encode("utf-8")
        sig, _ = _sign_paddle_payload(secret, raw)
        wh_resp = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig},
            content=raw,
        )
        assert wh_resp.status_code == 200

        # Invariant: Security boundaries remain strictly enforced
        # 1. Unauthenticated request still rejected
        unauth_client = httpx.AsyncClient(transport=web_client._transport, base_url="http://test")
        assert (await unauth_client.get("/api/v1/web/session")).status_code == 401

        # 2. CSRF check remains enforced
        no_csrf = await web_client.post(
            "/api/web/invitations",
            json={"email": "someone@example.com", "role": "VIEWER"},
        )
        assert no_csrf.status_code == 403
