# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent first-enrollment transaction boundaries; not customer journey receipts."""

import asyncio
import uuid
from contextlib import AsyncExitStack, aclosing

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from sqlalchemy import func, select, update
from tests.pg_test_url import isolated_pg_url
from tests.webauthn_fakes import registration_blob

from responsibleai.db.engine import (
    auth_replay_records,
    create_engine,
    governance_root_authority_records,
    organizations,
    passkey_credentials,
    web_memberships,
    web_sessions,
    web_users,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.policy import SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.enterprise.service import EnterpriseIAM


@pytest.fixture(params=["sqlite", "postgres"])
async def first_enrollment(request):
    async with AsyncExitStack() as stack:
        database = ":memory:"
        if request.param == "postgres":
            databases = await stack.enter_async_context(
                aclosing(isolated_pg_url("wp_absolute_enroll"))
            )
            database = await anext(databases)
            ini = _find_alembic_ini()
            assert ini is not None
            await _run_alembic(ini, _migration_env(database), "upgrade", "head")
        engine = create_engine(database)
        if request.param == "sqlite":
            await engine.init()
        identities = WebIdentityRepository(engine)
        user, token = await identities.register(
            "First owner", f"first-{uuid.uuid4().hex}@example.com", "Local-Strong-42!"
        )
        assert await identities.verify_email(token)
        org = await EnterpriseIAM(engine).create_workspace(
            actor_user_id=user,
            name="First enrollment",
            slug=f"first-{uuid.uuid4().hex}",
            kind="ORGANIZATION",
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
        try:
            yield engine, service, user, org_id, session, client, authenticator, grant
        finally:
            await engine.close()


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

    async def revoke_after_authorization(*args, **kwargs):
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

    monkeypatch.setattr(service, "require_step_up", revoke_after_authorization)
    with pytest.raises(EnterpriseError):
        await enroll(first_enrollment)
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

