# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent first-enrollment transaction boundaries; not customer journey receipts."""

import asyncio
import uuid

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from sqlalchemy import func, select, update
from tests.protected_component_tenant import component_controller
from tests.webauthn_fakes import registration_blob

from responsibleai.data_governance.tenant_client import TenantCreationDeniedError
from responsibleai.db.engine import (
    auth_replay_records,
    governance_root_authority_records,
    organizations,
    passkey_credentials,
    tenant_provisioning_records,
    web_memberships,
    web_sessions,
    web_users,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.policy import SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.enterprise.service import EnterpriseIAM

# The protected controller refuses a non-PostgreSQL engine. Historical assertion
# bodies below are unchanged and run on disposable PostgreSQL 16 only.


@pytest.fixture(params=["postgres"])
async def first_enrollment(request, tmp_path, monkeypatch):
    assert request.param == "postgres"
    async with component_controller(tmp_path, monkeypatch, "wp_abs_enroll") as controller:
        engine = controller.engine
        identities = WebIdentityRepository(engine)
        user, verification = await identities.register(
            "First owner", f"first-{uuid.uuid4().hex}@example.com", "Local-Strong-42!"
        )
        assert await identities.verify_email(verification)
        # The creator session exists before any organization or membership.
        creator_token, csrf = await identities.create_session(user)
        async with engine.raw.connect() as conn:
            assert await conn.scalar(select(func.count()).select_from(organizations)) == 0
            assert await conn.scalar(select(func.count()).select_from(web_memberships)) == 0
        org = await EnterpriseIAM(engine).create_workspace(
            actor_user_id=user,
            name="First enrollment",
            slug=f"first-{uuid.uuid4().hex}",
            kind="ORGANIZATION",
            session_token=creator_token,
            csrf=csrf,
        )
        org_id = org["id"] if isinstance(org, dict) else org.id
        service = IdentitySecurityService(engine, origin="http://localhost", rp_id="localhost")
        token, _ = await identities.create_session(user, org_id=org_id)
        _, _, session = await service.load_session(token)
        challenge = await service.begin_webauthn(
            user_id=user, session_id=session.session_id, ceremony="register"
        )
        key = generate_private_key(SECP256R1())
        client, authenticator, _, _ = registration_blob(
            rp_id="localhost",
            origin="http://localhost",
            challenge=b64url_decode(challenge["challenge"]),
            private_key=key,
        )
        grant = await service.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=org_id)
        yield engine, service, user, org_id, session, client, authenticator, grant


async def enroll(context):
    _, service, user, _, session, client, authenticator, grant = context
    return await service.finish_passkey_registration(
        user_id=user,
        session=session,
        client_data_b64=client,
        authenticator_data_b64=authenticator,
        grant=grant,
    )


@pytest.mark.asyncio
async def test_first_enrollment_does_not_elevate_session_or_create_root(first_enrollment):
    engine, _, _, _, session, *_ = first_enrollment
    result = await enroll(first_enrollment)
    assert result["credential_id"]
    async with engine.raw.connect() as conn:
        assert (
            await conn.scalar(
                select(web_sessions.c.assurance_level).where(
                    web_sessions.c.session_id == session.session_id
                )
            )
            == "PASSWORD"
        )
        assert (
            await conn.scalar(select(func.count()).select_from(governance_root_authority_records))
            == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary",
    [
        "organization",
        "membership",
        "session",
        "email",
        "absolute_expiry",
        "idle_expiry",
    ],
)
async def test_first_enrollment_rechecks_revocation_at_credential_write(
    first_enrollment, monkeypatch, boundary
):
    engine, service, user, org, session, *_ = first_enrollment
    original = service.require_step_up
    revocation_committed = False

    async def revoke_after_authorization(*args, **kwargs):
        nonlocal revocation_committed
        await original(*args, **kwargs)
        # Deterministically schedule a real state change between the two transactions.
        async with engine.raw.begin() as conn:
            if boundary == "organization":
                await conn.execute(
                    update(organizations)
                    .where(organizations.c.id == org)
                    .values(governance_status="SUSPENDED")
                )
            elif boundary == "membership":
                await conn.execute(
                    update(web_memberships)
                    .where(web_memberships.c.org_id == org, web_memberships.c.user_id == user)
                    .values(status="REVOKED")
                )
            elif boundary == "session":
                await conn.execute(
                    update(web_sessions)
                    .where(web_sessions.c.session_id == session.session_id)
                    .values(revoked=1)
                )
            elif boundary in {"absolute_expiry", "idle_expiry"}:
                column = "expires_at" if boundary == "absolute_expiry" else "inactivity_expires_at"
                await conn.execute(
                    update(web_sessions)
                    .where(web_sessions.c.session_id == session.session_id)
                    .values(**{column: "2000-01-01T00:00:00+00:00"})
                )
            else:
                await conn.execute(
                    update(web_users)
                    .where(web_users.c.id == user)
                    .values(email_verified_at=None, verification_status="UNVERIFIED")
                )

        revocation_committed = True

    monkeypatch.setattr(service, "require_step_up", revoke_after_authorization)
    with pytest.raises(EnterpriseError):
        await enroll(first_enrollment)
    assert revocation_committed, "The actual post-authorization revocation boundary must execute"
    async with engine.raw.connect() as conn:
        assert await conn.scalar(select(func.count()).select_from(passkey_credentials)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("first_enrollment", ["postgres"], indirect=True)
async def test_concurrent_initial_enrollment_has_one_winner(first_enrollment, monkeypatch):
    engine, service, user, org, session, *_ = first_enrollment
    begin = await service.begin_webauthn(
        user_id=user, session_id=session.session_id, ceremony="register"
    )
    client, authenticator, _, _ = registration_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=b64url_decode(begin["challenge"]),
        private_key=generate_private_key(SECP256R1()),
    )
    grant = await service.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=org)
    second = engine, service, user, org, session, client, authenticator, grant
    original = service.require_step_up
    arrived = 0
    both_authorized = asyncio.Event()

    async def barrier(*args, **kwargs):
        nonlocal arrived
        await original(*args, **kwargs)
        arrived += 1
        if arrived == 2:
            both_authorized.set()
        await asyncio.wait_for(both_authorized.wait(), timeout=15)

    monkeypatch.setattr(service, "require_step_up", barrier)
    results = await asyncio.wait_for(
        asyncio.gather(enroll(first_enrollment), enroll(second), return_exceptions=True), timeout=20
    )
    assert sum(isinstance(result, dict) for result in results) == 1, results
    assert sum(isinstance(result, EnterpriseError) for result in results) == 1, results
    async with engine.raw.connect() as conn:
        assert await conn.scalar(select(func.count()).select_from(passkey_credentials)) == 1
        assert (
            await conn.scalar(
                select(func.count())
                .select_from(auth_replay_records)
                .where(auth_replay_records.c.kind == "first_passkey_bootstrap")
            )
            == 1
        )


@pytest.fixture
async def creator_gate(tmp_path, monkeypatch):
    """Verified account and pre-organization session. No membership is inserted."""
    async with component_controller(tmp_path, monkeypatch, "wp_abs_deny") as controller:
        engine = controller.engine
        identities = WebIdentityRepository(engine)
        user, verification = await identities.register(
            "Creator gate", f"gate-{uuid.uuid4().hex}@example.com", "Local-Strong-42!"
        )
        assert await identities.verify_email(verification)
        token, csrf = await identities.create_session(user)
        yield engine, identities, user, token, csrf


async def _assert_no_tenant(engine) -> None:
    async with engine.raw.connect() as conn:
        assert await conn.scalar(select(func.count()).select_from(organizations)) == 0
        assert await conn.scalar(select(func.count()).select_from(web_memberships)) == 0
        assert await conn.scalar(select(func.count()).select_from(tenant_provisioning_records)) == 0


async def _deny_workspace(engine, user, token, csrf, match):
    with pytest.raises(TenantCreationDeniedError, match=match):
        await EnterpriseIAM(engine).create_workspace(
            actor_user_id=user,
            name="Denied enrollment",
            slug=f"deny-{uuid.uuid4().hex}",
            kind="ORGANIZATION",
            session_token=token,
            csrf=csrf,
        )
    await _assert_no_tenant(engine)


@pytest.mark.asyncio
async def test_missing_creator_session_is_denied(creator_gate):
    engine, _, user, _, _ = creator_gate
    await _deny_workspace(engine, user, "", "", "creator mismatch")


@pytest.mark.asyncio
async def test_invalid_creator_session_is_denied(creator_gate):
    engine, _, user, _, csrf = creator_gate
    await _deny_workspace(engine, user, "not-a-creator-session", csrf, "creator mismatch")


@pytest.mark.asyncio
async def test_expired_creator_session_is_denied(creator_gate):
    engine, _, user, token, csrf = creator_gate
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_sessions)
            .where(web_sessions.c.token_hash.is_not(None))
            .values(expires_at="2000-01-01T00:00:00+00:00")
        )
    await _deny_workspace(engine, user, token, csrf, "creator mismatch")


@pytest.mark.asyncio
async def test_mismatched_creator_session_is_denied(creator_gate):
    engine, identities, user, _, _ = creator_gate
    other, verification = await identities.register(
        "Other creator", f"other-{uuid.uuid4().hex}@example.com", "Local-Strong-42!"
    )
    assert await identities.verify_email(verification)
    other_token, other_csrf = await identities.create_session(other)
    await _deny_workspace(engine, user, other_token, other_csrf, "creator mismatch")


@pytest.mark.asyncio
async def test_missing_creator_csrf_is_denied(creator_gate):
    engine, _, user, token, _ = creator_gate
    await _deny_workspace(engine, user, token, "", "Verified session and CSRF are required")


@pytest.mark.asyncio
async def test_invalid_creator_csrf_is_denied(creator_gate):
    engine, _, user, token, _ = creator_gate
    await _deny_workspace(engine, user, token, "not-the-csrf", "authorization was rejected")


@pytest.mark.asyncio
async def test_expired_creator_csrf_is_denied(creator_gate):
    """CSRF has no independent lifetime; an idle-expired session retires its CSRF."""
    engine, _, user, token, csrf = creator_gate
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_sessions)
            .where(web_sessions.c.token_hash.is_not(None))
            .values(inactivity_expires_at="2000-01-01T00:00:00+00:00")
        )
    await _deny_workspace(engine, user, token, csrf, "creator mismatch")


@pytest.mark.asyncio
async def test_mismatched_creator_csrf_is_denied(creator_gate):
    engine, identities, user, token, _ = creator_gate
    _, other_csrf = await identities.create_session(user)
    await _deny_workspace(engine, user, token, other_csrf, "authorization was rejected")


@pytest.mark.asyncio
async def test_unverified_creator_session_is_denied(tmp_path, monkeypatch):
    """A user who has never verified email is refused tenant creation and root authority."""
    from responsibleai.db.org_repository import OrgRepository
    from responsibleai.enterprise.authority.errors import IDENTITY_ASSURANCE_REQUIRED
    from responsibleai.enterprise.authority.service import CustomerAuthorityService
    from responsibleai.enterprise.service import Actor
    from responsibleai.rbac.models import Role

    async with component_controller(tmp_path, monkeypatch, "wp_abs_unver") as controller:
        engine = controller.engine
        identities = WebIdentityRepository(engine)
        user, _ = await identities.register(
            "Never verified creator",
            f"never-verified-{uuid.uuid4().hex}@example.com",
            "Local-Strong-42!",
        )
        token, csrf = await identities.create_session(user)
        await _deny_workspace(engine, user, token, csrf, "creator mismatch")
        with pytest.raises(TenantCreationDeniedError, match="authorization was rejected"):
            await OrgRepository(engine).create_org(
                "Denied direct org",
                f"deny-direct-{uuid.uuid4().hex}",
                session_token=token,
                csrf=csrf,
            )
        await _assert_no_tenant(engine)
        actor = Actor(
            actor_type="USER",
            actor_id=user,
            user_id=user,
            org_id="org-never-created",
            role=Role.OWNER,
            membership_status="ACTIVE",
        )
        with pytest.raises(EnterpriseError) as exc:
            await CustomerAuthorityService(engine).initiate_root_bootstrap(
                actor, org_id="org-never-created"
            )
        assert exc.value.code in {"FORBIDDEN", IDENTITY_ASSURANCE_REQUIRED}
        async with engine.raw.connect() as conn:
            assert (
                await conn.scalar(
                    select(func.count()).select_from(governance_root_authority_records)
                )
                == 0
            )


@pytest.mark.asyncio
async def test_sqlite_controller_and_workspace_creation_refused_without_bypass(
    tmp_path, monkeypatch
):
    """SQLite refuses ProtectedTenantController and fails closed on workspace provisioning."""
    import secrets

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from responsibleai.data_governance.backup_defense import SqliteDurableLifecycleStateProvider
    from responsibleai.data_governance.provisioning_manifest import (
        ProvisionerTrust,
        ProvisioningAuthorizationError,
    )
    from responsibleai.data_governance.tenant_client import TenantProvisioningUnavailableError
    from responsibleai.data_governance.tenant_controller import (
        ProtectedTenantController,
        store_b_identity,
    )
    from responsibleai.db.engine import create_engine

    sqlite_engine = create_engine(":memory:")
    await sqlite_engine.init()
    try:
        provider = SqliteDurableLifecycleStateProvider(
            tmp_path / "sqlite-refused-store-b.sqlite3", secret_key=secrets.token_hex(32)
        )
        key = Ed25519PrivateKey.generate()
        trust = ProvisionerTrust(
            "sqlite-refused",
            key.public_key().public_bytes_raw(),
            "sqlite-refused",
            "staging",
            "0" * 64,
            store_b_identity(provider),
        )
        with pytest.raises(
            ProvisioningAuthorizationError, match="Controller deployment is not qualified"
        ):
            ProtectedTenantController(sqlite_engine, provider, trust, key)

        identities = WebIdentityRepository(sqlite_engine)
        unverified, _ = await identities.register(
            "SQLite unverified",
            f"sqlite-unv-{uuid.uuid4().hex}@example.com",
            "Local-Strong-42!",
        )
        unv_token, unv_csrf = await identities.create_session(unverified)
        await _deny_workspace(sqlite_engine, unverified, unv_token, unv_csrf, "creator mismatch")

        verified, verification = await identities.register(
            "SQLite verified",
            f"sqlite-ver-{uuid.uuid4().hex}@example.com",
            "Local-Strong-42!",
        )
        assert await identities.verify_email(verification)
        ver_token, ver_csrf = await identities.create_session(verified)
        monkeypatch.delenv("WHITEPACT_TENANT_CONTROLLER_SOCKET", raising=False)
        with pytest.raises(TenantProvisioningUnavailableError):
            await EnterpriseIAM(sqlite_engine).create_workspace(
                actor_user_id=verified,
                name="SQLite workspace",
                slug=f"sqlite-{uuid.uuid4().hex}",
                kind="ORGANIZATION",
                session_token=ver_token,
                csrf=ver_csrf,
            )
        await _assert_no_tenant(sqlite_engine)
        async with sqlite_engine.raw.connect() as conn:
            assert (
                await conn.scalar(
                    select(func.count()).select_from(governance_root_authority_records)
                )
                == 0
            )
    finally:
        await sqlite_engine.close()


@pytest.mark.asyncio
async def test_sqlite_totp_passkey_enrollment_does_not_elevate_session_or_create_root():
    """Database-independent WebAuthn registration on SQLite with TOTP step-up and no org bypass."""
    import pyotp

    from responsibleai.db.engine import create_engine, human_totp_factors
    from responsibleai.enterprise.security.policy import AuthMethod

    sqlite_engine = create_engine(":memory:")
    await sqlite_engine.init()
    try:
        identities = WebIdentityRepository(sqlite_engine)
        user, verification = await identities.register(
            "SQLite TOTP user",
            f"sqlite-totp-{uuid.uuid4().hex}@example.com",
            "Local-Strong-42!",
        )
        assert await identities.verify_email(verification)
        service = IdentitySecurityService(
            sqlite_engine, origin="http://localhost", rp_id="localhost"
        )
        await service.start_totp(user)
        async with sqlite_engine.raw.connect() as conn:
            secret = await conn.scalar(
                select(human_totp_factors.c.pending_secret_encrypted).where(
                    human_totp_factors.c.user_id == user
                )
            )
        assert secret
        await service.confirm_totp(user, pyotp.TOTP(secret).now())
        _, _, session = await service.issue_session(
            user_id=user,
            methods=(AuthMethod.PASSWORD, AuthMethod.TOTP),
            org_id=None,
            ip_label=None,
            user_agent=None,
        )
        challenge = await service.begin_webauthn(
            user_id=user, session_id=session.session_id, ceremony="register"
        )
        client, authenticator, _, _ = registration_blob(
            rp_id="localhost",
            origin="http://localhost",
            challenge=b64url_decode(challenge["challenge"]),
            private_key=generate_private_key(SECP256R1()),
        )
        grant = await service.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
        result = await service.finish_passkey_registration(
            user_id=user,
            session=session,
            client_data_b64=client,
            authenticator_data_b64=authenticator,
            grant=grant,
        )
        assert result["credential_id"]
        await _assert_no_tenant(sqlite_engine)
        async with sqlite_engine.raw.connect() as conn:
            assert (
                await conn.scalar(
                    select(web_sessions.c.assurance_level).where(
                        web_sessions.c.session_id == session.session_id
                    )
                )
                == "TOTP"
            )
            assert (
                await conn.scalar(
                    select(func.count()).select_from(governance_root_authority_records)
                )
                == 0
            )
            assert await conn.scalar(select(func.count()).select_from(passkey_credentials)) == 1
    finally:
        await sqlite_engine.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "boundary",
    [
        "organization",
        "membership",
        "session",
        "email",
        "absolute_expiry",
        "idle_expiry",
    ],
)
async def test_sqlite_first_passkey_bootstrap_denied_at_credential_write_without_controller_org(
    monkeypatch, boundary
):
    """SQLite PASSWORD-session first-passkey bootstrap fails closed without bypassing the controller."""
    from responsibleai.db.engine import create_engine

    sqlite_engine = create_engine(":memory:")
    await sqlite_engine.init()
    try:
        identities = WebIdentityRepository(sqlite_engine)
        user, verification = await identities.register(
            "SQLite bootstrap candidate",
            f"sqlite-boot-{uuid.uuid4().hex}@example.com",
            "Local-Strong-42!",
        )
        assert await identities.verify_email(verification)
        service = IdentitySecurityService(
            sqlite_engine, origin="http://localhost", rp_id="localhost"
        )
        claimed_org = f"unprovisioned-org-{uuid.uuid4().hex[:8]}"
        token, _ = await identities.create_session(user, org_id=claimed_org)
        # Before loading or mutating, verify no organization or membership exists on SQLite.
        await _assert_no_tenant(sqlite_engine)
        async with sqlite_engine.raw.connect() as conn:
            row = (
                await conn.execute(select(web_sessions).where(web_sessions.c.user_id == user))
            ).fetchone()
        from responsibleai.enterprise.security.policy import AuthMethod, SessionAssurance

        session = SessionAssurance(
            level="PASSWORD",
            methods=(AuthMethod.PASSWORD,),
            auth_time=row.auth_time or row.created_at,
            phishing_resistant=False,
            session_id=row.session_id,
            user_id=user,
            org_id=claimed_org,
        )
        challenge = await service.begin_webauthn(
            user_id=user, session_id=session.session_id, ceremony="register", org_id=claimed_org
        )
        client, authenticator, _, _ = registration_blob(
            rp_id="localhost",
            origin="http://localhost",
            challenge=b64url_decode(challenge["challenge"]),
            private_key=generate_private_key(SECP256R1()),
        )
        grant = await service.issue_step_up(
            session, SensitiveAction.ADD_PASSKEY, org_id=claimed_org
        )
        context = sqlite_engine, service, user, claimed_org, session, client, authenticator, grant

        # 1. Standard require_step_up refuses PASSWORD bootstrap when no controller org exists.
        with pytest.raises(EnterpriseError) as initial_denial:
            await enroll(context)
        assert initial_denial.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"

        # 2. Even if require_step_up is crossed, the credential-write transaction recheck refuses.
        revocation_committed = False

        async def mutate_after_step_up(*args, **kwargs):
            nonlocal revocation_committed
            async with sqlite_engine.raw.begin() as conn:
                if boundary == "session":
                    await conn.execute(
                        update(web_sessions)
                        .where(web_sessions.c.session_id == session.session_id)
                        .values(revoked=1)
                    )
                elif boundary in {"absolute_expiry", "idle_expiry"}:
                    column = (
                        "expires_at" if boundary == "absolute_expiry" else "inactivity_expires_at"
                    )
                    await conn.execute(
                        update(web_sessions)
                        .where(web_sessions.c.session_id == session.session_id)
                        .values(**{column: "2000-01-01T00:00:00+00:00"})
                    )
                elif boundary == "email":
                    await conn.execute(
                        update(web_users)
                        .where(web_users.c.id == user)
                        .values(email_verified_at=None, verification_status="UNVERIFIED")
                    )
            revocation_committed = True

        monkeypatch.setattr(service, "require_step_up", mutate_after_step_up)
        with pytest.raises(EnterpriseError) as write_denial:
            await enroll(context)
        assert write_denial.value.code == "AUTHENTICATION_ASSURANCE_TOO_LOW"
        assert revocation_committed
        await _assert_no_tenant(sqlite_engine)
        async with sqlite_engine.raw.connect() as conn:
            assert await conn.scalar(select(func.count()).select_from(passkey_credentials)) == 0
            assert await conn.scalar(select(func.count()).select_from(auth_replay_records)) == 0
    finally:
        await sqlite_engine.close()
