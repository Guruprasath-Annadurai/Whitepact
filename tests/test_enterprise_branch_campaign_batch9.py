# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 9 branch-coverage: enterprise IAM transitions, identity security deny paths,
Layer 2 preflight, and WebAuthn ceremony validation failures."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import cbor2
import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from sqlalchemy import insert, update

from responsibleai.db.engine import (
    create_engine,
    org_api_key_metadata,
    org_api_keys,
    step_up_grants,
    web_invitations,
    web_memberships,
    web_users,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    API_KEY_ISSUANCE_NOT_ALLOWED,
    FORBIDDEN,
    INVITE_REPLAY,
    KEY_EXPIRED,
    KEY_REVOKED,
    LAST_AUTH_METHOD,
    LAST_OWNER,
    MFA_REQUIRED,
    PROVIDER_TOKEN_INVALID,
    SECURITY_DOWNGRADE_BLOCKED,
    SERVICE_ACCOUNT_FORBIDDEN,
    STEP_UP_REQUIRED,
    VERIFICATION_SUSPENDED,
    WEBAUTHN_INVALID,
    WRONG_ENVIRONMENT,
    EnterpriseError,
)
from responsibleai.enterprise.preflight import HostedEnterpriseSecurityError
from responsibleai.enterprise.security.oidc import VerifiedIDToken
from responsibleai.enterprise.security.policy import AuthMethod, OrgAuthPolicy, SensitiveAction
from responsibleai.enterprise.security.preflight import assert_layer2_provider_boot_safe
from responsibleai.enterprise.security.service import (
    IdentitySecurityService,
    _hash,
    _iso,
    _now,
)
from responsibleai.enterprise.security.webauthn import (
    b64url_decode,
    b64url_encode,
    cose_ec2_uncompressed,
    parse_auth_data,
    parse_client_data,
    public_key_from_uncompressed,
    rp_id_hash,
    verify_assertion,
    verify_registration,
)
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.enterprise.verification import HmacVerificationProvider, VerificationService
from responsibleai.rbac.models import Role
from tests.webauthn_fakes import assertion_blob, client_data, registration_blob


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
    return await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label="203.0.113.9", user_agent="test"
    )


def _actor(
    user_id: str,
    org_id: str,
    role: Role,
    *,
    membership_status: str = "ACTIVE",
    actor_type: str = "human",
    scopes: frozenset[str] = frozenset(),
    environment_id: str | None = None,
) -> Actor:
    return Actor(
        actor_type=actor_type,
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        membership_status=membership_status,
        scopes=scopes,
        environment_id=environment_id,
    )


async def _org(engine, owner_id: str) -> str:
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner_id,
        name="Batch9 Org",
        slug=f"b9-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    return org["id"]


async def _verify_human(engine, user_id: str) -> None:
    provider = HmacVerificationProvider("test-webhook-secret")
    verification = VerificationService(engine, provider)
    body = {
        "event_id": f"evt-{uuid.uuid4().hex[:8]}",
        "subject_id": user_id,
        "outcome": "VERIFIED",
        "assurance_level": "government_id",
    }
    ts = datetime.now(UTC).isoformat()
    payload = json.dumps(body, separators=(",", ":")).encode()
    signature = hmac.new(b"test-webhook-secret", payload + ts.encode(), hashlib.sha256).hexdigest()
    await verification.apply_provider_event(
        payload=payload, signature=signature, timestamp=ts, expected_user_id=user_id
    )


async def _issue_dev_key(iam: EnterpriseIAM, actor: Actor, org_id: str) -> tuple[dict, str]:
    envs = await iam.list_environments(actor, org_id)
    env_id = next(e["id"] for e in envs if e["type"] == "DEVELOPMENT")
    allowed = MagicMock()
    allowed.allowed = True
    allowed.reason_code = "OK"
    allowed.message = "ok"
    allowed.accountable_human_user_id = actor.user_id
    with patch(
        "responsibleai.enterprise.eligibility.EligibilityGate.may_issue_api_key",
        return_value=allowed,
    ):
        return await iam.create_api_key(
            actor,
            org_id,
            name="batch9",
            environment_id=env_id,
            scopes=("governance:read",),
            expires_at=None,
        )


def _claims(**kwargs) -> VerifiedIDToken:
    base = {
        "issuer": "https://accounts.google.com",
        "subject": "sub-1",
        "audience": "client",
        "email": "u@example.com",
        "hosted_domain": None,
        "tenant_id": None,
        "nonce": "n",
        "expires_at": int(time.time()) + 120,
        "raw": {},
    }
    base.update(kwargs)
    return VerifiedIDToken(**base)


# ── security/webauthn.py deny paths ──────────────────────────────────────────


def test_webauthn_parse_client_data_rejects_malformed_json() -> None:
    bad = b64url_encode(b"{not-json")
    with pytest.raises(ValueError, match="Malformed"):
        parse_client_data(bad)


def test_webauthn_parse_auth_data_rejects_short_buffer() -> None:
    with pytest.raises(ValueError, match="too short"):
        parse_auth_data(b"\x00" * 10)


def test_webauthn_parse_auth_data_rejects_truncated_attestation() -> None:
    flags = 0x40  # AT
    short = rp_id_hash("localhost") + bytes([flags]) + (0).to_bytes(4, "big")
    with pytest.raises(ValueError, match="truncated"):
        parse_auth_data(short)


def test_webauthn_cose_rejects_non_map() -> None:
    with pytest.raises(ValueError, match="not a map"):
        cose_ec2_uncompressed(cbor2.dumps(["not", "a", "map"]))


def test_webauthn_cose_rejects_non_p256_key() -> None:
    cose = cbor2.dumps({1: 2, 3: -35, -1: 2, -2: b"\x00" * 48, -3: b"\x00" * 48})
    with pytest.raises(ValueError, match="Only ES256"):
        cose_ec2_uncompressed(cose)


def test_webauthn_public_key_rejects_wrong_length() -> None:
    with pytest.raises(ValueError, match="uncompressed"):
        public_key_from_uncompressed(b"\x04" + b"\x00" * 10)


def test_webauthn_verify_assertion_type_mismatch() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, adata, sig = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )[:3]
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="ceremony type"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=sig,
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=True,
            previous_sign_count=0,
        )


def test_webauthn_verify_assertion_origin_mismatch() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, adata, sig = assertion_blob(
        rp_id="localhost", origin="https://evil.example", challenge=challenge, private_key=key
    )
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="origin mismatch"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=sig,
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=True,
            previous_sign_count=0,
        )


def test_webauthn_verify_assertion_challenge_mismatch() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, adata, sig = assertion_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="challenge mismatch"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=sig,
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=b"other-challenge",
            require_uv=True,
            previous_sign_count=0,
        )


def test_webauthn_verify_assertion_rp_id_hash_mismatch() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, adata, sig = assertion_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="RP ID"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=sig,
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="evil.example",
            expected_challenge=challenge,
            require_uv=True,
            previous_sign_count=0,
        )


def test_webauthn_verify_assertion_requires_user_present() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata = client_data(typ="webauthn.get", origin="http://localhost", challenge=challenge)
    flags = 0x04  # UV only, no UP
    adata = b64url_encode(rp_id_hash("localhost") + bytes([flags]) + (1).to_bytes(4, "big"))
    sig = b64url_encode(b"\x00" * 64)
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="user-present"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=sig,
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=False,
            previous_sign_count=0,
        )


def test_webauthn_verify_assertion_requires_uv_when_policy_demands() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, _, _ = assertion_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    flags = 0x01  # UP without UV
    adata = b64url_encode(rp_id_hash("localhost") + bytes([flags]) + (1).to_bytes(4, "big"))
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="user verification"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=b64url_encode(b"\x00" * 64),
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=True,
            previous_sign_count=0,
        )


def test_webauthn_verify_assertion_rejects_stale_sign_count() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, adata, sig = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=challenge,
        private_key=key,
        sign_count=1,
    )
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="sign count"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=sig,
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=True,
            previous_sign_count=5,
        )


def test_webauthn_verify_assertion_rejects_bad_signature() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, adata, _sig = assertion_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    pub_uncompressed = (
        b"\x04"
        + key.private_numbers().public_numbers.x.to_bytes(32, "big")
        + key.private_numbers().public_numbers.y.to_bytes(32, "big")
    )
    with pytest.raises(ValueError, match="signature invalid"):
        verify_assertion(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            signature_b64=b64url_encode(b"\x00" * 64),
            public_key_uncompressed=pub_uncompressed,
            expected_type="webauthn.get",
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=True,
            previous_sign_count=0,
        )


def test_webauthn_verify_registration_wrong_ceremony_type() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    _, adata, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    cdata_get = client_data(typ="webauthn.get", origin="http://localhost", challenge=challenge)
    with pytest.raises(ValueError, match="Registration ceremony"):
        verify_registration(
            client_data_b64=cdata_get,
            authenticator_data_b64=adata,
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=True,
        )


def test_webauthn_verify_registration_missing_attested_credential() -> None:
    key = generate_private_key(SECP256R1())
    challenge = b"challenge-bytes-1234567890"
    cdata, _, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    flags = 0x01 | 0x04  # UP|UV without AT
    adata = b64url_encode(rp_id_hash("localhost") + bytes([flags]) + (0).to_bytes(4, "big"))
    with pytest.raises(ValueError, match="Attested credential"):
        verify_registration(
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            expected_origin="http://localhost",
            expected_rp_id="localhost",
            expected_challenge=challenge,
            require_uv=True,
        )


# ── security/preflight.py deny paths ─────────────────────────────────────────


def test_layer2_preflight_rejects_oidc_skip_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_OIDC_SKIP_VERIFICATION", "true")

    class S:
        environment = "production"
        is_production = True

    with pytest.raises(HostedEnterpriseSecurityError, match="skip_verification"):
        assert_layer2_provider_boot_safe(S())


def test_layer2_preflight_rejects_raw_id_token_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_OIDC_ALLOW_RAW_ID_TOKEN", "yes")

    class S:
        environment = "production"
        is_production = True

    with pytest.raises(HostedEnterpriseSecurityError, match="raw id_token"):
        assert_layer2_provider_boot_safe(S())


def test_layer2_preflight_rejects_microsoft_placeholder_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_MICROSOFT_CLIENT_ID", "real-ms-client-id-value")
    monkeypatch.setenv("WHITEPACT_MICROSOFT_CLIENT_SECRET", "changeme")

    class S:
        environment = "production"
        is_production = True

    with pytest.raises(HostedEnterpriseSecurityError, match="Microsoft"):
        assert_layer2_provider_boot_safe(S())


def test_layer2_preflight_rejects_non_https_oauth_callback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_GOOGLE_CLIENT_ID", "real-google-client-id")
    monkeypatch.setenv("WHITEPACT_GOOGLE_CLIENT_SECRET", "sixteen-plus-char-secret")
    monkeypatch.setenv("WHITEPACT_OIDC_REDIRECT_URI", "http://insecure.example/callback")

    class S:
        environment = "production"
        is_production = True

    with pytest.raises(HostedEnterpriseSecurityError, match="HTTPS"):
        assert_layer2_provider_boot_safe(S())


def test_layer2_preflight_requires_field_encryption_with_providers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_GOOGLE_CLIENT_ID", "real-google-client-id")
    monkeypatch.setenv("WHITEPACT_GOOGLE_CLIENT_SECRET", "sixteen-plus-char-secret")
    monkeypatch.delenv("WHITEPACT_FIELD_ENCRYPTION_KEY", raising=False)

    class S:
        environment = "production"
        is_production = True
        webauthn_origin = "https://app.example.com"
        webauthn_rp_id = "app.example.com"

    with patch(
        "responsibleai.enterprise.security.preflight.field_encryption_is_configured",
        return_value=False,
    ):
        with pytest.raises(HostedEnterpriseSecurityError, match="FIELD_ENCRYPTION"):
            assert_layer2_provider_boot_safe(S())


def test_layer2_preflight_webauthn_origin_must_be_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")

    class S:
        environment = "production"
        is_production = True
        webauthn_origin = "http://insecure.example.com"
        webauthn_rp_id = "insecure.example.com"

    with patch(
        "responsibleai.enterprise.security.preflight.field_encryption_is_configured",
        return_value=True,
    ):
        with pytest.raises(HostedEnterpriseSecurityError, match="WebAuthn origin"):
            assert_layer2_provider_boot_safe(S())


def test_layer2_preflight_rejects_short_session_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_SESSION_SECRET", "too-short")

    class S:
        environment = "production"
        is_production = True
        webauthn_origin = "https://app.example.com"
        webauthn_rp_id = "app.example.com"

    with patch(
        "responsibleai.enterprise.security.preflight.field_encryption_is_configured",
        return_value=True,
    ):
        with pytest.raises(HostedEnterpriseSecurityError, match="session secret"):
            assert_layer2_provider_boot_safe(S())


# ── enterprise/security/service.py deny paths ────────────────────────────────


@pytest.mark.asyncio
async def test_security_link_provider_requires_step_up(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.link_provider(
            session=session,
            provider="GOOGLE",
            claims=_claims(),
            grant=None,
            account_kind="PERSONAL",
        )
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_consume_step_up_expired_grant(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(step_up_grants)
            .where(step_up_grants.c.grant_hash == _hash(grant))
            .values(expires_at=_iso(_now() - timedelta(minutes=1)))
        )
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_step_up(session, SensitiveAction.ADD_PASSKEY, grant)
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_consume_step_up_wrong_action_binding(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_step_up(session, SensitiveAction.REMOVE_PASSKEY, grant)
    assert exc.value.code == STEP_UP_REQUIRED
    assert "different action" in exc.value.message


@pytest.mark.asyncio
async def test_security_confirm_totp_without_pending_enrollment(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.confirm_totp(user_id, "123456")
    assert exc.value.code == MFA_REQUIRED


@pytest.mark.asyncio
async def test_security_remove_passkey_unknown_credential(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    grant = await svc.issue_step_up(session, SensitiveAction.REMOVE_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.remove_passkey(
            user_id=user_id,
            credential_row_id=str(uuid.uuid4()),
            session=session,
            grant=grant,
        )
    assert exc.value.code == WEBAUTHN_INVALID


@pytest.mark.asyncio
async def test_security_remove_passkey_last_strong_factor_blocked(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org_id,
        ip_label="203.0.113.9",
        user_agent="test",
    )
    begin = await svc.begin_webauthn(
        user_id=owner, session_id=session.session_id, ceremony="register"
    )
    challenge = b64url_decode(begin["challenge"])
    key = generate_private_key(SECP256R1())
    cdata, adata, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    grant_add = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=org_id)
    rec = await svc.finish_passkey_registration(
        user_id=owner,
        session=session,
        client_data_b64=cdata,
        authenticator_data_b64=adata,
        grant=grant_add,
    )
    grant_rm = await svc.issue_step_up(session, SensitiveAction.REMOVE_PASSKEY, org_id=org_id)
    strict_org = OrgAuthPolicy(phishing_resistant_required=True)
    with patch.object(svc, "_org_policy", AsyncMock(return_value=strict_org)):
        with pytest.raises(EnterpriseError) as exc:
            await svc.remove_passkey(
                user_id=owner,
                credential_row_id=rec["id"],
                session=session,
                grant=grant_rm,
            )
    assert exc.value.code == LAST_AUTH_METHOD


@pytest.mark.asyncio
async def test_security_remove_totp_blocks_last_factor_downgrade(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    await svc.start_totp(owner)
    import pyotp
    from sqlalchemy import select

    from responsibleai.db.engine import human_totp_factors

    async with engine.raw.connect() as conn:
        secret = (
            await conn.execute(
                select(human_totp_factors.c.pending_secret_encrypted).where(
                    human_totp_factors.c.user_id == owner
                )
            )
        ).scalar()
    await svc.confirm_totp(owner, pyotp.TOTP(secret).now())
    _, _, session = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org_id,
        ip_label="203.0.113.9",
        user_agent="test",
    )
    grant = await svc.issue_step_up(session, SensitiveAction.DISABLE_MFA, org_id=org_id)
    strict_org = OrgAuthPolicy(phishing_resistant_required=True)
    with patch.object(svc, "_org_policy", AsyncMock(return_value=strict_org)):
        with pytest.raises(EnterpriseError) as exc:
            await svc.remove_totp(user_id=owner, session=session, grant=grant)
    assert exc.value.code == SECURITY_DOWNGRADE_BLOCKED


@pytest.mark.asyncio
async def test_security_issue_recovery_codes_requires_step_up(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.issue_recovery_codes(user_id, session=session, grant=None)
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_begin_hosted_oauth_microsoft_missing_secret(engine) -> None:
    svc = await _svc(engine, microsoft_client_id="ms", microsoft_client_secret=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.begin_hosted_oauth(provider="microsoft", redirect_uri="https://app/cb")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_security_assert_membership_denies_unknown_org_member(engine) -> None:
    user_id = await _user(engine)
    owner = await _user(engine, "owner@example.com")
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc._assert_membership(user_id, org_id)
    assert exc.value.code == "SSO_TENANT_MISMATCH"


# ── enterprise/service.py deny paths ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_iam_accept_invitation_replay_after_accepted(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    guest = await _user(engine, "guest@example.com")
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    _, token = await iam.invite_member(actor, org_id, email="guest@example.com", role=Role.VIEWER)
    await iam.accept_invitation(token=token, user_id=guest)
    with pytest.raises(EnterpriseError) as exc:
        await iam.accept_invitation(token=token, user_id=guest)
    assert exc.value.code == INVITE_REPLAY


@pytest.mark.asyncio
async def test_iam_accept_invitation_unacceptable_status(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    guest = await _user(engine, "guest2@example.com")
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    inv_id, token = await iam.invite_member(
        actor, org_id, email="guest2@example.com", role=Role.VIEWER
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_invitations).where(web_invitations.c.id == inv_id).values(status="CANCELLED")
        )
    with pytest.raises(EnterpriseError) as exc:
        await iam.accept_invitation(token=token, user_id=guest)
    assert exc.value.code == FORBIDDEN
    assert "not acceptable" in exc.value.message.lower()


@pytest.mark.asyncio
async def test_iam_change_role_noop_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.change_role(actor, org_id, user_id=owner, role=Role.OWNER)
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_revoke_co_owner_requires_owner_actor(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    co = await _user(engine, "co@example.com")
    org_id = await _org(engine, owner)
    owner_actor = _actor(owner, org_id, Role.OWNER)
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(web_memberships).values(
                id=str(uuid.uuid4()),
                user_id=co,
                org_id=org_id,
                role=Role.OWNER.value,
                status="ACTIVE",
                invited_by_user_id=owner,
                accepted_at=now,
                created_at=now,
                updated_at=now,
            )
        )
    admin = await _user(engine, "admin@example.com")
    _, admin_tok = await iam.invite_member(
        owner_actor, org_id, email="admin@example.com", role=Role.ADMIN
    )
    await iam.accept_invitation(token=admin_tok, user_id=admin)
    admin_actor = _actor(admin, org_id, Role.ADMIN)
    with pytest.raises(EnterpriseError) as exc:
        await iam.revoke_member(admin_actor, org_id, user_id=co)
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_create_api_key_denies_non_human_actor(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    envs = await iam.list_environments(_actor(owner, org_id, Role.OWNER), org_id)
    env_id = envs[0]["id"]
    api_actor = Actor(
        actor_type="api_key",
        actor_id="k",
        user_id=owner,
        org_id=org_id,
        role=Role.DEVELOPER,
        membership_status="ACTIVE",
        environment_id=env_id,
    )
    with pytest.raises(EnterpriseError) as exc:
        await iam.create_api_key(
            api_actor,
            org_id,
            name="x",
            environment_id=env_id,
            scopes=("governance:read",),
            expires_at=None,
        )
    assert exc.value.code == API_KEY_ISSUANCE_NOT_ALLOWED


@pytest.mark.asyncio
async def test_iam_create_api_key_eligibility_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    envs = await iam.list_environments(actor, org_id)
    env_id = next(e["id"] for e in envs if e["type"] == "DEVELOPMENT")
    denied = MagicMock()
    denied.allowed = False
    denied.reason_code = "IDENTITY_VERIFICATION_REQUIRED"
    denied.message = "denied"
    denied.accountable_human_user_id = None
    with patch(
        "responsibleai.enterprise.eligibility.EligibilityGate.may_issue_api_key",
        return_value=denied,
    ):
        with pytest.raises(EnterpriseError) as exc:
            await iam.create_api_key(
                actor,
                org_id,
                name="x",
                environment_id=env_id,
                scopes=("governance:read",),
                expires_at=None,
            )
    assert exc.value.code == "IDENTITY_VERIFICATION_REQUIRED"


@pytest.mark.asyncio
async def test_iam_rotate_revoked_api_key_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    record, _secret = await _issue_dev_key(iam, actor, org_id)
    await iam.revoke_api_key(actor, org_id, record["id"])
    with pytest.raises(EnterpriseError) as exc:
        await iam.rotate_api_key(actor, org_id, record["id"])
    assert exc.value.code == KEY_REVOKED


@pytest.mark.asyncio
async def test_iam_authenticate_api_key_invalid_secret(engine) -> None:
    iam = EnterpriseIAM(engine)
    with pytest.raises(EnterpriseError) as exc:
        await iam.authenticate_api_key("wp_test_not-a-real-key-value", expected_org_id=None)
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_authenticate_api_key_expired(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    record, secret = await _issue_dev_key(iam, actor, org_id)
    past = _iso(_now() - timedelta(days=1))
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(org_api_key_metadata)
            .where(org_api_key_metadata.c.key_id == record["id"])
            .values(expires_at=past)
        )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authenticate_api_key(secret, expected_org_id=org_id)
    assert exc.value.code == KEY_EXPIRED


@pytest.mark.asyncio
async def test_iam_authenticate_api_key_overlap_window_ended(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    record, secret = await _issue_dev_key(iam, actor, org_id)
    _new, _new_secret = await iam.rotate_api_key(actor, org_id, record["id"], overlap_seconds=60)
    past = _iso(_now() - timedelta(minutes=5))
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(org_api_keys)
            .where(org_api_keys.c.id == record["id"])
            .values(overlap_expires_at=past)
        )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authenticate_api_key(secret, expected_org_id=org_id)
    assert exc.value.code == KEY_REVOKED
    assert "overlap" in exc.value.message.lower()


@pytest.mark.asyncio
async def test_iam_authenticate_api_key_accountable_human_disabled(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    record, secret = await _issue_dev_key(iam, actor, org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == owner).values(disabled=1))
    with pytest.raises(EnterpriseError) as exc:
        await iam.authenticate_api_key(secret, expected_org_id=org_id)
    assert exc.value.code == KEY_REVOKED


@pytest.mark.asyncio
async def test_iam_authenticate_api_key_verification_suspended(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    record, secret = await _issue_dev_key(iam, actor, org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_users).where(web_users.c.id == owner).values(verification_status="SUSPENDED")
        )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authenticate_api_key(secret, expected_org_id=org_id)
    assert exc.value.code == VERIFICATION_SUSPENDED


@pytest.mark.asyncio
async def test_iam_revoke_api_key_idempotent_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    record, _secret = await _issue_dev_key(iam, actor, org_id)
    await iam.revoke_api_key(actor, org_id, record["id"])
    with pytest.raises(EnterpriseError) as exc:
        await iam.revoke_api_key(actor, org_id, record["id"])
    assert exc.value.code == KEY_REVOKED


@pytest.mark.asyncio
async def test_iam_list_sessions_denies_cross_user_for_developer(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    other = await _user(engine, "peer@example.com")
    org_id = await _org(engine, owner)
    owner_actor = _actor(owner, org_id, Role.OWNER)
    _, token = await iam.invite_member(
        owner_actor, org_id, email="peer@example.com", role=Role.DEVELOPER
    )
    await iam.accept_invitation(token=token, user_id=other)
    dev_actor = _actor(other, org_id, Role.DEVELOPER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.list_sessions(dev_actor, org_id, user_id=owner)
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_create_service_account_owner_role_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    envs = await iam.list_environments(actor, org_id)
    env_id = envs[0]["id"]
    sponsor = MagicMock()
    sponsor.allowed = True
    sponsor.reason_code = "OK"
    sponsor.message = "ok"
    with patch(
        "responsibleai.enterprise.issuance.CredentialIssuancePolicy.assert_sponsor_eligible",
        return_value=sponsor,
    ):
        with pytest.raises(EnterpriseError) as exc:
            await iam.create_service_account(
                actor,
                org_id,
                display_name="bot",
                role=Role.OWNER,
                environment_ids=(env_id,),
            )
    assert exc.value.code == SERVICE_ACCOUNT_FORBIDDEN


@pytest.mark.asyncio
async def test_iam_create_service_account_wrong_environment_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    await _verify_human(engine, owner)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    sponsor = MagicMock()
    sponsor.allowed = True
    sponsor.reason_code = "OK"
    sponsor.message = "ok"
    with patch(
        "responsibleai.enterprise.issuance.CredentialIssuancePolicy.assert_sponsor_eligible",
        return_value=sponsor,
    ):
        with pytest.raises(EnterpriseError) as exc:
            await iam.create_service_account(
                actor,
                org_id,
                display_name="bot",
                role=Role.DEVELOPER,
                environment_ids=(str(uuid.uuid4()),),
            )
    assert exc.value.code == WRONG_ENVIRONMENT


@pytest.mark.asyncio
async def test_iam_transfer_ownership_success_and_blocks_non_owner(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    heir = await _user(engine, "heir@example.com")
    org_id = await _org(engine, owner)
    owner_actor = _actor(owner, org_id, Role.OWNER)
    _, token = await iam.invite_member(
        owner_actor, org_id, email="heir@example.com", role=Role.ADMIN
    )
    await iam.accept_invitation(token=token, user_id=heir)
    heir_actor = _actor(heir, org_id, Role.ADMIN)
    with pytest.raises(EnterpriseError) as exc:
        await iam.transfer_ownership(
            heir_actor, org_id, new_owner_user_id=heir, confirmation="TRANSFER_OWNERSHIP"
        )
    assert exc.value.code == FORBIDDEN
    await iam.transfer_ownership(
        owner_actor, org_id, new_owner_user_id=heir, confirmation="TRANSFER_OWNERSHIP"
    )
    members = await iam.list_members(heir_actor, org_id)
    roles = {m["user_id"]: m["role"] for m in members}
    assert roles[heir] == Role.OWNER.value
    assert roles[owner] == Role.ADMIN.value


@pytest.mark.asyncio
async def test_iam_revoke_last_owner_still_blocked_with_two_owners(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    co = await _user(engine, "co2@example.com")
    org_id = await _org(engine, owner)
    owner_actor = _actor(owner, org_id, Role.OWNER)
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(web_memberships).values(
                id=str(uuid.uuid4()),
                user_id=co,
                org_id=org_id,
                role=Role.OWNER.value,
                status="ACTIVE",
                invited_by_user_id=owner,
                accepted_at=now,
                created_at=now,
                updated_at=now,
            )
        )
    await iam.revoke_member(owner_actor, org_id, user_id=co)
    with pytest.raises(EnterpriseError) as exc:
        await iam.revoke_member(owner_actor, org_id, user_id=owner)
    assert exc.value.code == LAST_OWNER
