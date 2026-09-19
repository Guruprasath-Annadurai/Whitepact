# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial tests for Enterprise SaaS Layer 2 identity security."""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key

from responsibleai.db.engine import create_engine, org_security_policies, web_users
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    ACCOUNT_LINK_CONFLICT,
    AUTHENTICATION_FAILED,
    CHALLENGE_REPLAY,
    ENTRA_TENANT_MISMATCH,
    GOOGLE_WORKSPACE_MISMATCH,
    PROVIDER_TOKEN_INVALID,
    RECOVERY_REVIEW_REQUIRED,
    SECURITY_DOWNGRADE_BLOCKED,
    SSO_REQUIRED,
    STEP_UP_REQUIRED,
    WEBAUTHN_INVALID,
    EnterpriseError,
)
from responsibleai.enterprise.security.oidc import OIDCTokenValidator, VerifiedIDToken
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.preflight import assert_layer2_provider_boot_safe
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_encode
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN
from tests.webauthn_fakes import assertion_blob, registration_blob


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


async def _passkey_session(svc: IdentitySecurityService, user_id: str):
    token, csrf, assurance = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label="203.0.113.9", user_agent="test"
    )
    return token, csrf, assurance


def _rsa():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    import base64

    def b64int(n: int) -> str:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    jwk = {"kty": "RSA", "kid": "kid-1", "n": b64int(pub.n), "e": b64int(pub.e), "alg": "RS256", "use": "sig"}
    return key, jwk


def _token(key, *, iss, aud, sub, nonce="n1", extra=None, exp=None, kid="kid-1"):
    now = int(time.time())
    payload = {"iss": iss, "aud": aud, "sub": sub, "iat": now, "exp": exp or now + 300, "nonce": nonce}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


@pytest.mark.asyncio
async def test_passkey_challenge_replay_and_wrong_origin_rpid_user(engine) -> None:
    user_id = await _user(engine)
    other = await _user(engine, "other@example.com")
    svc = await _svc(engine)
    token, csrf, session = await _passkey_session(svc, user_id)
    begin = await svc.begin_webauthn(user_id=user_id, session_id=session.session_id, ceremony="register")
    from responsibleai.enterprise.security.webauthn import b64url_decode

    challenge = b64url_decode(begin["challenge"])
    key = generate_private_key(SECP256R1())
    cdata, adata, cred_b64, _ = registration_blob(rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key)
    rec = await svc.finish_passkey_registration(
        user_id=user_id, session=session, client_data_b64=cdata, authenticator_data_b64=adata, display_name="Laptop"
    )
    assert rec["credential_id"]
    with pytest.raises(EnterpriseError) as replay:
        await svc.finish_passkey_registration(
            user_id=user_id, session=session, client_data_b64=cdata, authenticator_data_b64=adata
        )
    assert replay.value.code == CHALLENGE_REPLAY

    begin2 = await svc.begin_webauthn(user_id=user_id, session_id=session.session_id, ceremony="register")
    ch2 = b64url_decode(begin2["challenge"])
    bad_origin, adata2, _, _ = registration_blob(rp_id="localhost", origin="https://evil.example", challenge=ch2, private_key=key)
    with pytest.raises(EnterpriseError) as origin:
        await svc.finish_passkey_registration(
            user_id=user_id, session=session, client_data_b64=bad_origin, authenticator_data_b64=adata2
        )
    assert origin.value.code in {WEBAUTHN_INVALID, CHALLENGE_REPLAY}

    begin3 = await svc.begin_webauthn(user_id=other, session_id="s", ceremony="register")
    ch3 = b64url_decode(begin3["challenge"])
    c3, a3, _, _ = registration_blob(rp_id="localhost", origin="http://localhost", challenge=ch3, private_key=key)
    with pytest.raises(EnterpriseError):
        await svc.finish_passkey_registration(user_id=user_id, session=session, client_data_b64=c3, authenticator_data_b64=a3)


@pytest.mark.asyncio
async def test_passkey_authenticate_wrong_credential_and_removed(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    begin = await svc.begin_webauthn(user_id=user_id, session_id=session.session_id, ceremony="register")
    from responsibleai.enterprise.security.webauthn import b64url_decode

    challenge = b64url_decode(begin["challenge"])
    key = generate_private_key(SECP256R1())
    cdata, adata, cred_b64, _ = registration_blob(rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key)
    rec = await svc.finish_passkey_registration(
        user_id=user_id, session=session, client_data_b64=cdata, authenticator_data_b64=adata
    )
    auth_begin = await svc.begin_webauthn(user_id=user_id, session_id=session.session_id, ceremony="authenticate")
    ach = b64url_decode(auth_begin["challenge"])
    ac, aa, asig = assertion_blob(rp_id="localhost", origin="http://localhost", challenge=ach, private_key=key, sign_count=2)
    token, csrf, assurance = await svc.authenticate_passkey(
        client_data_b64=ac, authenticator_data_b64=aa, signature_b64=asig, credential_id=cred_b64
    )
    assert assurance.phishing_resistant is True
    with pytest.raises(EnterpriseError):
        await svc.authenticate_passkey(
            client_data_b64=ac, authenticator_data_b64=aa, signature_b64=asig, credential_id="missing"
        )
    grant = await svc.issue_step_up(assurance, SensitiveAction.REMOVE_PASSKEY, org_id=None)
    await svc.remove_passkey(user_id=user_id, credential_row_id=rec["id"], session=assurance, grant=grant)
    auth_begin2 = await svc.begin_webauthn(user_id=user_id, session_id=assurance.session_id, ceremony="authenticate")
    ach2 = b64url_decode(auth_begin2["challenge"])
    ac2, aa2, asig2 = assertion_blob(rp_id="localhost", origin="http://localhost", challenge=ach2, private_key=key, sign_count=3)
    with pytest.raises(EnterpriseError):
        await svc.authenticate_passkey(
            client_data_b64=ac2, authenticator_data_b64=aa2, signature_b64=asig2, credential_id=cred_b64
        )


@pytest.mark.asyncio
async def test_totp_replay_and_removal_requires_step_up(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    started = await svc.start_totp(user_id)
    assert "otpauth_uri" in started
    from responsibleai.db.engine import human_totp_factors
    from sqlalchemy import select

    async with engine.raw.connect() as conn:
        secret = (await conn.execute(select(human_totp_factors.c.pending_secret_encrypted).where(human_totp_factors.c.user_id == user_id))).scalar()
    import pyotp

    code = pyotp.TOTP(secret).now()
    await svc.confirm_totp(user_id, code)
    with pytest.raises(EnterpriseError) as replay:
        await svc.verify_totp(user_id, code)
    assert replay.value.code == CHALLENGE_REPLAY
    _, _, session = await svc.issue_session(user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None)
    with pytest.raises(EnterpriseError) as step:
        await svc.remove_totp(user_id=user_id, session=session)
    assert step.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_recovery_codes_one_time_and_owner_email_only_blocked(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=None)
    codes = await svc.issue_recovery_codes(user_id, session=session, grant=grant)
    await svc.consume_recovery_code(user_id, codes[0])
    with pytest.raises(EnterpriseError):
        await svc.consume_recovery_code(user_id, codes[0])
    await svc.request_recovery("human@example.com")
    token = svc.last_recovery_token_for_tests
    # not privileged without org owner membership
    recovered = await svc.consume_recovery_token(token)
    assert recovered == user_id
    with pytest.raises(EnterpriseError):
        await svc.consume_recovery_token(token)

    from responsibleai.enterprise.service import Actor, EnterpriseIAM
    from responsibleai.rbac.models import Role

    iam = EnterpriseIAM(engine)
    owner = user_id
    org = await iam.create_workspace(actor_user_id=owner, name="Co", slug=f"co-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    await svc.request_recovery("human@example.com")
    token2 = svc.last_recovery_token_for_tests
    with pytest.raises(EnterpriseError) as review:
        await svc.consume_recovery_token(token2)
    assert review.value.code == RECOVERY_REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_google_forged_issuer_audience_nonce_hd(engine) -> None:
    user_id = await _user(engine)
    key, jwk = _rsa()
    svc = await _svc(engine, google_client_id="google-client")
    _, _, session = await _passkey_session(svc, user_id)

    async def _get(self, kid, allow_refresh=True):
        return jwk

    with patch("responsibleai.enterprise.security.oidc.TrustedJWKS.get", new=_get):
        good = _token(key, iss="https://accounts.google.com", aud="google-client", sub="sub-1", extra={"hd": "acme.com", "email": "a@acme.com"})
        claims = await OIDCTokenValidator(
            issuer="https://accounts.google.com", audience="google-client", jwks_url="https://www.googleapis.com/oauth2/v3/certs"
        ).validate(good, expected_nonce="n1")
        assert claims.hosted_domain == "acme.com"
        with pytest.raises(EnterpriseError):
            await OIDCTokenValidator(
                issuer="https://accounts.google.com", audience="google-client", jwks_url="https://www.googleapis.com/oauth2/v3/certs"
            ).validate(_token(key, iss="https://evil.example", aud="google-client", sub="sub-1"), expected_nonce="n1")
        with pytest.raises(EnterpriseError):
            await OIDCTokenValidator(
                issuer="https://accounts.google.com", audience="google-client", jwks_url="https://www.googleapis.com/oauth2/v3/certs"
            ).validate(_token(key, iss="https://accounts.google.com", aud="other", sub="sub-1"), expected_nonce="n1")
        with pytest.raises(EnterpriseError):
            await OIDCTokenValidator(
                issuer="https://accounts.google.com", audience="google-client", jwks_url="https://www.googleapis.com/oauth2/v3/certs"
            ).validate(good, expected_nonce="wrong")
        expired = _token(key, iss="https://accounts.google.com", aud="google-client", sub="sub-1", exp=int(time.time()) - 10)
        with pytest.raises(EnterpriseError):
            await OIDCTokenValidator(
                issuer="https://accounts.google.com", audience="google-client", jwks_url="https://www.googleapis.com/oauth2/v3/certs"
            ).validate(expired, expected_nonce="n1")
        none_tok = jwt.encode({"iss": "https://accounts.google.com", "aud": "google-client", "sub": "x", "exp": int(time.time()) + 60, "iat": int(time.time())}, "", algorithm="none", headers={"kid": "kid-1"})
        with pytest.raises(EnterpriseError):
            await OIDCTokenValidator(
                issuer="https://accounts.google.com", audience="google-client", jwks_url="https://www.googleapis.com/oauth2/v3/certs"
            ).validate(none_tok, expected_nonce="n1")

    # Personal Google cannot use company path; email domain is insufficient.
    personal = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="sub-p",
        audience="google-client",
        email="person@acme.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    from responsibleai.enterprise.service import EnterpriseIAM

    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(actor_user_id=user_id, name="Acme", slug=f"acme-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    svc.google_client_id = "google-client"
    with patch.object(IdentitySecurityService, "_binding", AsyncMock(return_value={"verified_domain": "acme.com", "tenant_id": None})):
        with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=personal)):
            with pytest.raises(EnterpriseError) as err:
                await svc.google_login(id_token="x.y.z", nonce="n1", intended_org_id=org["id"])
            assert err.value.code == GOOGLE_WORKSPACE_MISMATCH


@pytest.mark.asyncio
async def test_microsoft_wrong_tenant_and_personal_org_path(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine, microsoft_client_id="ms-client")
    from responsibleai.enterprise.service import EnterpriseIAM

    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(actor_user_id=user_id, name="Ent", slug=f"ent-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    personal = VerifiedIDToken(
        issuer="https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0",
        subject="oid-1",
        audience="ms-client",
        email="user@company.com",
        hosted_domain=None,
        tenant_id="9188040d-6c67-4c5b-b112-36a304b66dad",
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(IdentitySecurityService, "_binding", AsyncMock(return_value={"tenant_id": "tenant-real", "verified_domain": "company.com"})):
        with patch("responsibleai.enterprise.security.service._unverified_iss", return_value="https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0"):
            with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=personal)):
                with pytest.raises(EnterpriseError) as err:
                    await svc.microsoft_login(id_token="a.b.c", nonce="n1", intended_org_id=org["id"])
                assert err.value.code == ENTRA_TENANT_MISMATCH
    foreign = VerifiedIDToken(
        issuer="https://login.microsoftonline.com/foreign/v2.0",
        subject="oid-2",
        audience="ms-client",
        email="user@company.com",
        hosted_domain=None,
        tenant_id="foreign",
        nonce="n1",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    with patch.object(IdentitySecurityService, "_binding", AsyncMock(return_value={"tenant_id": "tenant-real", "verified_domain": "company.com"})):
        with patch("responsibleai.enterprise.security.service._unverified_iss", return_value="https://login.microsoftonline.com/foreign/v2.0"):
            with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=foreign)):
                with pytest.raises(EnterpriseError) as err:
                    await svc.microsoft_login(id_token="a.b.c", nonce="n1", intended_org_id=org["id"])
                assert err.value.code == ENTRA_TENANT_MISMATCH


@pytest.mark.asyncio
async def test_account_link_conflict_and_email_not_merge(engine) -> None:
    a = await _user(engine, "a@example.com")
    b = await _user(engine, "b@example.com")
    svc = await _svc(engine)
    _, _, session_a = await _passkey_session(svc, a)
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="same-sub",
        audience="c",
        email="shared@example.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n",
        expires_at=int(time.time()) + 9,
        raw={},
    )
    grant = await svc.issue_step_up(session_a, SensitiveAction.LINK_GOOGLE, org_id=None)
    await svc.link_provider(session=session_a, provider="GOOGLE", claims=claims, grant=grant, account_kind="PERSONAL")
    _, _, session_b = await _passkey_session(svc, b)
    grant_b = await svc.issue_step_up(session_b, SensitiveAction.LINK_GOOGLE, org_id=None)
    with pytest.raises(EnterpriseError) as conflict:
        await svc.link_provider(session=session_b, provider="GOOGLE", claims=claims, grant=grant_b, account_kind="PERSONAL")
    assert conflict.value.code == ACCOUNT_LINK_CONFLICT


@pytest.mark.asyncio
async def test_step_up_action_binding_and_stolen_session(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, low = await svc.issue_session(user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None)
    grant = await svc.issue_step_up(low, SensitiveAction.TRANSFER_OWNERSHIP, org_id=None)
    with pytest.raises(EnterpriseError):
        await svc.consume_step_up(low, SensitiveAction.CREATE_PRODUCTION_API_KEY, grant)
    _, _, high = await _passkey_session(svc, user_id)
    grant2 = await svc.issue_step_up(high, SensitiveAction.TRANSFER_OWNERSHIP, org_id=None)
    with pytest.raises(EnterpriseError):
        await svc.consume_step_up(low, SensitiveAction.TRANSFER_OWNERSHIP, grant2)
    await svc.consume_step_up(high, SensitiveAction.TRANSFER_OWNERSHIP, grant2)
    with pytest.raises(EnterpriseError):
        await svc.consume_step_up(high, SensitiveAction.TRANSFER_OWNERSHIP, grant2)


@pytest.mark.asyncio
async def test_session_revoke_and_suspension(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    token, csrf, assurance = await _passkey_session(svc, user_id)
    await svc.load_session(f"{token}.{csrf}")
    await svc.revoke_session(user_id=user_id, session_id=assurance.session_id)
    with pytest.raises(EnterpriseError):
        await svc.load_session(f"{token}.{csrf}")
    token2, csrf2, _ = await _passkey_session(svc, user_id)
    from sqlalchemy import update

    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == user_id).values(verification_status="SUSPENDED"))
    with pytest.raises(EnterpriseError):
        await svc.load_session(f"{token2}.{csrf2}")


@pytest.mark.asyncio
async def test_sso_required_blocks_password_and_downgrade(engine) -> None:
    user_id = await _user(engine)
    from responsibleai.enterprise.service import EnterpriseIAM

    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(actor_user_id=user_id, name="SSO Co", slug=f"sso-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    grant = await svc.issue_step_up(session, SensitiveAction.CONFIGURE_SSO, org_id=org["id"])
    await svc.configure_sso(
        org_id=org["id"],
        session=session,
        grant=grant,
        protocol="OIDC",
        issuer="https://login.microsoftonline.com/tenant/v2.0",
        client_id="cli",
        client_secret="secret-value-not-placeholder",
        redirect_uri="https://app.example.com/callback",
        enforcement="SSO_REQUIRED",
        provisioning="INVITE_ONLY",
    )
    with pytest.raises(EnterpriseError) as denied:
        await svc.authenticate_password("human@example.com", "correct-horse-battery-staple-9", org_id=org["id"])
    assert denied.value.code == SSO_REQUIRED
    grant2 = await svc.issue_step_up(session, SensitiveAction.CONFIGURE_SSO, org_id=org["id"])
    with pytest.raises(EnterpriseError) as down:
        await svc.configure_sso(
            org_id=org["id"],
            session=session,
            grant=grant2,
            protocol="OIDC",
            issuer="https://login.microsoftonline.com/tenant/v2.0",
            client_id="cli",
            client_secret="secret-value-not-placeholder",
            redirect_uri="https://app.example.com/callback",
            enforcement="SSO_OPTIONAL",
            provisioning="INVITE_ONLY",
        )
    assert down.value.code in {SECURITY_DOWNGRADE_BLOCKED, "FORBIDDEN"} or down.value.http_status in {403, 409}


@pytest.mark.asyncio
async def test_phone_is_not_strong_and_gate_b_closed() -> None:
    from responsibleai.enterprise.security.policy import AuthenticationSecurityPolicy, OrgAuthPolicy

    policy = AuthenticationSecurityPolicy()
    decision = policy.evaluate_login(
        methods=(AuthMethod.PHONE,),
        role="OWNER",
        org=OrgAuthPolicy(),
    )
    assert decision.allowed is False
    assert PRODUCTION_GATE_B_OPEN is False
    src = open("src/responsibleai/enterprise/security/service.py").read()
    assert "ExecutionAuthorization" not in src or "must not" in src
    assert "Sovereign" not in src


def test_production_preflight_rejects_placeholders(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_GOOGLE_CLIENT_ID", "changeme")
    monkeypatch.setenv("WHITEPACT_GOOGLE_CLIENT_SECRET", "secret")

    class S:
        environment = "production"
        is_production = True
        google_client_id = "changeme"

    with pytest.raises(Exception):
        assert_layer2_provider_boot_safe(S())


@pytest.mark.asyncio
async def test_unknown_kid_denies_after_refresh() -> None:
    key, jwk = _rsa()
    token = _token(key, iss="https://accounts.google.com", aud="c", sub="s", kid="unknown")

    async def empty(self, kid, allow_refresh=True):
        return None

    with patch("responsibleai.enterprise.security.oidc.TrustedJWKS.get", new=empty):
        with pytest.raises(EnterpriseError) as err:
            await OIDCTokenValidator(
                issuer="https://accounts.google.com", audience="c", jwks_url="https://www.googleapis.com/oauth2/v3/certs"
            ).validate(token, expected_nonce="n1")
        assert err.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_login_enumeration_uniform_unknown_email(engine) -> None:
    svc = await _svc(engine)
    a = await svc.authenticate_password("missing@example.com", "wrong")
    await _user(engine, "exists@example.com")
    b = await svc.authenticate_password("exists@example.com", "wrong-password-value")
    assert a is None and b is None
