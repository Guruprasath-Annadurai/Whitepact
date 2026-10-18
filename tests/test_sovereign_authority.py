# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A2/B1 component qualification; not hardware or production certification."""

import base64
import hashlib
import uuid
from dataclasses import replace
from types import SimpleNamespace

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import select, update

from responsibleai.db.engine import create_engine, organizations, web_memberships, web_sessions
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.agent_auth import (
    AUDIENCE,
    INTENT_PATH,
    DevelopmentAgentAuth,
    challenges,
    credentials,
)
from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.policy import SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from tests.pg_test_url import isolated_pg_url
from tests.webauthn_fakes import assertion_blob, registration_blob


@pytest.fixture
async def owner(request):
    databases = None
    database = ":memory:"
    if getattr(request, "param", None) == "postgres":
        databases = isolated_pg_url("wp_sovereign_b1")
        database = await anext(databases)
        await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "head")
    engine = create_engine(database)
    if database == ":memory:":
        await engine.init()
    web = WebIdentityRepository(engine)
    user, verification = await web.register(
        "Owner", f"a2-{uuid.uuid4().hex}@example.com", "Valid-Password42!"
    )
    assert await web.verify_email(verification)
    org = await EnterpriseIAM(engine).create_workspace(
        actor_user_id=user, name="A2", slug=f"a2-{uuid.uuid4().hex}", kind="ORGANIZATION"
    )
    org_id = org["id"] if isinstance(org, dict) else org.id
    identity = IdentitySecurityService(engine, origin="http://localhost", rp_id="localhost")
    token, _ = await web.create_session(user, org_id=org_id)
    _, _, password = await identity.load_session(token)
    actor = Actor("human", user, user, org_id, Role.OWNER, "ACTIVE")
    key = generate_private_key(SECP256R1())
    challenge = await identity.begin_webauthn(
        user_id=user, session_id=password.session_id, ceremony="register", org_id=org_id
    )
    client, auth, credential, _ = registration_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=b64url_decode(challenge["challenge"]),
        private_key=key,
    )
    grant = await identity.issue_step_up(password, SensitiveAction.ADD_PASSKEY, org_id=org_id)
    await identity.finish_passkey_registration(
        user_id=user,
        session=password,
        client_data_b64=client,
        authenticator_data_b64=auth,
        grant=grant,
    )
    assertion = await identity.begin_webauthn(
        user_id=None, session_id=None, ceremony="authenticate"
    )
    c, a, signature = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=b64url_decode(assertion["challenge"]),
        private_key=key,
    )
    uv_token, uv_csrf, session = await identity.authenticate_passkey(
        client_data_b64=c,
        authenticator_data_b64=a,
        signature_b64=signature,
        credential_id=credential,
        org_id=org_id,
    )
    if "session_id" in Actor.__dataclass_fields__:
        actor = replace(actor, session_id=session.session_id)
    try:
        yield engine, identity, actor, password, session, key, credential, uv_token, uv_csrf
    finally:
        await engine.close()
        if databases:
            await databases.aclose()


@pytest.mark.asyncio
async def test_a2_caller_flags_cannot_allow_password_only_root(owner):
    engine, _, actor, password, *_ = owner
    if "session_id" in Actor.__dataclass_fields__:
        actor = replace(actor, session_id=password.session_id)
    with pytest.raises(EnterpriseError):
        await CustomerAuthorityService(engine).initiate_root_bootstrap(
            actor,
            org_id=actor.org_id,
            require_identity_assurance=False,
            require_passkey_stepup=False,
        )


@pytest.mark.asyncio
async def test_a2_legitimate_uv_forces_server_mandatory_flags(owner):
    engine, _, actor, *_ = owner
    ceremony = await CustomerAuthorityService(engine).initiate_root_bootstrap(
        actor, org_id=actor.org_id, require_identity_assurance=False, require_passkey_stepup=False
    )
    assert ceremony["require_passkey_stepup"] is True


async def root(owner, *, signature_required=True, prepare_only=False):
    engine, _, actor, _, _, key, credential, *_ = owner
    service = CustomerAuthorityService(engine)
    boot = await service.initiate_root_bootstrap(actor, org_id=actor.org_id)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes_raw().hex()
    token_hash = hashlib.sha256(boot["token"].encode()).hexdigest()
    from responsibleai.enterprise.authority.service import compute_canonical_operation_digest

    operation_digest = compute_canonical_operation_digest(
        "COMPLETE_ROOT_BOOTSTRAP",
        dict(
            org_id=actor.org_id, nonce=boot["nonce"], token_hash=token_hash, root_public_key=public
        ),
    )
    challenge = await service.create_authority_stepup_challenge(
        actor,
        org_id=actor.org_id,
        action="COMPLETE_ROOT_BOOTSTRAP",
        operation_digest=operation_digest,
    )
    c, a, s = assertion_blob(
        rp_id=challenge["rp_id"],
        origin=challenge["origin"],
        challenge=b64url_decode(challenge["challenge"]),
        private_key=key,
        sign_count=2,
    )
    proof = base64.urlsafe_b64encode(
        private.sign(f"WP_ROOT_POP:{actor.org_id}:{boot['nonce']}:{token_hash}".encode())
    ).decode()
    parameters = dict(
        org_id=actor.org_id,
        token=boot["token"],
        nonce=boot["nonce"],
        root_public_key=public,
        root_signature=proof if signature_required else None,
        webauthn_assertion=dict(
            credential_id=credential, client_data_json=c, authenticator_data=a, signature=s
        ),
        scope_description="Harmless local policy evaluation",
        purpose="B1 development qualification",
        allowed_action_types=["rai_policy_check"],
        allowed_targets=["rai_policy_check"],
        consent_method="API_AUTHENTICATED_REQUEST",
    )
    if prepare_only:
        return service, actor, parameters
    return await service.complete_root_bootstrap(actor, **parameters)


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["postgres"], indirect=True)
@pytest.mark.parametrize("fault", ["epoch", "missing_assertion", "signature", "tenant"])
async def test_a2_root_ceremony_boundaries(owner, fault):
    from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection

    service, actor, parameters = await root(owner, prepare_only=True)
    if fault == "epoch":
        async with owner[0].raw.begin() as conn:
            await bump_epoch_on_connection(conn, actor.org_id)
    elif fault == "missing_assertion":
        parameters["webauthn_assertion"] = None
    elif fault == "signature":
        parameters["root_signature"] = base64.urlsafe_b64encode(b"x" * 64).decode()
    else:
        parameters["org_id"] = str(uuid.uuid4())
    with pytest.raises(EnterpriseError):
        await service.complete_root_bootstrap(actor, **parameters)


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["postgres"], indirect=True)
async def test_a2_concurrent_root_completion_has_one_winner_and_replay_denied(owner):
    import asyncio

    service, actor, parameters = await root(owner, prepare_only=True)
    results = await asyncio.gather(
        *(service.complete_root_bootstrap(actor, **parameters) for _ in range(2)),
        return_exceptions=True,
    )
    assert sum(isinstance(result, dict) for result in results) == 1
    assert sum(isinstance(result, EnterpriseError) for result in results) == 1
    with pytest.raises(EnterpriseError):
        await service.complete_root_bootstrap(actor, **parameters)


@pytest.mark.asyncio
async def test_a2_root_key_possession_is_mandatory(owner):
    with pytest.raises(EnterpriseError) as error:
        await root(owner, signature_required=False)
    assert error.value.code == "PROOF_OF_POSSESSION_INVALID"


@pytest.mark.asyncio
@pytest.mark.parametrize("owner", ["postgres"], indirect=True)
async def test_unqualified_customer_recovery_routes_are_blocked(owner, monkeypatch):
    import httpx
    from fastapi import FastAPI
    from sqlalchemy import func

    from responsibleai.db.engine import (
        authority_recovery_requests,
        governance_root_authority_records,
    )
    from responsibleai.enterprise import runtime
    from responsibleai.enterprise.authority.router import router

    await root(owner)
    engine, _, actor, *_ = owner
    monkeypatch.setattr(runtime, "_engine", engine)
    app = FastAPI()
    app.include_router(router)
    async with engine.raw.connect() as conn:
        target = await conn.scalar(select(governance_root_authority_records.c.root_id))
        roots_before = await conn.scalar(
            select(func.count()).select_from(governance_root_authority_records)
        )
        requests_before = await conn.scalar(
            select(func.count()).select_from(authority_recovery_requests)
        )
    base = f"/api/enterprise/organizations/{actor.org_id}/authority/recovery/requests"
    payload = dict(
        request_type="ROOT_KEY_REPLACEMENT",
        target_root_id=target,
        proposed_parameters={
            "new_root_public_key": Ed25519PrivateKey.generate()
            .public_key()
            .public_bytes_raw()
            .hex()
        },
        required_quorum_m=1,
        eligible_quorum_n=1,
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        client.cookies.set("wp_session", owner[7])
        client.cookies.set("wp_csrf", owner[8])
        headers = {"X-WP-CSRF": owner[8]}
        responses = [
            await client.post(base, json=payload, headers=headers),
            await client.post(
                base + "/unqualified/vote",
                json={"decision": "APPROVE", "action_digest": "unqualified"},
                headers=headers,
            ),
            await client.post(
                base + "/unqualified/execute",
                json={"action_digest": "unqualified"},
                headers=headers,
            ),
        ]
        assert [r.status_code for r in responses] == [503, 503, 503]
        assert all(
            r.json()["error"] == "RECOVERY_SECURITY_QUALIFICATION_REQUIRED" for r in responses
        )
        assert (await client.get(base)).status_code == 200
        other_tenant = base.replace(actor.org_id, str(uuid.uuid4()))
        assert (await client.post(other_tenant, json=payload, headers=headers)).status_code == 403
        assert (
            await client.post(base, json=payload, headers={"X-WP-CSRF": "wrong"})
        ).status_code == 403
        client.cookies.clear()
        assert (await client.post(base, json=payload)).status_code == 401
    async with engine.raw.connect() as conn:
        assert (
            await conn.scalar(select(func.count()).select_from(governance_root_authority_records))
            == roots_before
        )
        assert (
            await conn.scalar(select(func.count()).select_from(authority_recovery_requests))
            == requests_before
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["session", "membership", "organization", "expired", "stale"])
async def test_a2_revoked_or_stale_context_is_denied(owner, state):
    engine, _, actor, *_ = owner
    async with engine.raw.begin() as conn:
        if state == "session":
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.session_id == actor.session_id)
                .values(revoked=1)
            )
        elif state == "membership":
            await conn.execute(
                update(web_memberships)
                .where(web_memberships.c.org_id == actor.org_id)
                .values(status="REVOKED")
            )
        elif state == "organization":
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == actor.org_id)
                .values(governance_status="SUSPENDED")
            )
        else:
            field = "expires_at" if state == "expired" else "auth_time"
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.session_id == actor.session_id)
                .values(**{field: "2020-01-01T00:00:00+00:00"})
            )
    with pytest.raises(EnterpriseError):
        await CustomerAuthorityService(engine).initiate_root_bootstrap(actor, org_id=actor.org_id)


def proof(key, challenge):
    return base64.urlsafe_b64encode(
        key.sign(base64.urlsafe_b64decode(challenge["message"]))
    ).decode()


async def delegated(owner, *, issue=True):
    await root(owner)
    engine, _, actor, *_ = owner
    svc = CustomerAuthorityService(engine)
    app = await svc.register_application(
        actor, org_id=actor.org_id, name="B1 app", environment="development"
    )
    agent = await svc.register_agent(
        actor, org_id=actor.org_id, name="B1 agent", application_id=app["application_id"]
    )
    await svc.delegate_to_agent(
        actor,
        org_id=actor.org_id,
        agent_id=agent["agent_id"],
        granted_action_types=["rai_policy_check"],
        allowed_targets=["rai_policy_check"],
        purpose="B1 development qualification",
    )
    auth = DevelopmentAgentAuth(
        engine,
        SimpleNamespace(
            dev_agent_auth_enabled=True, environment="development", is_production=False
        ),
    )
    await auth.initialize()
    key = Ed25519PrivateKey.generate()
    if not issue:
        return auth, agent["agent_id"], key, None
    challenge = await auth.begin_issue(
        actor, agent["agent_id"], key.public_key().public_bytes_raw().hex()
    )
    issued = await auth.finish_issue(actor, challenge["challenge_id"], proof(key, challenge))
    return auth, agent["agent_id"], key, issued


@pytest.mark.parametrize("owner", ["postgres"], indirect=True)
class TestDevelopmentB1:
    @pytest.mark.asyncio
    async def test_request_authentication_with_single_connection_pool(self, owner):
        import asyncio

        from sqlalchemy.ext.asyncio import create_async_engine

        from responsibleai.db.engine import DatabaseEngine

        original, _, key, issued = await delegated(owner)
        pool = create_async_engine(owner[0].raw.url, pool_size=1, max_overflow=0, pool_timeout=1)
        auth = DevelopmentAgentAuth(DatabaseEngine(pool), original.settings)
        body = dict(name="rai_policy_check", arguments={}, purpose="bounded pool")
        try:
            challenge = await asyncio.wait_for(
                auth.begin_request(
                    issued["credential"],
                    audience=AUDIENCE,
                    method="POST",
                    path=INTENT_PATH,
                    body=body,
                ),
                5,
            )
            context = await asyncio.wait_for(
                auth.authenticate(
                    issued["credential"],
                    challenge["challenge_id"],
                    proof(key, challenge),
                    audience=AUDIENCE,
                    method="POST",
                    path=INTENT_PATH,
                    body=body,
                ),
                5,
            )
            assert context.authentication_method == "agent_pop"
        finally:
            await pool.dispose()

    @pytest.mark.asyncio
    async def test_concurrent_prototype_initialization(self, owner):
        import asyncio

        from responsibleai.enterprise.agent_auth import prototype_metadata

        auth = DevelopmentAgentAuth(
            owner[0],
            SimpleNamespace(
                dev_agent_auth_enabled=True, environment="development", is_production=False
            ),
        )
        async with owner[0].raw.begin() as conn:
            await conn.run_sync(prototype_metadata.drop_all)
        await asyncio.gather(auth.initialize(), auth.initialize())
        async with owner[0].raw.connect() as conn:
            assert (await conn.execute(select(credentials))).first() is None
            assert (await conn.execute(select(challenges))).first() is None

    @pytest.mark.asyncio
    async def test_invalid_handles_do_not_create_per_handle_counters(self, owner):
        from responsibleai.db.engine import identity_rate_counters

        auth, _, _, _ = await delegated(owner)
        for _ in range(12):
            with pytest.raises(EnterpriseError):
                await auth.begin_request(
                    uuid.uuid4().hex,
                    audience=AUDIENCE,
                    method="POST",
                    path=INTENT_PATH,
                    body={},
                )
        async with owner[0].raw.connect() as conn:
            keys = (
                (
                    await conn.execute(
                        select(identity_rate_counters.c.bucket_key).where(
                            identity_rate_counters.c.bucket_key.like("b1-request:%")
                        )
                    )
                )
                .scalars()
                .all()
            )
        assert keys == ["b1-request:unauthenticated"]

    @pytest.mark.asyncio
    async def test_real_issuance_and_agent_proof(self, owner):
        auth, agent, key, issued = await delegated(owner)
        body = dict(
            name="rai_policy_check",
            arguments={"text": "harmless", "policy": {}},
            purpose="B1 development qualification",
        )
        challenge = await auth.begin_request(
            issued["credential"], audience=AUDIENCE, method="POST", path=INTENT_PATH, body=body
        )
        context = await auth.authenticate(
            issued["credential"],
            challenge["challenge_id"],
            proof(key, challenge),
            audience=AUDIENCE,
            method="POST",
            path=INTENT_PATH,
            body=body,
        )
        assert context.key_id == agent and context.org_id == owner[2].org_id
        assert (
            context.authentication_method == "agent_pop" and issued["authentication_only"] is True
        )
        with pytest.raises(EnterpriseError):
            await auth.authenticate(
                issued["credential"],
                challenge["challenge_id"],
                proof(key, challenge),
                audience=AUDIENCE,
                method="POST",
                path=INTENT_PATH,
                body=body,
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "attack",
        [
            "stolen",
            "audience",
            "intent",
            "expired",
            "issuer",
            "epoch",
            "session",
            "nonce_expired",
            "nonce_mismatch",
            "revoked",
            "principal",
            "delegation",
            "future",
            "lifetime",
        ],
    )
    async def test_invalid_credential_or_proof_cannot_authenticate(self, owner, attack):
        auth, agent, key, issued = await delegated(owner)
        body = dict(name="rai_policy_check", arguments={}, purpose="B1 development qualification")
        challenge = await auth.begin_request(
            issued["credential"], audience=AUDIENCE, method="POST", path=INTENT_PATH, body=body
        )
        audience = "wrong" if attack == "audience" else AUDIENCE
        signature = proof(Ed25519PrivateKey.generate() if attack == "stolen" else key, challenge)
        if attack == "intent":
            body["arguments"] = {"tampered": True}
        elif attack == "revoked":
            await auth.revoke(owner[2], issued["credential_id"])
        elif attack == "principal":
            await CustomerAuthorityService(owner[0]).disable_agent(
                owner[2], org_id=owner[2].org_id, agent_id=agent
            )
        elif attack == "delegation":
            from responsibleai.db.delegation_repository import DelegationRepository

            async with owner[0].raw.connect() as conn:
                row = (await conn.execute(select(credentials))).first()
            await DelegationRepository(owner[0]).revoke_branch(
                owner[2].org_id, row.agent_id, revoked_by=owner[2].user_id, reason="qualification"
            )
        elif attack in {
            "expired",
            "issuer",
            "epoch",
            "session",
            "nonce_expired",
            "nonce_mismatch",
            "future",
            "lifetime",
        }:
            async with owner[0].raw.begin() as conn:
                if attack == "expired":
                    await conn.execute(update(credentials).values(expires=0))
                elif attack == "nonce_expired":
                    await conn.execute(update(challenges).values(expires=0))
                elif attack == "nonce_mismatch":
                    await conn.execute(update(challenges).values(expires=challenges.c.expires - 1))
                elif attack == "future":
                    from datetime import UTC, datetime

                    future = int(datetime.now(UTC).timestamp()) + 3600
                    await conn.execute(
                        update(credentials).values(issued=future, expires=future + 120)
                    )
                elif attack == "lifetime":
                    row = (await conn.execute(select(credentials))).first()
                    await conn.execute(update(credentials).values(expires=row.issued + 121))
                elif attack == "issuer":
                    import json

                    row = (await conn.execute(select(credentials))).first()
                    binding = json.loads(row.binding)
                    binding["issuer"] = "untrusted"
                    await conn.execute(update(credentials).values(binding=json.dumps(binding)))
                elif attack == "epoch":
                    from responsibleai.db.revocation_epoch_repository import (
                        bump_epoch_on_connection,
                    )

                    await bump_epoch_on_connection(conn, owner[2].org_id)
                else:
                    await conn.execute(
                        update(web_sessions)
                        .where(web_sessions.c.session_id == owner[2].session_id)
                        .values(revoked=1)
                    )
        with pytest.raises(EnterpriseError):
            await auth.authenticate(
                issued["credential"],
                challenge["challenge_id"],
                signature,
                audience=audience,
                method="POST",
                path=INTENT_PATH,
                body=body,
            )

    @pytest.mark.asyncio
    async def test_actual_concurrent_issue_and_rotation(self, owner):
        import asyncio

        auth, agent, key, _ = await delegated(owner, issue=False)
        challenge = await auth.begin_issue(
            owner[2], agent, key.public_key().public_bytes_raw().hex()
        )
        results = await asyncio.gather(
            *(
                auth.finish_issue(owner[2], challenge["challenge_id"], proof(key, challenge))
                for _ in range(2)
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(result, dict) for result in results) == 1
        assert sum(isinstance(result, EnterpriseError) for result in results) == 1
        issued = next(result for result in results if isinstance(result, dict))
        new_key = Ed25519PrivateKey.generate()
        rotate = await auth.begin_issue(
            owner[2],
            agent,
            new_key.public_key().public_bytes_raw().hex(),
            rotate_from=issued["credential_id"],
        )
        replacement = await auth.finish_issue(
            owner[2], rotate["challenge_id"], proof(new_key, rotate)
        )
        body = dict(name="rai_policy_check", arguments={}, purpose="qualification")
        with pytest.raises(EnterpriseError):
            await auth.begin_request(
                issued["credential"], audience=AUDIENCE, method="POST", path=INTENT_PATH, body=body
            )
        nonce = await auth.begin_request(
            replacement["credential"], audience=AUDIENCE, method="POST", path=INTENT_PATH, body=body
        )
        with pytest.raises(EnterpriseError):
            await auth.authenticate(
                replacement["credential"],
                nonce["challenge_id"],
                proof(key, nonce),
                audience=AUDIENCE,
                method="POST",
                path=INTENT_PATH,
                body=body,
            )
        context = await auth.authenticate(
            replacement["credential"],
            nonce["challenge_id"],
            proof(new_key, nonce),
            audience=AUDIENCE,
            method="POST",
            path=INTENT_PATH,
            body=body,
        )
        assert context.key_id == agent
        async with owner[0].raw.connect() as conn:
            active = (
                await conn.execute(select(credentials).where(credentials.c.revoked == 0))
            ).all()
        assert len(active) == 1

    @pytest.mark.asyncio
    async def test_actual_nonce_race_has_one_winner(self, owner):
        import asyncio

        auth, _, key, issued = await delegated(owner)
        body = dict(name="rai_policy_check", arguments={}, purpose="qualification")
        nonce = await auth.begin_request(
            issued["credential"], audience=AUDIENCE, method="POST", path=INTENT_PATH, body=body
        )
        results = await asyncio.gather(
            *(
                auth.authenticate(
                    issued["credential"],
                    nonce["challenge_id"],
                    proof(key, nonce),
                    audience=AUDIENCE,
                    method="POST",
                    path=INTENT_PATH,
                    body=body,
                )
                for _ in range(2)
            ),
            return_exceptions=True,
        )
        assert sum(isinstance(result, EnterpriseError) for result in results) == 1
        assert (
            sum(getattr(result, "authentication_method", None) == "agent_pop" for result in results)
            == 1
        )

    @pytest.mark.asyncio
    async def test_pending_real_recovery_blocks_credentials(self, owner):
        import json

        from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

        auth, _, _, issued = await delegated(owner)
        before = (await RevocationEpochRepository(owner[0]).current(owner[2].org_id)).epoch
        async with owner[0].raw.connect() as conn:
            binding = json.loads((await conn.execute(select(credentials))).first().binding)
        request = await CustomerAuthorityService(owner[0]).create_recovery_request(
            owner[2],
            org_id=owner[2].org_id,
            request_type="ROOT_KEY_REPLACEMENT",
            target_root_id=binding["root_id"],
            proposed_parameters={
                "new_root_public_key": Ed25519PrivateKey.generate()
                .public_key()
                .public_bytes_raw()
                .hex()
            },
        )
        assert request["request_id"]
        assert (await RevocationEpochRepository(owner[0]).current(owner[2].org_id)).epoch > before
        with pytest.raises(EnterpriseError):
            await auth.begin_request(
                issued["credential"], audience=AUDIENCE, method="POST", path=INTENT_PATH, body={}
            )

    @pytest.mark.asyncio
    async def test_real_database_connection_outage_denies_and_recovers(self, owner):
        import asyncpg

        auth, _, key, issued = await delegated(owner)
        body = dict(name="rai_policy_check", arguments={}, purpose="qualification")
        nonce = await auth.begin_request(
            issued["credential"], audience=AUDIENCE, method="POST", path=INTENT_PATH, body=body
        )
        url = (
            owner[0]
            .raw.url.set(database="postgres")
            .render_as_string(hide_password=False)
            .replace("postgresql+asyncpg://", "postgresql://")
        )
        admin = await asyncpg.connect(url)
        database = owner[0].raw.url.database
        assert database.startswith("wp_sovereign_b1")
        quoted = '"' + database.replace('"', '""') + '"'
        await owner[0].raw.dispose()
        try:
            await admin.execute(f"ALTER DATABASE {quoted} ALLOW_CONNECTIONS false")
            from starlette.requests import Request

            from responsibleai.enterprise.agent_auth_router import guarded

            async def operation():
                return await auth.authenticate(
                    issued["credential"],
                    nonce["challenge_id"],
                    proof(key, nonce),
                    audience=AUDIENCE,
                    method="POST",
                    path=INTENT_PATH,
                    body=body,
                )

            response = await guarded(Request({"type": "http", "headers": []}), operation)
            assert response.status_code == 503
            import json

            assert json.loads(response.body)["error"] in {
                "B1_STORAGE_UNVERIFIED",
                "IDENTITY_PROTECTION_UNAVAILABLE",
            }
        finally:
            await admin.execute(f"ALTER DATABASE {quoted} ALLOW_CONNECTIONS true")
            await admin.close()
        context = await auth.authenticate(
            issued["credential"],
            nonce["challenge_id"],
            proof(key, nonce),
            audience=AUDIENCE,
            method="POST",
            path=INTENT_PATH,
            body=body,
        )
        assert context.authentication_method == "agent_pop"

    @pytest.mark.asyncio
    async def test_qualified_other_tenant_cannot_claim_agent(self, owner):
        auth, agent, key, _ = await delegated(owner)
        other = await EnterpriseIAM(owner[0]).create_workspace(
            actor_user_id=owner[2].user_id,
            name="Other tenant",
            slug=f"other-{uuid.uuid4().hex}",
            kind="ORGANIZATION",
        )
        org = other["id"] if isinstance(other, dict) else other.id
        challenge = await owner[1].begin_webauthn(
            user_id=None, session_id=None, ceremony="authenticate"
        )
        c, a, s = assertion_blob(
            rp_id="localhost",
            origin="http://localhost",
            challenge=b64url_decode(challenge["challenge"]),
            private_key=owner[5],
            sign_count=3,
        )
        _, _, session = await owner[1].authenticate_passkey(
            client_data_b64=c,
            authenticator_data_b64=a,
            signature_b64=s,
            credential_id=owner[6],
            org_id=org,
        )
        actor = replace(owner[2], org_id=org, session_id=session.session_id)
        with pytest.raises(EnterpriseError):
            await auth.begin_issue(actor, agent, key.public_key().public_bytes_raw().hex())

    @pytest.mark.asyncio
    async def test_durable_rate_limit_bounds_live_challenges(self, owner):
        auth, agent, key, _ = await delegated(owner, issue=False)
        for _ in range(10):
            await auth.begin_issue(owner[2], agent, key.public_key().public_bytes_raw().hex())
        with pytest.raises(EnterpriseError) as error:
            await auth.begin_issue(owner[2], agent, key.public_key().public_bytes_raw().hex())
        assert error.value.http_status == 429
        async with owner[0].raw.connect() as conn:
            rows = (await conn.execute(select(challenges))).all()
        assert len(rows) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode", ["default", "production", "staging", "process-production", "sqlite"]
)
async def test_b1_gate_never_silently_enables_or_provisions(mode, monkeypatch):
    from sqlalchemy import inspect

    engine = create_engine(":memory:")
    settings = SimpleNamespace(
        dev_agent_auth_enabled=mode != "default", environment="development", is_production=False
    )
    if mode in {"production", "staging"}:
        settings.environment = mode
    if mode == "process-production":
        monkeypatch.setenv("WHITEPACT_ENV", "production")
    auth = DevelopmentAgentAuth(engine, settings)
    try:
        with pytest.raises(EnterpriseError) as error:
            await auth.initialize()
        assert error.value.code == ("B1_POSTGRES_REQUIRED" if mode == "sqlite" else "B1_DISABLED")
        async with engine.raw.connect() as conn:
            assert not await conn.run_sync(lambda c: inspect(c).has_table("dev_b1_credentials"))
    finally:
        await engine.close()
