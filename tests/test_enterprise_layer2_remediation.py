# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial coverage for Layer 2 identity-security remediation."""

from __future__ import annotations

import inspect
import logging
import time
import uuid
from unittest.mock import patch

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from sqlalchemy import insert, update

from responsibleai.db.engine import (
    create_engine,
    identity_oauth_transactions,
    web_memberships,
    web_users,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    PROVIDER_TOKEN_INVALID,
    RECOVERY_REVIEW_REQUIRED,
    EnterpriseError,
)
from responsibleai.enterprise.security.assurance import map_authentication_assurance
from responsibleai.enterprise.security.oidc import OIDCTokenValidator
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.preflight import assert_layer2_provider_boot_safe
from responsibleai.enterprise.security.providers import canonicalize_provider
from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import cose_ec2_uncompressed
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN, phase7a_dispatcher_flag_from_env


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _user(engine, email: str) -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


async def _svc(engine, **kwargs) -> IdentitySecurityService:
    return IdentitySecurityService(
        engine,
        rp_id="localhost",
        origin="http://localhost",
        hosted_redirect_uri="https://app.example.com/callback",
        **kwargs,
    )


def _rsa():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()
    import base64

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


def _token(key, *, iss, aud, sub, nonce="n1", extra=None, exp=None, kid="kid-1"):
    now = int(time.time())
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "iat": now,
        "exp": exp or now + 300,
        "nonce": nonce,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": kid})


@pytest.mark.asyncio
async def test_raw_hosted_id_token_rejected(engine) -> None:
    svc = await _svc(
        engine, google_client_id="google-client", google_client_secret="confidential-secret-value"
    )
    with pytest.raises(EnterpriseError) as err:
        await svc.google_login(id_token="a.b.c", nonce="n1")
    assert err.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_hosted_oauth_code_success_and_replays(engine) -> None:
    key, jwk = _rsa()
    svc = await _svc(
        engine,
        google_client_id="google-client",
        google_client_secret="confidential-secret-value",
    )
    started = await svc.begin_hosted_oauth(
        provider="GOOGLE", redirect_uri="https://app.example.com/callback"
    )
    token = _token(
        key,
        iss="https://accounts.google.com",
        aud="google-client",
        sub="sub-code",
        nonce=started["nonce"],
        extra={"email": "a@example.com"},
    )

    async def _get(self, kid, allow_refresh=True):
        return jwk

    async def _exchange(**kwargs):
        assert kwargs["code_verifier"]
        assert kwargs["client_secret"] == "confidential-secret-value"
        return {"id_token": token}

    with patch("responsibleai.enterprise.security.oidc.TrustedJWKS.get", new=_get):
        with patch(
            "responsibleai.enterprise.security.oauth.exchange_authorization_code", new=_exchange
        ):
            result = await svc.complete_hosted_oauth(
                provider="GOOGLE",
                state=started["state"],
                code="auth-code-1",
                redirect_uri="https://app.example.com/callback",
            )
            assert result["status"] == "UNLINKED_PROVIDER"
            with pytest.raises(EnterpriseError) as replay:
                await svc.complete_hosted_oauth(
                    provider="GOOGLE",
                    state=started["state"],
                    code="auth-code-1",
                    redirect_uri="https://app.example.com/callback",
                )
            assert replay.value.code in {PROVIDER_TOKEN_INVALID, "CHALLENGE_REPLAY"}


@pytest.mark.asyncio
async def test_hosted_oauth_invalid_state_pkce_nonce_redirect(engine) -> None:
    key, jwk = _rsa()
    svc = await _svc(
        engine, google_client_id="google-client", google_client_secret="confidential-secret-value"
    )
    started = await svc.begin_hosted_oauth(
        provider="GOOGLE", redirect_uri="https://app.example.com/callback"
    )

    async def _get(self, kid, allow_refresh=True):
        return jwk

    with pytest.raises(EnterpriseError):
        await svc.complete_hosted_oauth(
            provider="GOOGLE",
            state="not-the-state",
            code="code",
            redirect_uri="https://app.example.com/callback",
        )
    with pytest.raises(EnterpriseError):
        await svc.complete_hosted_oauth(
            provider="GOOGLE",
            state=started["state"],
            code="code",
            redirect_uri="https://evil.example/callback",
        )

    started2 = await svc.begin_hosted_oauth(
        provider="GOOGLE", redirect_uri="https://app.example.com/callback"
    )
    bad_nonce = _token(
        key, iss="https://accounts.google.com", aud="google-client", sub="s", nonce="wrong"
    )

    async def _exchange_bad(**kwargs):
        return {"id_token": bad_nonce}

    with patch("responsibleai.enterprise.security.oidc.TrustedJWKS.get", new=_get):
        with patch(
            "responsibleai.enterprise.security.oauth.exchange_authorization_code", new=_exchange_bad
        ):
            with pytest.raises(EnterpriseError):
                await svc.complete_hosted_oauth(
                    provider="GOOGLE",
                    state=started2["state"],
                    code="code-2",
                    redirect_uri="https://app.example.com/callback",
                )

    started3 = await svc.begin_hosted_oauth(
        provider="GOOGLE", redirect_uri="https://app.example.com/callback"
    )

    async def _exchange_pkce(**kwargs):
        raise EnterpriseError(
            PROVIDER_TOKEN_INVALID, "Authorization code exchange failed closed.", 401
        )

    with patch(
        "responsibleai.enterprise.security.oauth.exchange_authorization_code", new=_exchange_pkce
    ):
        with pytest.raises(EnterpriseError) as err:
            await svc.complete_hosted_oauth(
                provider="GOOGLE",
                state=started3["state"],
                code="code-3",
                redirect_uri="https://app.example.com/callback",
            )
        assert err.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_hosted_oauth_expired_and_jwks_fail_closed(engine, caplog) -> None:
    svc = await _svc(
        engine, google_client_id="google-client", google_client_secret="confidential-secret-value"
    )
    started = await svc.begin_hosted_oauth(
        provider="GOOGLE", redirect_uri="https://app.example.com/callback"
    )
    import hashlib

    digest = hashlib.sha256(started["state"].encode()).hexdigest()
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(identity_oauth_transactions)
            .where(identity_oauth_transactions.c.state_hash == digest)
            .values(expires_at="2000-01-01T00:00:00+00:00")
        )
    with pytest.raises(EnterpriseError):
        await svc.complete_hosted_oauth(
            provider="GOOGLE",
            state=started["state"],
            code="late",
            redirect_uri="https://app.example.com/callback",
        )

    started2 = await svc.begin_hosted_oauth(
        provider="GOOGLE", redirect_uri="https://app.example.com/callback"
    )
    key, _jwk = _rsa()
    token = _token(
        key,
        iss="https://accounts.google.com",
        aud="google-client",
        sub="s",
        nonce=started2["nonce"],
    )

    async def empty(self, kid, allow_refresh=True):
        raise RuntimeError("jwks down")

    async def _exchange(**kwargs):
        return {"id_token": token}

    caplog.set_level(logging.WARNING)
    with patch("responsibleai.enterprise.security.oidc.TrustedJWKS.get", new=empty):
        with patch(
            "responsibleai.enterprise.security.oauth.exchange_authorization_code", new=_exchange
        ):
            with pytest.raises(EnterpriseError):
                await svc.complete_hosted_oauth(
                    provider="GOOGLE",
                    state=started2["state"],
                    code="code-jwks",
                    redirect_uri="https://app.example.com/callback",
                )
    joined = " ".join(rec.getMessage() for rec in caplog.records)
    assert "id_token" not in joined
    assert token not in joined
    assert "confidential-secret-value" not in joined


@pytest.mark.asyncio
async def test_distributed_rate_limit_shared_and_fail_closed(engine) -> None:
    a = DurableIdentityRateLimiter(engine)
    b = DurableIdentityRateLimiter(engine)
    await a.check("login:shared@example.com", limit=2, window_seconds=60)
    await b.check("login:shared@example.com", limit=2, window_seconds=60)
    with pytest.raises(EnterpriseError) as err:
        await a.check("login:shared@example.com", limit=2, window_seconds=60)
    assert err.value.code == "RATE_LIMITED"

    from sqlalchemy.exc import SQLAlchemyError

    class FakeRaw:
        def begin(self):
            raise SQLAlchemyError("storage down")

    class FakeEngine:
        raw = FakeRaw()

    broken = DurableIdentityRateLimiter(FakeEngine())  # type: ignore[arg-type]
    with pytest.raises(EnterpriseError) as unavailable:
        await broken.check("recovery:owner@example.com", limit=5, window_seconds=60)
    assert unavailable.value.code == "IDENTITY_PROTECTION_UNAVAILABLE"


def test_assurance_evidence_not_org_policy() -> None:
    totp = map_authentication_assurance(
        methods=(AuthMethod.TOTP,), org_policy_claims_phishing_resistant=True
    )
    assert totp.phishing_resistant is False
    sso = map_authentication_assurance(
        methods=(AuthMethod.ENTERPRISE_SSO,), org_policy_claims_phishing_resistant=True
    )
    assert sso.phishing_resistant is False
    sso_hwk = map_authentication_assurance(methods=(AuthMethod.ENTERPRISE_SSO,), amr=("hwk",))
    assert sso_hwk.phishing_resistant is True
    unknown = map_authentication_assurance(
        methods=(AuthMethod.ENTERPRISE_SSO,), amr=("mfa",), acr="https://refeds.org/profile/mfa"
    )
    assert unknown.phishing_resistant is False
    passkey = map_authentication_assurance(methods=(AuthMethod.PASSKEY_UV,), webauthn_uv=True)
    assert passkey.phishing_resistant is True


@pytest.mark.asyncio
async def test_privileged_action_rejects_low_assurance(engine) -> None:
    user_id = await _user(engine, "low@example.com")
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    grant = await svc.issue_step_up(session, SensitiveAction.TRANSFER_OWNERSHIP, org_id=None)
    with pytest.raises(EnterpriseError) as err:
        await svc.consume_step_up(session, SensitiveAction.TRANSFER_OWNERSHIP, grant)
    assert err.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"


@pytest.mark.asyncio
async def test_four_eyes_workflow(engine) -> None:
    from responsibleai.enterprise.service import EnterpriseIAM

    owner = await _user(engine, "owner@example.com")
    checker = await _user(engine, "checker@example.com")
    outsider = await _user(engine, "out@example.com")
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Four", slug=f"four-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(web_memberships).values(
                id=str(uuid.uuid4()),
                user_id=checker,
                org_id=org["id"],
                role="SECURITY_ADMIN",
                status="ACTIVE",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    svc = await _svc(engine)
    _, _, requester = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org["id"],
        ip_label=None,
        user_agent=None,
    )
    _, _, approver = await svc.issue_session(
        user_id=checker,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org["id"],
        ip_label=None,
        user_agent=None,
    )
    _, _, foreign = await svc.issue_session(
        user_id=outsider,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=None,
        ip_label=None,
        user_agent=None,
    )
    params = {"org_id": org["id"], "enforcement": "SSO_OPTIONAL"}
    rec = await svc.four_eyes.request(
        org_id=org["id"],
        requester=requester,
        action=SensitiveAction.DISABLE_REQUIRED_SSO.value,
        parameters=params,
    )
    with pytest.raises(EnterpriseError) as self_approve:
        await svc.four_eyes.approve(org_id=org["id"], request_id=rec.id, approver=requester)
    assert self_approve.value.code == "SELF_APPROVAL_BLOCKED"
    with pytest.raises(EnterpriseError):
        await svc.four_eyes.approve(org_id=org["id"], request_id=rec.id, approver=foreign)
    await svc.four_eyes.approve(org_id=org["id"], request_id=rec.id, approver=approver)
    mutated = dict(params)
    mutated["enforcement"] = "changed"
    with pytest.raises(EnterpriseError) as mutation:
        await svc.four_eyes.consume(
            org_id=org["id"],
            request_id=rec.id,
            action=SensitiveAction.DISABLE_REQUIRED_SSO.value,
            parameters=mutated,
        )
    assert mutation.value.code == "FOUR_EYES_MUTATION"
    await svc.four_eyes.consume(
        org_id=org["id"],
        request_id=rec.id,
        action=SensitiveAction.DISABLE_REQUIRED_SSO.value,
        parameters=params,
    )
    with pytest.raises(EnterpriseError) as second:
        await svc.four_eyes.consume(
            org_id=org["id"],
            request_id=rec.id,
            action=SensitiveAction.DISABLE_REQUIRED_SSO.value,
            parameters=params,
        )
    assert second.value.code == "FOUR_EYES_REPLAY"


@pytest.mark.asyncio
async def test_four_eyes_expiry_and_suspension(engine) -> None:
    from responsibleai.enterprise.service import EnterpriseIAM

    owner = await _user(engine, "own2@example.com")
    checker = await _user(engine, "chk2@example.com")
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Exp", slug=f"exp-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(web_memberships).values(
                id=str(uuid.uuid4()),
                user_id=checker,
                org_id=org["id"],
                role="SECURITY_ADMIN",
                status="ACTIVE",
                created_at="2026-01-01T00:00:00+00:00",
            )
        )
    svc = await _svc(engine)
    _, _, requester = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org["id"],
        ip_label=None,
        user_agent=None,
    )
    _, _, approver = await svc.issue_session(
        user_id=checker,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org["id"],
        ip_label=None,
        user_agent=None,
    )
    rec = await svc.four_eyes.request(
        org_id=org["id"],
        requester=requester,
        action=SensitiveAction.DISABLE_REQUIRED_SSO.value,
        parameters={"x": 1},
        ttl_minutes=0,
    )
    with pytest.raises(EnterpriseError) as expired:
        await svc.four_eyes.approve(org_id=org["id"], request_id=rec.id, approver=approver)
    assert expired.value.code == "FOUR_EYES_EXPIRED"

    rec2 = await svc.four_eyes.request(
        org_id=org["id"],
        requester=requester,
        action=SensitiveAction.DISABLE_REQUIRED_SSO.value,
        parameters={"x": 2},
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == checker)
            .values(verification_status="SUSPENDED")
        )
    with pytest.raises(EnterpriseError) as suspended:
        await svc.four_eyes.approve(org_id=org["id"], request_id=rec2.id, approver=approver)
    assert suspended.value.code == "FOUR_EYES_PRINCIPAL_REVOKED"


@pytest.mark.asyncio
async def test_provider_alias_and_email_not_identity(engine) -> None:
    assert canonicalize_provider("google_oidc") == "GOOGLE"
    assert canonicalize_provider("Google") == "GOOGLE"
    a = await _user(engine, "a2@example.com")
    b = await _user(engine, "b2@example.com")
    svc = await _svc(engine)
    _, _, sa = await svc.issue_session(
        user_id=a, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    from responsibleai.enterprise.security.oidc import VerifiedIDToken

    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="sub-alias",
        audience="c",
        email="shared@example.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n",
        expires_at=int(time.time()) + 9,
        raw={},
    )
    grant = await svc.issue_step_up(sa, SensitiveAction.LINK_GOOGLE, org_id=None)
    await svc.link_provider(
        session=sa, provider="google_oidc", claims=claims, grant=grant, account_kind="PERSONAL"
    )
    other = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="other-sub",
        audience="c",
        email="shared@example.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n",
        expires_at=int(time.time()) + 9,
        raw={},
    )
    _, _, sb = await svc.issue_session(
        user_id=b, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    grant_b = await svc.issue_step_up(sb, SensitiveAction.LINK_GOOGLE, org_id=None)
    await svc.link_provider(
        session=sb, provider="GOOGLE", claims=other, grant=grant_b, account_kind="PERSONAL"
    )


@pytest.mark.asyncio
async def test_password_session_cannot_enroll_passkey(engine) -> None:
    user_id = await _user(engine, "pw@example.com")
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    begin = await svc.begin_webauthn(
        user_id=user_id, session_id=session.session_id, ceremony="register"
    )

    from responsibleai.enterprise.security.webauthn import b64url_decode
    from tests.webauthn_fakes import registration_blob

    challenge = b64url_decode(begin["challenge"])
    key = generate_private_key(SECP256R1())
    cdata, adata, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    with pytest.raises(EnterpriseError) as err:
        await svc.finish_passkey_registration(
            user_id=user_id, session=session, client_data_b64=cdata, authenticator_data_b64=adata
        )
    assert err.value.code == "STEP_UP_REQUIRED"
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as low:
        await svc.finish_passkey_registration(
            user_id=user_id,
            session=session,
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            grant=grant,
        )
    assert low.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"


def test_unsupported_webauthn_algorithm_rejected() -> None:
    import cbor2

    cose = cbor2.dumps({1: 2, 3: -35, -1: 2, -2: b"\x00" * 48, -3: b"\x00" * 48})
    with pytest.raises(ValueError, match="Only ES256"):
        cose_ec2_uncompressed(cose)


@pytest.mark.asyncio
async def test_privileged_recovery_requires_recovery_code(engine) -> None:
    from responsibleai.enterprise.service import EnterpriseIAM

    user_id = await _user(engine, "rec@example.com")
    iam = EnterpriseIAM(engine)
    await iam.create_workspace(
        actor_user_id=user_id, name="Rec", slug=f"rec-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=None)
    codes = await svc.issue_recovery_codes(user_id, session=session, grant=grant)
    await svc.request_recovery("rec@example.com")
    token = svc.last_recovery_token_for_tests
    with pytest.raises(EnterpriseError) as blocked:
        await svc.consume_recovery_token(token)
    assert blocked.value.code == RECOVERY_REVIEW_REQUIRED
    recovered = await svc.consume_recovery_token(token, recovery_code=codes[0])
    assert recovered == user_id


def test_production_preflight_requires_webauthn_and_rejects_raw_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_OIDC_ALLOW_RAW_ID_TOKEN", "true")

    class S:
        environment = "production"
        is_production = True
        webauthn_origin = ""
        webauthn_rp_id = ""

    from responsibleai.enterprise.preflight import HostedEnterpriseSecurityError

    with pytest.raises(HostedEnterpriseSecurityError):
        assert_layer2_provider_boot_safe(S())


def test_gate_b_closed_and_identity_cannot_mint_execution() -> None:
    assert PRODUCTION_GATE_B_OPEN is False
    assert phase7a_dispatcher_flag_from_env() is False
    src = inspect.getsource(IdentitySecurityService)
    assert "ExecutionAuthorization(" not in src
    from responsibleai.governance.execution import authorize_execution

    assert "enterprise.security" not in inspect.getsource(authorize_execution)


@pytest.mark.asyncio
async def test_wrong_issuer_audience_in_hosted_validator() -> None:
    key, jwk = _rsa()

    async def _get(self, kid, allow_refresh=True):
        return jwk

    with patch("responsibleai.enterprise.security.oidc.TrustedJWKS.get", new=_get):
        validator = OIDCTokenValidator(
            issuer="https://accounts.google.com",
            audience="google-client",
            jwks_url="https://www.googleapis.com/oauth2/v3/certs",
        )
        good = _token(
            key, iss="https://accounts.google.com", aud="google-client", sub="s", nonce="n"
        )
        await validator.validate(good, expected_nonce="n")
        with pytest.raises(EnterpriseError):
            await validator.validate(
                _token(key, iss="https://evil.example", aud="google-client", sub="s", nonce="n"),
                expected_nonce="n",
            )
        with pytest.raises(EnterpriseError):
            await validator.validate(
                _token(key, iss="https://accounts.google.com", aud="other", sub="s", nonce="n"),
                expected_nonce="n",
            )
