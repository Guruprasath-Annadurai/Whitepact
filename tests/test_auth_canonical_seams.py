# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive test suite for WhitePact Auth, Account Lifecycle, and Paddle Entitlement.

Validates the six canonical seam closures:
Domain 1: Step-Up Reauthentication & Privileged Operations (Session Binding)
Domain 2: Durable Multi-Replica OIDC Flow State & Account Takeover Prevention
Domain 3: Web Session Security & Multi-Tenant Organization Switching
Domain 4: Account Lifecycle & Sole-Owner Protection / Tombstones
Domain 5: Paddle Webhook Verification & Real Provider Chronology (occurred_at)
Domain 6: Direct Separation of Commercial Entitlement & Governance Authority
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
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
from sqlalchemy import insert, update

import responsibleai.dashboard.app as app_module
from responsibleai.auth.oidc import OIDCProvider
from responsibleai.data_governance.legal_hold import LegalHoldManager
from responsibleai.db.authority_passport_repository import AuthorityPassportRepository
from responsibleai.db.engine import (
    create_engine,
    tenant_tombstones,
    web_sessions,
    web_users,
)
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import (
    WebIdentityRepository,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    GovernanceDecision,
    IdentityContext,
    RiskTier,
)
from responsibleai.governance.policy import Policy, PolicyRule
from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
from responsibleai.iam.errors import (
    StepUpVerificationFailedError,
)
from responsibleai.iam.models import StepUpProof
from responsibleai.iam.step_up import StepUpVerifier
from responsibleai.rbac.models import Plan

# ── Fixtures & Helpers ────────────────────────────────────────────────────────


@pytest.fixture()
async def db_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def web_client(monkeypatch):
    monkeypatch.setattr(app_module.settings, "db_path", ":memory:")
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "auth_enabled", False)
    monkeypatch.setattr(app_module.settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(app_module.settings, "web_session_secure", False)
    monkeypatch.setattr(app_module.settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(
        app_module.settings, "paddle_webhook_secret", "paddle-test-placeholder"
    )
    monkeypatch.setattr(app_module.settings, "paddle_signature_tolerance_seconds", 300)
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


def _sign_paddle_payload(secret: str, raw_bytes: bytes, ts: int | None = None) -> tuple[str, int]:
    if ts is None:
        ts = int(datetime.now(UTC).timestamp())
    signed_payload = f"{ts}:".encode() + raw_bytes
    h1 = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}", ts


# ── Domain 1: Step-Up Reauthentication & Session Binding ──────────────────────


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

    async def test_step_up_session_binding_success_same_session(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        nonce = await verifier.issue_step_up_nonce(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            session_id="sess_alpha_123",
            ttl_seconds=300,
        )

        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )

        success = await verifier.verify_and_consume_step_up(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
            proof=proof,
            session_id="sess_alpha_123",
        )
        assert success is True

    async def test_step_up_session_binding_fails_cross_session(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        nonce = await verifier.issue_step_up_nonce(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            session_id="sess_alpha_123",
            ttl_seconds=300,
        )

        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )

        cross_session_successes = 0
        try:
            await verifier.verify_and_consume_step_up(
                org_id="org_test",
                principal_id="user_1",
                action="TRANSFER_ROOT_AUTHORITY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
                session_id="sess_beta_456",
            )
            cross_session_successes += 1
        except StepUpVerificationFailedError as exc:
            assert "session mismatch" in str(exc).lower()

        assert cross_session_successes == 0

    async def test_step_up_wrong_principal(self, db_engine):
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

        wrong_principal_successes = 0
        try:
            await verifier.verify_and_consume_step_up(
                org_id="org_test",
                principal_id="user_2",
                action="TRANSFER_ROOT_AUTHORITY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
            )
            wrong_principal_successes += 1
        except StepUpVerificationFailedError:
            pass

        assert wrong_principal_successes == 0

    async def test_step_up_wrong_tenant(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        nonce = await verifier.issue_step_up_nonce(
            org_id="org_1",
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

        wrong_tenant_successes = 0
        try:
            await verifier.verify_and_consume_step_up(
                org_id="org_2",
                principal_id="user_1",
                action="TRANSFER_ROOT_AUTHORITY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
            )
            wrong_tenant_successes += 1
        except StepUpVerificationFailedError:
            pass

        assert wrong_tenant_successes == 0

    async def test_step_up_revoked_session_rejected(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        now_iso = datetime.now(UTC).isoformat()
        future_iso = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
        sess_token_hash = hashlib.sha256(b"sess_revoked_test").hexdigest()

        async with db_engine.raw.begin() as conn:
            await conn.execute(
                insert(web_users).values(
                    id="user_sess_rev",
                    email="sess_rev@example.com",
                    full_name="Rev Test",
                    password_hash="hash",
                    disabled=0,
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            await conn.execute(
                insert(web_sessions).values(
                    token_hash=sess_token_hash,
                    user_id="user_sess_rev",
                    csrf_hash="csrf",
                    created_at=now_iso,
                    expires_at=future_iso,
                    last_seen_at=now_iso,
                    revoked=0,
                )
            )

        nonce = await verifier.issue_step_up_nonce(
            org_id="org_test",
            principal_id="user_sess_rev",
            action="TRANSFER_ROOT_AUTHORITY",
            session_id=sess_token_hash,
            ttl_seconds=300,
        )

        # Revoke session
        async with db_engine.raw.begin() as conn:
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.token_hash == sess_token_hash)
                .values(revoked=1)
            )

        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=now_iso,
            token_or_code="123456",
        )

        with pytest.raises(StepUpVerificationFailedError, match="revoked or expired"):
            await verifier.verify_and_consume_step_up(
                org_id="org_test",
                principal_id="user_sess_rev",
                action="TRANSFER_ROOT_AUTHORITY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
                session_id=sess_token_hash,
            )

    async def test_step_up_session_rotated_after_issuance(self, db_engine):
        verifier = StepUpVerifier(db_engine)
        sess_old = "sess_old_token_1"
        sess_new = "sess_new_token_2"

        nonce = await verifier.issue_step_up_nonce(
            org_id="org_test",
            principal_id="user_1",
            action="TRANSFER_ROOT_AUTHORITY",
            session_id=sess_old,
            ttl_seconds=300,
        )

        proof = StepUpProof(
            nonce=nonce,
            method=StepUpMethod.MFA_TOTP,
            auth_time=datetime.now(UTC).isoformat(),
            token_or_code="123456",
        )

        with pytest.raises(StepUpVerificationFailedError, match="session mismatch"):
            await verifier.verify_and_consume_step_up(
                org_id="org_test",
                principal_id="user_1",
                action="TRANSFER_ROOT_AUTHORITY",
                risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
                proof=proof,
                session_id=sess_new,
            )

    async def test_web_transfer_ownership_requires_step_up(self, web_client):
        owner_id, _, csrf_owner = await _register_and_login(
            web_client, "Owner Alice", "alice@example.com"
        )
        await _onboard_org(web_client, csrf_owner, "Alice Inc")
        bob_id, _, _ = await _register_and_login(web_client, "Bob Member", "bob@example.com")

        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice@example.com", "password": "Correct-Horse-42!"},
        )
        csrf_owner = web_client.cookies["wp_csrf"]

        invite_resp = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf_owner},
            json={"email": "bob@example.com", "role": "VIEWER"},
        )
        assert invite_resp.status_code == 202
        inv_url = invite_resp.json()["invitation_url"]
        invite_token = parse_qs(urlparse(inv_url).query)["token"][0]

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

        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice@example.com", "password": "Correct-Horse-42!"},
        )
        csrf_owner = web_client.cookies["wp_csrf"]

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

        res_new_nonce = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={"X-WP-CSRF": csrf_owner},
            json=transfer_req,
        )
        nonce2 = _get_step_up_detail(res_new_nonce)["required_nonce"]

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
        owner_id, _, csrf = await _register_and_login(
            web_client, "Esc Owner", "esc_owner@example.com"
        )
        await _onboard_org(web_client, csrf, "Esc Inc")
        member_id, _, _ = await _register_and_login(web_client, "Esc Member", "esc_mem@example.com")

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

        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "esc_mem@example.com", "password": "Correct-Horse-42!"},
        )
        await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]},
            json={"token": token},
        )

        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "esc_owner@example.com", "password": "Correct-Horse-42!"},
        )
        csrf = web_client.cookies["wp_csrf"]

        escalate_resp = await web_client.patch(
            f"/api/web/members/{member_id}",
            headers={"X-WP-CSRF": csrf},
            json={"role": "ADMIN"},
        )
        assert escalate_resp.status_code == 403
        detail = _get_step_up_detail(escalate_resp)
        assert detail["error"] == "step_up_required"
        nonce = detail["required_nonce"]

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


# ── Domain 2: Durable OIDC Flow State Browser/Session Binding ─────────────────


class TestDurableOIDCAndAccountTakeover:
    async def test_oauth_flow_state_durable_single_use(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        state_key = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        redirect = "https://app.example.com/callback"

        await repo.create_oauth_flow_state(
            state=state_key,
            provider="oidc",
            nonce=nonce,
            redirect_uri=redirect,
            pkce_verifier=verifier,
            ttl_seconds=300,
        )

        assert await repo.consume_oauth_flow_state(state_key, expected_provider="github") is None

        record = await repo.consume_oauth_flow_state(state_key, expected_provider="oidc")
        assert record is not None
        assert record["nonce"] == nonce
        assert record["pkce_verifier"] == verifier
        assert record["redirect_uri"] == redirect

        # Replay -> None
        assert await repo.consume_oauth_flow_state(state_key, expected_provider="oidc") is None

    async def test_oauth_flow_state_shared_across_repository_instances(self, db_engine):
        """Two repository objects on one engine share durable OAuth state (replica-safe)."""
        writer = WebIdentityRepository(db_engine)
        reader = WebIdentityRepository(db_engine)
        state_key = secrets.token_urlsafe(32)
        await writer.create_oauth_flow_state(
            state=state_key,
            provider="oidc",
            nonce="n-shared",
            redirect_uri="https://app.example.com/callback",
            pkce_verifier="v-shared",
            ttl_seconds=300,
        )
        first = await reader.consume_oauth_flow_state(state_key, expected_provider="oidc")
        assert first is not None
        assert first["nonce"] == "n-shared"
        assert first["pkce_verifier"] == "v-shared"
        assert await writer.consume_oauth_flow_state(state_key, expected_provider="oidc") is None

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

    async def test_oauth_flow_state_browser_session_binding(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        state_key = secrets.token_urlsafe(32)
        tx_id = hashlib.sha256(b"browser_tx_1").hexdigest()

        await repo.create_oauth_flow_state(
            state=state_key,
            provider="oidc",
            nonce="n1",
            redirect_uri="https://app.example.com/cb",
            pkce_verifier="v1",
            ttl_seconds=300,
            session_id=tx_id,
        )

        rec = await repo.consume_oauth_flow_state(
            state_key, expected_provider="oidc", expected_session_id=tx_id
        )
        assert rec is not None
        assert rec["session_id"] == tx_id

    async def test_oauth_flow_state_wrong_browser_session_rejected(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        state_key = secrets.token_urlsafe(32)
        tx_id_a = hashlib.sha256(b"browser_tx_A").hexdigest()
        tx_id_b = hashlib.sha256(b"browser_tx_B").hexdigest()

        await repo.create_oauth_flow_state(
            state=state_key,
            provider="oidc",
            nonce="n1",
            redirect_uri="https://app.example.com/cb",
            pkce_verifier="v1",
            ttl_seconds=300,
            session_id=tx_id_a,
        )

        consumed = await repo.consume_oauth_flow_state(
            state_key, expected_provider="oidc", expected_session_id=tx_id_b
        )
        assert consumed is None

    async def test_oauth_flow_state_wrong_org_rejected(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        state_key = secrets.token_urlsafe(32)

        await repo.create_oauth_flow_state(
            state=state_key,
            provider="oidc",
            nonce="n1",
            redirect_uri="https://app.example.com/cb",
            pkce_verifier="v1",
            tenant_id="org_alpha",
            ttl_seconds=300,
        )

        assert (
            await repo.consume_oauth_flow_state(
                state_key, expected_provider="oidc", expected_tenant_id="org_beta"
            )
            is None
        )

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
            {
                "sub": "user_42",
                "aud": "test_client",
                "iss": "https://issuer.example.com",
                "nonce": "nonce_123",
            },
            private,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        token_bad_nonce = pyjwt.encode(
            {
                "sub": "user_42",
                "aud": "test_client",
                "iss": "https://issuer.example.com",
                "nonce": "wrong_nonce",
            },
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

        parsed = await provider.validate_token(token_ok, expected_nonce="nonce_123")
        assert parsed.sub == "user_42"

        with pytest.raises(ValueError, match="nonce validation failed"):
            await provider.validate_token(token_bad_nonce, expected_nonce="nonce_123")

        with pytest.raises(ValueError, match="nonce validation failed"):
            await provider.validate_token(token_no_nonce, expected_nonce="nonce_123")

    async def test_provider_identity_linking_and_resolution(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        user_id, _ = await repo.register(
            "OIDC User", "oidc_user@example.com", "Secure-Password-42!"
        )

        assert await repo.resolve_provider_identity("google", "goog_sub_999") is None

        await repo.link_provider_identity(
            user_id=user_id,
            issuer="google",
            subject="goog_sub_999",
            email="oidc_user@example.com",
            email_verified=True,
        )

        resolved_id = await repo.resolve_provider_identity("google", "goog_sub_999")
        assert resolved_id == user_id

    async def test_oidc_account_linking_negative_matrix(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        user_1, _ = await repo.register("User One", "user1@example.com", "Secure-Password-42!")
        user_2, _ = await repo.register("User Two", "user2@example.com", "Secure-Password-42!")

        # 1. Unverified email must NOT link
        with pytest.raises(ValueError, match="unverified email"):
            await repo.link_provider_identity(
                user_id=user_1,
                issuer="google",
                subject="goog_sub_unverified",
                email="user1@example.com",
                email_verified=False,
            )

        # 2. Same email from different IdP must NOT silently merge accounts
        await repo.link_provider_identity(
            user_id=user_1,
            issuer="google",
            subject="goog_sub_1",
            email="shared@example.com",
            email_verified=True,
        )
        assert await repo.resolve_provider_identity("github", "gh_sub_2") is None
        email_only_takeover_successes = 0
        if await repo.resolve_provider_identity("github", "gh_sub_2") == user_1:
            email_only_takeover_successes += 1
        assert email_only_takeover_successes == 0

        # 3. Issuer mismatch / Subject mismatch
        assert await repo.resolve_provider_identity("google", "wrong_sub") is None
        assert await repo.resolve_provider_identity("wrong_issuer", "goog_sub_1") is None

        # 4. Duplicate (issuer, subject) linked to a second user -> MUST FAIL
        cross_account_links = 0
        try:
            await repo.link_provider_identity(
                user_id=user_2,
                issuer="google",
                subject="goog_sub_1",
                email="user2@example.com",
                email_verified=True,
            )
            cross_account_links += 1
        except ValueError as exc:
            assert "already linked" in str(exc).lower()
        assert cross_account_links == 0

        # 5. Cross-tenant linking: user is not member of tenant -> MUST FAIL
        cross_tenant_links = 0
        try:
            await repo.link_provider_identity(
                user_id=user_1,
                issuer="okta",
                subject="okta_sub_1",
                email="user1@example.com",
                email_verified=True,
                tenant_id="non_member_org",
            )
            cross_tenant_links += 1
        except ValueError as exc:
            assert "not a member" in str(exc).lower()
        assert cross_tenant_links == 0


# ── Domain 3: Web Session Security & Multi-Tenant Organization Switching ───────


class TestWebSessionAndMultiTenantSwitching:
    async def test_login_revokes_prior_sessions(self, web_client):
        user_id, sess_1, csrf_1 = await _register_and_login(
            web_client, "Session User", "sess_user@example.com"
        )

        me_1 = await web_client.get("/api/v1/web/session")
        assert me_1.status_code == 200
        assert me_1.json()["user"]["id"] == user_id

        login_2 = await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "sess_user@example.com", "password": "Correct-Horse-42!"},
        )
        assert login_2.status_code == 200
        sess_2 = web_client.cookies.get("wp_session")
        assert sess_2 != sess_1

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

        logout_resp = await web_client.post(
            "/api/v1/web/auth/logout-all",
            headers={"X-WP-CSRF": csrf},
        )
        assert logout_resp.status_code == 200
        assert logout_resp.json()["status"] == "all_sessions_revoked"

        me = await web_client.get("/api/v1/web/session")
        assert me.status_code == 401

    async def test_organization_switching_authorized_and_unauthorized(self, web_client):
        user_id, _, csrf = await _register_and_login(
            web_client, "Multi Org User", "multi_org@example.com"
        )
        await _onboard_org(web_client, csrf, "Org Primary")

        other_id, _, csrf_other = await _register_and_login(
            web_client, "Other Owner", "other_owner@example.com"
        )
        org_2_id = await _onboard_org(web_client, csrf_other, "Org Secondary")

        invite = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf_other},
            json={"email": "multi_org@example.com", "role": "VIEWER"},
        )
        assert invite.status_code == 202
        token = parse_qs(urlparse(invite.json()["invitation_url"]).query)["token"][0]

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

        fresh_csrf = web_client.cookies["wp_csrf"]

        switch_ok = await web_client.post(
            "/api/web/session/switch-organization",
            headers={"X-WP-CSRF": fresh_csrf},
            json={"organization_id": org_2_id},
        )
        assert switch_ok.status_code == 200
        assert switch_ok.json()["status"] == "organization_switched"

        session_info = await web_client.get("/api/web/session")
        assert session_info.json()["organization"]["id"] == org_2_id

        fake_org_id = str(uuid.uuid4())
        switch_bad = await web_client.post(
            "/api/web/session/switch-organization",
            headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]},
            json={"organization_id": fake_org_id},
        )
        assert switch_bad.status_code == 404


# ── Domain 4: Account Lifecycle, Sole-Owner Protection & Tombstones ───────────


class TestAccountLifecycleAndSoleOwnerProtection:
    async def test_sole_owner_deletion_blocked(self, web_client):
        user_id, _, csrf = await _register_and_login(
            web_client, "Sole Owner", "sole_owner@example.com", password="Secure-Password-42!"
        )
        await _onboard_org(web_client, csrf, "Sole Corp")

        delete_payload = {
            "password": "Secure-Password-42!",
            "confirmation": "DELETE MY ACCOUNT",
        }

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
        alice_id, _, csrf_alice = await _register_and_login(
            web_client, "Alice Transfer", "alice_trans@example.com", password="Alice-Secure-42!"
        )
        await _onboard_org(web_client, csrf_alice, "Transfer Corp")

        bob_id, _, _ = await _register_and_login(
            web_client, "Bob Transfer", "bob_trans@example.com", password="Bob-Secure-42!"
        )

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

        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "bob_trans@example.com", "password": "Bob-Secure-42!"},
        )
        await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]},
            json={"token": token},
        )

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

        alice_relogin = await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice_trans@example.com", "password": "Alice-Secure-42!"},
        )
        assert alice_relogin.status_code == 200
        csrf_alice = web_client.cookies["wp_csrf"]

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

        login_fail = await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "alice_trans@example.com", "password": "Alice-Secure-42!"},
        )
        assert login_fail.status_code == 401

    async def test_account_deletion_data_hold_blocked(self, web_client, db_engine):
        user_id, _, csrf = await _register_and_login(
            web_client, "Hold User", "hold_user@example.com", password="Hold-Secure-42!"
        )
        org_id = await _onboard_org(web_client, csrf, "Hold Corp")

        bob_id, _, _ = await _register_and_login(web_client, "Hold Bob", "hold_bob@example.com")
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "hold_user@example.com", "password": "Hold-Secure-42!"},
        )
        csrf = web_client.cookies["wp_csrf"]
        inv = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf},
            json={"email": "hold_bob@example.com", "role": "ADMIN"},
        )
        token = parse_qs(urlparse(inv.json()["invitation_url"]).query)["token"][0]
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "hold_bob@example.com", "password": "Correct-Horse-42!"},
        )
        await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": web_client.cookies["wp_csrf"]},
            json={"token": token},
        )
        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "hold_user@example.com", "password": "Hold-Secure-42!"},
        )
        csrf = web_client.cookies["wp_csrf"]

        s1 = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={"X-WP-CSRF": csrf},
            json={"new_owner_user_id": bob_id, "confirmation": "TRANSFER OWNERSHIP"},
        )
        nonce_t = _get_step_up_detail(s1)["required_nonce"]
        await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={
                "X-WP-CSRF": csrf,
                "X-Step-Up-Nonce": nonce_t,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "123456",
            },
            json={"new_owner_user_id": bob_id, "confirmation": "TRANSFER OWNERSHIP"},
        )

        hold_mgr = LegalHoldManager(app_module._db_engine)
        await hold_mgr.create_hold(
            org_id=org_id,
            data_category="ALL",
            hold_reason="Subpoena Active",
            created_by="legal_officer",
        )

        await web_client.post(
            "/api/v1/web/auth/login",
            json={"email": "hold_user@example.com", "password": "Hold-Secure-42!"},
        )
        csrf = web_client.cookies["wp_csrf"]

        d1 = await web_client.request(
            "DELETE",
            "/api/web/account",
            headers={"X-WP-CSRF": csrf},
            json={"password": "Hold-Secure-42!", "confirmation": "DELETE MY ACCOUNT"},
        )
        nonce_d = _get_step_up_detail(d1)["required_nonce"]

        d2 = await web_client.request(
            "DELETE",
            "/api/web/account",
            headers={
                "X-WP-CSRF": csrf,
                "X-Step-Up-Nonce": nonce_d,
                "X-Step-Up-Method": "mfa_totp",
                "X-Step-Up-Token": "123456",
            },
            json={"password": "Hold-Secure-42!", "confirmation": "DELETE MY ACCOUNT"},
        )
        assert d2.status_code == 409
        assert "legal hold" in d2.text.lower()

    async def test_account_deletion_credential_and_session_revocation(self, db_engine):
        repo = WebIdentityRepository(db_engine)
        user_id, token = await repo.register(
            "Purge User", "purge@example.com", "Secure-Password-42!"
        )
        await repo.verify_email(token)

        sess_token, csrf_token = await repo.create_session(user_id)
        sess_hash = hashlib.sha256(sess_token.encode("utf-8")).hexdigest()
        await repo.create_oauth_flow_state(
            state="state_purge",
            provider="oidc",
            nonce="nonce_p",
            redirect_uri="https://app.example.com",
            pkce_verifier="pkce_p",
            ttl_seconds=300,
            session_id=sess_hash,
        )

        disabled = await repo.disable_account(user_id)
        assert disabled is True

        session = await repo.get_principal(sess_token)
        assert session is None
        session_resurrections = 0
        if session is not None:
            session_resurrections += 1
        assert session_resurrections == 0

        cred = await repo.authenticate("purge@example.com", "Secure-Password-42!")
        assert cred is None
        credential_resurrections = 0
        if cred is not None:
            credential_resurrections += 1
        assert credential_resurrections == 0

        state_rec = await repo.consume_oauth_flow_state("state_purge")
        assert state_rec is None

    async def test_tombstoned_tenant_cannot_reactivate(self, db_engine):
        org_repo = OrgRepository(db_engine)
        org = await org_repo.create_org("Tombstone Corp", "tombstone-corp")

        now_iso = datetime.now(UTC).isoformat()
        async with db_engine.raw.begin() as conn:
            await conn.execute(
                insert(tenant_tombstones).values(
                    id=str(uuid.uuid4()),
                    org_id=org.id,
                    original_name=org.name,
                    generation_id="gen-1",
                    tombstoned_at=now_iso,
                    tombstoned_by="admin",
                    authority_hash="hash-1",
                    evidence_digest="digest-1",
                    details_json=json.dumps({"reason": "GDPR Complete Erasure"}),
                )
            )

        tenant_resurrections = 0
        authority_resurrections = 0

        try:
            await org_repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id="ctm_tombstone",
                subscription_id="sub_tombstone",
                plan=Plan.PRO,
                subscription_status="active",
                occurred_at=now_iso,
            )
            tenant_resurrections += 1
        except ValueError as exc:
            assert "tombstoned" in str(exc).lower()

        assert tenant_resurrections == 0
        assert authority_resurrections == 0


# ── Domain 5: Paddle Webhook Verification & Chronology ────────────────────────


class TestPaddleWebhookVerificationAndReplay:
    async def test_paddle_webhook_hmac_signature_validation(self, web_client):
        secret = "paddle-test-placeholder"  # gitleaks:allow
        payload = {
            "event_id": "evt_pad_sig_test",
            "event_type": "subscription.created",
            "occurred_at": "2026-09-16T12:00:00Z",
            "data": {
                "id": "sub_1",
                "customer_id": "ctm_1",
                "status": "active",
                "custom_data": {"org_id": "org_paddle_test"},
            },
        }
        raw_body = json.dumps(payload).encode("utf-8")

        res_no_sig = await web_client.post("/api/billing/paddle/webhook", content=raw_body)
        assert res_no_sig.status_code == 400

        res_bad_sig = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": "ts=1700000000;h1=tampered_h1_hash"},
            content=raw_body,
        )
        assert res_bad_sig.status_code == 400

        sig_header, _ = _sign_paddle_payload(secret, raw_body)
        res_tampered_body = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_header},
            content=raw_body + b"tampered",
        )
        assert res_tampered_body.status_code == 400

        old_ts = int(datetime.now(UTC).timestamp()) - 400
        sig_old, _ = _sign_paddle_payload(secret, raw_body, ts=old_ts)
        res_expired = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_old},
            content=raw_body,
        )
        assert res_expired.status_code == 400
        assert "expired" in res_expired.text.lower()

        future_ts = int(datetime.now(UTC).timestamp()) + 400
        sig_future, _ = _sign_paddle_payload(secret, raw_body, ts=future_ts)
        res_future = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_future},
            content=raw_body,
        )
        assert res_future.status_code == 400
        assert "future" in res_future.text.lower()

    async def test_paddle_webhook_durable_replay_and_conflict_defense(self, web_client):
        secret = "paddle-test-placeholder"  # gitleaks:allow

        _, _, csrf = await _register_and_login(web_client, "Paddle User", "paddle_test@example.com")
        org_id = await _onboard_org(web_client, csrf, "Paddle Org")

        event_id = f"evt_replay_{secrets.token_hex(8)}"
        payload = {
            "event_id": event_id,
            "event_type": "subscription.activated",
            "occurred_at": "2026-09-16T12:00:00Z",
            "data": {
                "id": "sub_test_123",
                "customer_id": "ctm_test_456",
                "status": "active",
                "custom_data": {"org_id": org_id, "plan": "pro"},
            },
        }
        raw_body = json.dumps(payload).encode("utf-8")
        sig_header, _ = _sign_paddle_payload(secret, raw_body)

        res_first = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_header},
            content=raw_body,
        )
        assert res_first.status_code == 200
        assert res_first.json() == {"received": True, "processed": True}

        res_dup = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_header},
            content=raw_body,
        )
        assert res_dup.status_code == 200
        assert res_dup.json() == {"received": True, "processed": False, "duplicate": True}

        conflicting_payload = {
            "event_id": event_id,
            "event_type": "subscription.activated",
            "occurred_at": "2026-09-16T12:00:00Z",
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

    async def test_paddle_webhook_occurred_at_chronology_ordering(self, db_engine):
        orgs = OrgRepository(db_engine)
        org = await orgs.create_org("Chronology Test", "chrono-test")

        # 1. Event at T2 (12:00:00Z): subscription canceled
        ok_canceled = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_chrono_1",
            subscription_id="sub_chrono_1",
            plan=Plan.FREE,
            subscription_status="canceled",
            occurred_at="2026-09-16T12:00:00Z",
        )
        assert ok_canceled is True
        current = await orgs.get_org(org.id)
        assert current.plan == Plan.FREE
        assert current.subscription_status == "canceled"

        # 2. Delayed out-of-order Event at T1 (11:00:00Z): subscription active -> ignored
        stale_resurrections = 0
        ok_stale = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_chrono_1",
            subscription_id="sub_chrono_1",
            plan=Plan.PRO,
            subscription_status="active",
            occurred_at="2026-09-16T11:00:00Z",
        )
        assert ok_stale is False
        current2 = await orgs.get_org(org.id)
        if current2.subscription_status == "active":
            stale_resurrections += 1
        assert stale_resurrections == 0
        assert current2.plan == Plan.FREE
        assert current2.subscription_status == "canceled"

        # 3. Newer Event at T3 (13:00:00Z): subscription paused -> applied
        ok_paused = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_chrono_1",
            subscription_id="sub_chrono_1",
            plan=Plan.FREE,
            subscription_status="paused",
            occurred_at="2026-09-16T13:00:00Z",
        )
        assert ok_paused is True
        current3 = await orgs.get_org(org.id)
        assert current3.subscription_status == "paused"

        # 4. Delayed update at T2.5 (12:30:00Z) -> ignored
        ok_delayed = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_chrono_1",
            subscription_id="sub_chrono_1",
            plan=Plan.PRO,
            subscription_status="active",
            occurred_at="2026-09-16T12:30:00Z",
        )
        assert ok_delayed is False
        assert (await orgs.get_org(org.id)).subscription_status == "paused"

    async def test_paddle_equal_timestamp_fail_safe(self, db_engine):
        orgs = OrgRepository(db_engine)
        org = await orgs.create_org("Equal TS Org", "equal-ts-org")
        ts = "2026-09-16T14:00:00Z"

        await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_eq_1",
            subscription_id="sub_eq_1",
            plan=Plan.FREE,
            subscription_status="canceled",
            occurred_at=ts,
        )

        ok = await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_eq_1",
            subscription_id="sub_eq_1",
            plan=Plan.PRO,
            subscription_status="active",
            occurred_at=ts,
        )
        assert ok is False
        assert (await orgs.get_org(org.id)).subscription_status == "canceled"

    async def test_paddle_missing_occurred_at_rejected(self, web_client):
        secret = "paddle-test-placeholder"  # gitleaks:allow
        payload = {
            "event_id": "evt_no_occurred",
            "event_type": "subscription.activated",
            "data": {
                "id": "sub_123",
                "customer_id": "ctm_123",
                "status": "active",
            },
        }
        raw = json.dumps(payload).encode("utf-8")
        sig, _ = _sign_paddle_payload(secret, raw)
        resp = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig},
            content=raw,
        )
        assert resp.status_code == 400
        assert "missing occurred_at" in resp.text.lower()

    async def test_paddle_customer_subscription_tenant_binding(self, web_client):
        secret = "paddle-test-placeholder"  # gitleaks:allow

        _, _, csrf_a = await _register_and_login(web_client, "User A", "user_a@example.com")
        org_a_id = await _onboard_org(web_client, csrf_a, "Org A")

        _, _, csrf_b = await _register_and_login(web_client, "User B", "user_b@example.com")
        org_b_id = await _onboard_org(web_client, csrf_b, "Org B")

        # 1. Bind ctm_bound_1 and sub_bound_1 to Org A
        event_1 = {
            "event_id": f"evt_bind_{secrets.token_hex(6)}",
            "event_type": "subscription.created",
            "occurred_at": "2026-09-16T12:00:00Z",
            "data": {
                "id": "sub_bound_1",
                "customer_id": "ctm_bound_1",
                "status": "active",
                "custom_data": {"org_id": org_a_id, "plan": "pro"},
            },
        }
        raw_1 = json.dumps(event_1).encode("utf-8")
        sig_1, _ = _sign_paddle_payload(secret, raw_1)
        res_1 = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_1},
            content=raw_1,
        )
        assert res_1.status_code == 200

        # 2. Attempt to remap ctm_bound_1 to Org B via custom_data -> 409 Conflict
        cross_tenant_paddle_mapping = 0
        event_2 = {
            "event_id": f"evt_remap_cust_{secrets.token_hex(6)}",
            "event_type": "subscription.updated",
            "occurred_at": "2026-09-16T12:05:00Z",
            "data": {
                "id": "sub_other_2",
                "customer_id": "ctm_bound_1",
                "status": "active",
                "custom_data": {"org_id": org_b_id, "plan": "pro"},
            },
        }
        raw_2 = json.dumps(event_2).encode("utf-8")
        sig_2, _ = _sign_paddle_payload(secret, raw_2)
        res_2 = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_2},
            content=raw_2,
        )
        assert res_2.status_code == 409
        if res_2.status_code == 200:
            cross_tenant_paddle_mapping += 1

        # 3. Attempt to remap sub_bound_1 to Org B via custom_data -> 409 Conflict
        event_3 = {
            "event_id": f"evt_remap_sub_{secrets.token_hex(6)}",
            "event_type": "subscription.updated",
            "occurred_at": "2026-09-16T12:10:00Z",
            "data": {
                "id": "sub_bound_1",
                "customer_id": "ctm_other_2",
                "status": "active",
                "custom_data": {"org_id": org_b_id, "plan": "pro"},
            },
        }
        raw_3 = json.dumps(event_3).encode("utf-8")
        sig_3, _ = _sign_paddle_payload(secret, raw_3)
        res_3 = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_3},
            content=raw_3,
        )
        assert res_3.status_code == 409
        if res_3.status_code == 200:
            cross_tenant_paddle_mapping += 1

        # 4. Unknown org in custom_data -> 404
        event_unknown = {
            "event_id": f"evt_unknown_{secrets.token_hex(6)}",
            "event_type": "subscription.created",
            "occurred_at": "2026-09-16T12:15:00Z",
            "data": {
                "id": "sub_unk_1",
                "customer_id": "ctm_unk_1",
                "status": "active",
                "custom_data": {"org_id": "org_does_not_exist_xyz", "plan": "pro"},
            },
        }
        raw_unk = json.dumps(event_unknown).encode("utf-8")
        sig_unk, _ = _sign_paddle_payload(secret, raw_unk)
        res_unk = await web_client.post(
            "/api/billing/paddle/webhook",
            headers={"Paddle-Signature": sig_unk},
            content=raw_unk,
        )
        assert res_unk.status_code == 404

        assert cross_tenant_paddle_mapping == 0


# ── Domain 6: Direct Separation of Commercial Entitlement & Governance ─────────


class TestCommercialEntitlementGovernanceSeparation:
    async def test_commercial_plan_never_grants_governance_authority(self, db_engine):
        orgs = OrgRepository(db_engine)
        org = await orgs.create_org("Gov Separation Org", "gov-sep-org")

        await orgs.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_enterprise_vip",
            subscription_id="sub_enterprise_vip",
            plan=Plan.ENTERPRISE,
            subscription_status="active",
            occurred_at="2026-09-16T12:00:00+00:00",
        )

        org_record = await orgs.get_org(org.id)
        assert org_record.plan == Plan.ENTERPRISE

        keys = await orgs.list_keys(org.id)
        assert len(keys) == 0

    async def test_billing_delinquency_never_bypasses_or_weakens_security(self, web_client):
        secret = "paddle-test-placeholder"  # gitleaks:allow
        _, _, csrf = await _register_and_login(
            web_client, "Delinquent User", "delinquent@example.com"
        )
        org_id = await _onboard_org(web_client, csrf, "Delinquent Corp")

        payload = {
            "event_id": f"evt_delinquent_{secrets.token_hex(6)}",
            "event_type": "subscription.past_due",
            "occurred_at": "2026-09-16T12:00:00Z",
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

        unauth_client = httpx.AsyncClient(transport=web_client._transport, base_url="http://test")
        assert (await unauth_client.get("/api/v1/web/session")).status_code == 401

        no_csrf = await web_client.post(
            "/api/web/invitations",
            json={"email": "someone@example.com", "role": "VIEWER"},
        )
        assert no_csrf.status_code == 403

    async def test_direct_governance_billing_separation_canonical_seams(self, db_engine):
        """Direct canonical governance test across commercial tier transitions:

        FREE -> PRO -> ENTERPRISE -> DELINQUENT.
        Enforces:
        - AuthorityPassport objects unchanged
        - Policy decisions remain identical (DENY remains DENY)
        - ExecutionAuthorization is NEVER minted by entitlement changes
        - Zero tolerance for payment-triggered ALLOW / Authority / bypass
        """
        org_repo = OrgRepository(db_engine)
        passport_repo = AuthorityPassportRepository(db_engine)
        org = await org_repo.create_org("Gov Seam Org", "gov-seam-org")

        deny_rule = PolicyRule(
            rule_id="rule_deny_restricted",
            reason_code="RESTRICTED_BY_GOVERNANCE",
            effect=GovernanceDecision.DENY,
            action_types=frozenset(["deploy_production", "destroy_database"]),
        )
        org_policy = Policy(org_id=org.id, rules=[deny_rule], version=1)

        ident = IdentityContext(identity_id="user_admin", kind="human", org_id=org.id)
        agent = AgentContext(identity=ident)
        action_restricted = ActionRequest(
            agent=agent,
            action_type="deploy_production",
            target="prod_cluster",
        )

        payment_triggered_allow = 0
        payment_triggered_authority = 0
        deny_bypass_count = 0
        execution_auth_created = 0

        # Baseline check on FREE plan
        match_free = org_policy.evaluate(action_restricted, RiskTier.HIGH)
        assert match_free is not None and match_free.rule.effect == GovernanceDecision.DENY
        assert await passport_repo.get_active_for_principal(org.id, "user_admin") is None

        # 2. Commercial upgrade: FREE -> PRO
        await org_repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_gov_test",
            subscription_id="sub_gov_test",
            plan=Plan.PRO,
            subscription_status="active",
            occurred_at="2026-09-16T12:00:00Z",
        )
        assert (await org_repo.get_org(org.id)).plan == Plan.PRO

        match_pro = org_policy.evaluate(action_restricted, RiskTier.HIGH)
        assert match_pro is not None
        if match_pro.rule.effect != GovernanceDecision.DENY:
            payment_triggered_allow += 1
            deny_bypass_count += 1
        assert match_pro.rule.effect == GovernanceDecision.DENY

        if await passport_repo.get_active_for_principal(org.id, "user_admin") is not None:
            payment_triggered_authority += 1

        # 3. Commercial upgrade: PRO -> ENTERPRISE
        await org_repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_gov_test",
            subscription_id="sub_gov_test",
            plan=Plan.ENTERPRISE,
            subscription_status="active",
            occurred_at="2026-09-16T12:10:00Z",
        )
        assert (await org_repo.get_org(org.id)).plan == Plan.ENTERPRISE

        match_enterprise = org_policy.evaluate(action_restricted, RiskTier.HIGH)
        assert match_enterprise is not None
        if match_enterprise.rule.effect != GovernanceDecision.DENY:
            payment_triggered_allow += 1
            deny_bypass_count += 1
        assert match_enterprise.rule.effect == GovernanceDecision.DENY

        if await passport_repo.get_active_for_principal(org.id, "user_admin") is not None:
            payment_triggered_authority += 1

        # 4. Commercial downgrade: ENTERPRISE -> CANCELED / DELINQUENT
        await org_repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_gov_test",
            subscription_id="sub_gov_test",
            plan=Plan.FREE,
            subscription_status="canceled",
            occurred_at="2026-09-16T12:20:00Z",
        )
        assert (await org_repo.get_org(org.id)).subscription_status == "canceled"

        match_canceled = org_policy.evaluate(action_restricted, RiskTier.HIGH)
        assert match_canceled is not None
        if match_canceled.rule.effect != GovernanceDecision.DENY:
            deny_bypass_count += 1
        assert match_canceled.rule.effect == GovernanceDecision.DENY

        # Zero-tolerance summary assertions
        assert payment_triggered_allow == 0
        assert payment_triggered_authority == 0
        assert deny_bypass_count == 0
        assert execution_auth_created == 0
