# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 2 branch-coverage: SAML, recovery, break-glass, notifications, provider deny paths."""

from __future__ import annotations

import base64
import json
import time
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy import insert, select, update

from responsibleai.db.engine import (
    account_recovery_requests,
    create_engine,
    identity_security_notifications,
    org_security_policies,
    organization_idp_bindings,
    organization_sso_configs,
    provider_identities,
    web_users,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    AUTHENTICATION_FAILED,
    BREAK_GLASS_DENIED,
    CHALLENGE_REPLAY,
    COMPANY_VERIFICATION_REQUIRED,
    ENTRA_TENANT_MISMATCH,
    GOOGLE_WORKSPACE_MISMATCH,
    PASSKEY_REQUIRED,
    PROVIDER_TOKEN_INVALID,
    RECOVERY_REVIEW_REQUIRED,
    SSO_REQUIRED,
    SSO_TENANT_MISMATCH,
    STEP_UP_REQUIRED,
    UNAUTHENTICATED,
    EnterpriseError,
)
from responsibleai.enterprise.security.oidc import MSA_TENANT, OIDCTokenValidator, VerifiedIDToken
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.service import (
    ENTRA_PROVIDER,
    GOOGLE_PROVIDER,
    GOOGLE_WORKSPACE,
    IdentitySecurityService,
    _hash,
    _iso,
    _now,
    _unverified_iss,
)
from responsibleai.enterprise.service import EnterpriseIAM
from tests.test_saml import _signed_response

pytest_plugins = ("tests.test_saml",)


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _user(engine, email: str = "human@example.com") -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


async def _svc(engine, **kwargs) -> IdentitySecurityService:
    return IdentitySecurityService(engine, rp_id="localhost", origin="http://localhost", **kwargs)


async def _org(engine, owner_id: str) -> str:
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner_id,
        name="Batch2 Org",
        slug=f"b2-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    return org["id"]


async def _passkey_session(svc: IdentitySecurityService, user_id: str):
    return await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label="203.0.113.9", user_agent="test"
    )


async def _password_session(svc: IdentitySecurityService, user_id: str):
    return await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )


def _rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()

    def b64int(n: int) -> str:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    jwk = {
        "kty": "RSA",
        "kid": "kid-1",
        "n": b64int(pub.n),
        "e": b64int(pub.e),
        "alg": "RS256",
        "use": "sig",
    }
    return key, jwk


async def _insert_sso(
    engine,
    org_id: str,
    owner: str,
    *,
    protocol: str = "OIDC",
    issuer: str = "https://login.microsoftonline.com/tenant/v2.0",
    client_id: str = "https://whitepact.com/saml/metadata",
    redirect_uri: str = "http://localhost:8765/api/auth/acs",
    idp_entity_id: str | None = "test-idp",
    idp_cert: str | None = None,
) -> None:
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organization_sso_configs).values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                protocol=protocol,
                issuer=issuer,
                client_id=client_id,
                client_secret_encrypted=None,
                redirect_uri=redirect_uri,
                enforcement="SSO_REQUIRED",
                provisioning="INVITE_ONLY",
                idp_entity_id=idp_entity_id,
                idp_sso_url="https://idp.example/sso",
                idp_x509_cert=idp_cert,
                created_by=owner,
                created_at=now,
                updated_at=now,
            )
        )


async def _break_glass_policy(engine, org_id: str, user_id: str) -> None:
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(org_security_policies).values(
                org_id=org_id,
                phishing_resistant_required=0,
                privileged_roles_json='["OWNER"]',
                sso_enforcement="SSO_OPTIONAL",
                dual_control_json="[]",
                break_glass_user_id=user_id,
                updated_at=now,
            )
        )
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == user_id)
            .values(verification_status="IDENTITY_VERIFIED")
        )


# ── SAML deny paths ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_consume_saml_missing_sso_config_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_saml_assertion(
            org_id=org_id,
            saml_response="aGVsbG8=",
            request_id="_req",
            session_secret="secret",
        )
    assert exc.value.code == SSO_REQUIRED


@pytest.mark.asyncio
async def test_consume_saml_oidc_protocol_not_saml_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await _insert_sso(engine, org_id, owner, protocol="OIDC")
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_saml_assertion(
            org_id=org_id,
            saml_response="aGVsbG8=",
            request_id="_req",
            session_secret="secret",
        )
    assert exc.value.code == SSO_REQUIRED


@pytest.mark.asyncio
async def test_consume_saml_invalid_assertion_denied(engine, idp_keypair) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    _, cert_pem = idp_keypair
    await _insert_sso(engine, org_id, owner, protocol="SAML", idp_cert=cert_pem)
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_saml_assertion(
            org_id=org_id,
            saml_response=base64.b64encode(b"<not-saml/>").decode(),
            request_id="_wpREQ123",
            session_secret="test-session-secret",
        )
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_consume_saml_assertion_replay_denied(engine, idp_keypair) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    _, cert_pem = idp_keypair
    await _insert_sso(engine, org_id, owner, protocol="SAML", idp_cert=cert_pem)
    svc = await _svc(engine)
    request_id = "_wpREQ456"
    response = _signed_response(idp_keypair, in_response_to=request_id)
    await svc.consume_saml_assertion(
        org_id=org_id,
        saml_response=response,
        request_id=request_id,
        session_secret="test-session-secret",
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_saml_assertion(
            org_id=org_id,
            saml_response=response,
            request_id=request_id,
            session_secret="test-session-secret",
        )
    assert exc.value.code == CHALLENGE_REPLAY


# ── Enterprise OIDC SSO callback deny paths ────────────────────────────────


@pytest.mark.asyncio
async def test_consume_oidc_sso_unconfigured_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    claims = VerifiedIDToken(
        issuer="https://login.microsoftonline.com/tenant/v2.0",
        subject="sub",
        audience="cli",
        email="u@co.com",
        hosted_domain=None,
        tenant_id="tenant",
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_oidc_code_claims(
            org_id=org_id, claims=claims, redirect_uri="https://app/cb"
        )
    assert exc.value.code == SSO_REQUIRED


@pytest.mark.asyncio
async def test_consume_oidc_sso_redirect_uri_mismatch_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await _insert_sso(
        engine,
        org_id,
        owner,
        redirect_uri="https://app.example.com/callback",
        client_id="oidc-client",
    )
    svc = await _svc(engine)
    claims = VerifiedIDToken(
        issuer="https://login.microsoftonline.com/tenant/v2.0",
        subject="sub",
        audience="oidc-client",
        email="u@co.com",
        hosted_domain=None,
        tenant_id="tenant",
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_oidc_code_claims(
            org_id=org_id, claims=claims, redirect_uri="https://evil.example/callback"
        )
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_consume_oidc_sso_issuer_mixup_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await _insert_sso(
        engine,
        org_id,
        owner,
        issuer="https://login.microsoftonline.com/expected/v2.0",
        redirect_uri="https://app.example.com/callback",
        client_id="oidc-client",
    )
    svc = await _svc(engine)
    claims = VerifiedIDToken(
        issuer="https://login.microsoftonline.com/wrong/v2.0",
        subject="sub",
        audience="oidc-client",
        email="u@co.com",
        hosted_domain=None,
        tenant_id="tenant",
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_oidc_code_claims(
            org_id=org_id,
            claims=claims,
            redirect_uri="https://app.example.com/callback",
        )
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_consume_oidc_sso_tenant_binding_mismatch_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await _insert_sso(
        engine,
        org_id,
        owner,
        redirect_uri="https://app.example.com/callback",
        client_id="oidc-client",
    )
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organization_idp_bindings).values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                provider=ENTRA_PROVIDER,
                tenant_id="bound-tenant",
                issuer="https://login.microsoftonline.com/bound-tenant/v2.0",
                verified_domain=None,
                status="ACTIVE",
                configured_by=owner,
                verified_at=now,
                policy_json="{}",
                created_at=now,
            )
        )
    svc = await _svc(engine)
    expected_issuer = "https://login.microsoftonline.com/tenant/v2.0"
    claims = VerifiedIDToken(
        issuer=expected_issuer,
        subject="sub",
        audience="oidc-client",
        email="u@co.com",
        hosted_domain=None,
        tenant_id="other-tenant",
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_oidc_code_claims(
            org_id=org_id,
            claims=claims,
            redirect_uri="https://app.example.com/callback",
        )
    assert exc.value.code == SSO_TENANT_MISMATCH


# ── Account recovery deny paths ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_recovery_token_passkey_shortcut_denied(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_token("any-token", passkey_ok=True)
    assert exc.value.code == RECOVERY_REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_recovery_token_unknown_denied(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_token("not-a-real-recovery-token-value")
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_recovery_token_wrong_user_denied(engine) -> None:
    await _user(engine, "rec@example.com")
    other = await _user(engine, "other@example.com")
    svc = await _svc(engine)
    await svc.request_recovery("rec@example.com")
    token = svc.last_recovery_token_for_tests
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_token(token, user_id=other)
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_recovery_token_expired_denied(engine) -> None:
    user_id = await _user(engine, "exp@example.com")
    svc = await _svc(engine)
    raw = "expired-recovery-token-value"
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(account_recovery_requests).values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                token_hash=_hash(raw),
                status="RECOVERY_CHALLENGED",
                privileged=0,
                created_at=_iso(_now() - timedelta(hours=2)),
                expires_at=_iso(_now() - timedelta(minutes=1)),
                evidence_json="{}",
            )
        )
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_token(raw)
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_recovery_code_invalid_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_code(user_id, "NOTVALID12")
    assert exc.value.code == AUTHENTICATION_FAILED


@pytest.mark.asyncio
async def test_recovery_privileged_owner_email_only_denied(engine) -> None:
    owner = await _user(engine, "owner@example.com")
    await _org(engine, owner)
    svc = await _svc(engine)
    await svc.request_recovery("owner@example.com")
    token = svc.last_recovery_token_for_tests
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_token(token)
    assert exc.value.code == RECOVERY_REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_recovery_privileged_wrong_backup_code_denied(engine) -> None:
    owner = await _user(engine, "priv@example.com")
    await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=None)
    await svc.issue_recovery_codes(owner, session=session, grant=grant)
    await svc.request_recovery("priv@example.com")
    token = svc.last_recovery_token_for_tests
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_token(token, recovery_code="BBBBBBBBBB")
    assert exc.value.code == AUTHENTICATION_FAILED


# ── Break-glass deny paths ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_break_glass_wrong_principal_denied(engine) -> None:
    owner = await _user(engine)
    intruder = await _user(engine, "intruder@example.com")
    org_id = await _org(engine, owner)
    await _break_glass_policy(engine, org_id, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, intruder)
    with pytest.raises(EnterpriseError) as exc:
        await svc.break_glass(org_id=org_id, user_id=intruder, session=session)
    assert exc.value.code == BREAK_GLASS_DENIED


@pytest.mark.asyncio
async def test_break_glass_not_configured_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    with pytest.raises(EnterpriseError) as exc:
        await svc.break_glass(org_id=org_id, user_id=owner, session=session)
    assert exc.value.code == BREAK_GLASS_DENIED


@pytest.mark.asyncio
async def test_break_glass_requires_phishing_resistant_session(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await _break_glass_policy(engine, org_id, owner)
    svc = await _svc(engine)
    _, _, session = await _password_session(svc, owner)
    with pytest.raises(EnterpriseError) as exc:
        await svc.break_glass(org_id=org_id, user_id=owner, session=session)
    assert exc.value.code == PASSKEY_REQUIRED


@pytest.mark.asyncio
async def test_break_glass_identity_not_verified_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(org_security_policies).values(
                org_id=org_id,
                phishing_resistant_required=0,
                privileged_roles_json='["OWNER"]',
                sso_enforcement="SSO_OPTIONAL",
                dual_control_json="[]",
                break_glass_user_id=owner,
                updated_at=now,
            )
        )
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    with pytest.raises(EnterpriseError) as exc:
        await svc.break_glass(org_id=org_id, user_id=owner, session=session)
    assert exc.value.code == BREAK_GLASS_DENIED


@pytest.mark.asyncio
async def test_evaluate_privileged_role_change_without_passkey_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _password_session(svc, owner)
    with pytest.raises(EnterpriseError) as exc:
        await svc.evaluate_role_change(session, new_role="OWNER", org_id=org_id)
    assert exc.value.code == PASSKEY_REQUIRED


# ── Provider login edge deny paths ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_google_login_missing_client_configuration_denied(engine) -> None:
    svc = await _svc(engine, allow_raw_id_token=True)
    with pytest.raises(EnterpriseError) as exc:
        await svc.google_login(id_token="a.b.c", nonce="n1")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_google_login_unexpected_issuer_denied(engine) -> None:
    key, jwk = _rsa_keypair()
    svc = await _svc(engine, google_client_id="google-client", allow_raw_id_token=True)
    token = jwt.encode(
        {
            "iss": "https://evil.example",
            "aud": "google-client",
            "sub": "s",
            "exp": int(time.time()) + 120,
            "iat": int(time.time()),
            "nonce": "n1",
        },
        key,
        algorithm="RS256",
        headers={"kid": "kid-1"},
    )

    async def _get(self, kid, allow_refresh=True):
        return jwk

    with patch("responsibleai.enterprise.security.oidc.TrustedJWKS.get", new=_get):
        with pytest.raises(EnterpriseError) as exc:
            await svc.google_login(id_token=token, nonce="n1")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_google_login_company_path_without_binding_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine, google_client_id="google-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="sub",
        audience="google-client",
        email="a@acme.com",
        hosted_domain="acme.com",
        tenant_id=None,
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
        with pytest.raises(EnterpriseError) as exc:
            await svc.google_login(id_token="x.y.z", nonce="n1", intended_org_id=org_id)
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_google_login_hosted_domain_mismatch_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine, google_client_id="google-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="sub",
        audience="google-client",
        email="a@acme.com",
        hosted_domain="other.com",
        tenant_id=None,
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(
        IdentitySecurityService,
        "_binding",
        AsyncMock(return_value={"verified_domain": "acme.com", "tenant_id": None}),
    ):
        with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
            with pytest.raises(EnterpriseError) as exc:
                await svc.google_login(id_token="x.y.z", nonce="n1", intended_org_id=org_id)
    assert exc.value.code == GOOGLE_WORKSPACE_MISMATCH


@pytest.mark.asyncio
async def test_microsoft_login_missing_client_configuration_denied(engine) -> None:
    svc = await _svc(engine, allow_raw_id_token=True)
    with pytest.raises(EnterpriseError) as exc:
        await svc.microsoft_login(id_token="a.b.c", nonce="n1")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_microsoft_login_unexpected_issuer_denied(engine) -> None:
    svc = await _svc(engine, microsoft_client_id="ms-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer="https://evil.example/v2.0",
        subject="oid",
        audience="ms-client",
        email="u@co.com",
        hosted_domain=None,
        tenant_id="tenant-1",
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
        with pytest.raises(EnterpriseError) as exc:
            await svc.microsoft_login(id_token="a.b.c", nonce="n1")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_microsoft_login_company_path_without_binding_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine, microsoft_client_id="ms-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer="https://login.microsoftonline.com/tenant-1/v2.0",
        subject="oid",
        audience="ms-client",
        email="u@co.com",
        hosted_domain=None,
        tenant_id="tenant-1",
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
        with pytest.raises(EnterpriseError) as exc:
            await svc.microsoft_login(id_token="a.b.c", nonce="n1", intended_org_id=org_id)
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_microsoft_login_personal_account_company_path_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine, microsoft_client_id="ms-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer=f"https://login.microsoftonline.com/{MSA_TENANT}/v2.0",
        subject="oid",
        audience="ms-client",
        email="user@outlook.com",
        hosted_domain=None,
        tenant_id=MSA_TENANT,
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(
        IdentitySecurityService,
        "_binding",
        AsyncMock(return_value={"tenant_id": "corp-tenant", "verified_domain": "co.com"}),
    ):
        with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
            with pytest.raises(EnterpriseError) as exc:
                await svc.microsoft_login(id_token="a.b.c", nonce="n1", intended_org_id=org_id)
    assert exc.value.code == ENTRA_TENANT_MISMATCH


@pytest.mark.asyncio
async def test_begin_hosted_oauth_unknown_provider_denied(engine) -> None:
    svc = await _svc(engine, google_client_id="g", google_client_secret="s")
    with pytest.raises(EnterpriseError) as exc:
        await svc.begin_hosted_oauth(provider="enterprise_sso", redirect_uri="https://app/cb")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_begin_hosted_oauth_google_missing_secret_denied(engine) -> None:
    svc = await _svc(engine, google_client_id="g", google_client_secret=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.begin_hosted_oauth(provider="google", redirect_uri="https://app/cb")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_complete_hosted_oauth_unknown_provider_denied(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.complete_hosted_oauth(
            provider="ENTERPRISE_SSO", state="st", code="cd", redirect_uri="https://app/cb"
        )
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_unverified_iss_malformed_jwt_denied() -> None:
    with pytest.raises(EnterpriseError) as exc:
        _unverified_iss("not-a-jwt")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_unverified_iss_non_microsoft_issuer_denied() -> None:
    header = base64.urlsafe_b64encode(b'{"alg":"none"}').rstrip(b"=").decode()
    payload = (
        base64.urlsafe_b64encode(json.dumps({"iss": "https://accounts.google.com"}).encode())
        .rstrip(b"=")
        .decode()
    )
    token = f"{header}.{payload}.sig"
    with pytest.raises(EnterpriseError) as exc:
        _unverified_iss(token)
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_linked_provider_login_without_membership_denied(engine) -> None:
    user_id = await _user(engine, "linked@example.com")
    owner = await _user(engine, "owner@example.com")
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(provider_identities).values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider=GOOGLE_PROVIDER,
                subject="google-sub-1",
                tenant_id="",
                hosted_domain=None,
                account_kind="PERSONAL",
                email_at_link="linked@example.com",
                status="ACTIVE",
                created_at=now,
            )
        )
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="google-sub-1",
        audience="c",
        email="linked@example.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc._complete_provider_login(
            provider=GOOGLE_PROVIDER,
            claims=claims,
            account_kind="PERSONAL",
            org_id=org_id,
            method=AuthMethod.GOOGLE_OIDC,
        )
    assert exc.value.code == SSO_TENANT_MISMATCH


@pytest.mark.asyncio
async def test_jit_disabled_provider_login_without_membership_denied(engine) -> None:
    user_id = await _user(engine, "jit@example.com")
    owner = await _user(engine, "jit-owner@example.com")
    org_id = await _org(engine, owner)
    await _insert_sso(
        engine,
        org_id,
        owner,
        protocol="OIDC",
        redirect_uri="https://app.example.com/callback",
        client_id="oidc-client",
    )
    svc = await _svc(engine)
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(provider_identities).values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider=GOOGLE_PROVIDER,
                subject="google-sub-jit",
                tenant_id="acme.com",
                hosted_domain="acme.com",
                account_kind="WORKSPACE",
                email_at_link="jit@acme.com",
                status="ACTIVE",
                created_at=now,
            )
        )
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="google-sub-jit",
        audience="c",
        email="jit@acme.com",
        hosted_domain="acme.com",
        tenant_id=None,
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(
        IdentitySecurityService,
        "_binding",
        AsyncMock(return_value={"verified_domain": "acme.com", "tenant_id": None}),
    ):
        with pytest.raises(EnterpriseError) as exc:
            await svc._complete_provider_login(
                provider=GOOGLE_PROVIDER,
                claims=claims,
                account_kind="WORKSPACE",
                org_id=org_id,
                method=AuthMethod.GOOGLE_OIDC,
            )
    assert exc.value.code == SSO_TENANT_MISMATCH


# ── Notifications, domain challenge, IdP binding deny paths ────────────────


@pytest.mark.asyncio
async def test_notify_redacts_secret_and_token_payload_keys(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc._notify(
        "test_event",
        user_id=user_id,
        payload={"client_secret": "leak", "refresh_token": "leak", "provider": "GOOGLE"},
    )
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(identity_security_notifications).where(
                    identity_security_notifications.c.user_id == user_id
                )
            )
        ).fetchone()
    assert row is not None
    stored = json.loads(row.payload_json)
    assert "client_secret" not in stored
    assert "refresh_token" not in stored
    assert stored["provider"] == "GOOGLE"


@pytest.mark.asyncio
async def test_domain_challenge_unsupported_method_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.start_domain_challenge(
            org_id=org_id,
            domain="example.com",
            method="EMAIL_LINK",
            session=session,
            grant=grant,
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_domain_challenge_complete_wrong_token_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id)
    token = await svc.start_domain_challenge(
        org_id=org_id,
        domain="example.com",
        method="DNS_TXT",
        session=session,
        grant=grant,
    )
    svc.txt_lookup = lambda _d: [f"whitepact-verify={token}"]
    with pytest.raises(EnterpriseError) as exc:
        await svc.complete_domain_challenge(
            org_id=org_id,
            domain="example.com",
            method="DNS_TXT",
            token="wrong-token-value",
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_bind_idp_without_verification_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    grant = await svc.issue_step_up(
        session, SensitiveAction.CHANGE_GOOGLE_WORKSPACE_BINDING, org_id=org_id
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.bind_organization_idp(
            org_id=org_id,
            provider=GOOGLE_WORKSPACE,
            tenant_id=None,
            issuer="https://accounts.google.com",
            verified_domain="acme.com",
            configured_by=owner,
            session=session,
            grant=grant,
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_configure_sso_wildcard_redirect_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    grant = await svc.issue_step_up(session, SensitiveAction.CONFIGURE_SSO, org_id=org_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.configure_sso(
            org_id=org_id,
            session=session,
            grant=grant,
            protocol="OIDC",
            issuer="https://login.microsoftonline.com/t/v2.0",
            client_id="cli",
            client_secret="not-placeholder-secret",
            redirect_uri="https://*.example.com/callback",
            enforcement="SSO_OPTIONAL",
            provisioning="INVITE_ONLY",
        )
    assert exc.value.code == SSO_REQUIRED


@pytest.mark.asyncio
async def test_start_domain_challenge_without_step_up_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _password_session(svc, owner)
    with pytest.raises(EnterpriseError) as exc:
        await svc.start_domain_challenge(
            org_id=org_id,
            domain="example.com",
            method="DNS_TXT",
            session=session,
            grant=None,
        )
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_domain_challenge_missing_pending_row_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.complete_domain_challenge(
            org_id=org_id,
            domain="missing.example",
            method="DNS_TXT",
            token="nope",
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_domain_challenge_https_well_known_failure_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id)
    token = await svc.start_domain_challenge(
        org_id=org_id,
        domain="wellknown.example",
        method="HTTPS_WELL_KNOWN",
        session=session,
        grant=grant,
    )
    svc.well_known_lookup = lambda _d: "not-the-token"
    with pytest.raises(EnterpriseError) as exc:
        await svc.complete_domain_challenge(
            org_id=org_id,
            domain="wellknown.example",
            method="HTTPS_WELL_KNOWN",
            token=token,
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED
