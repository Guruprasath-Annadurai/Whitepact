# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-coverage campaign for enterprise identity security and IAM deny paths."""

from __future__ import annotations

import os
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from sqlalchemy import insert, update

from responsibleai.db.engine import (
    create_engine,
    org_security_policies,
    organization_sso_configs,
    organizations,
    web_memberships,
    web_users,
    webauthn_challenges,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.errors import (
    CHALLENGE_REPLAY,
    ENVIRONMENT_DISABLED,
    FORBIDDEN,
    INSUFFICIENT_SCOPE,
    MEMBERSHIP_REVOKED,
    ORG_SUSPENDED,
    PROVIDER_TOKEN_INVALID,
    STEP_UP_REQUIRED,
    UNAUTHENTICATED,
    WEBAUTHN_INVALID,
    WRONG_ENVIRONMENT,
    WRONG_TENANT,
    EnterpriseError,
)
from responsibleai.enterprise.roles import Permission
from responsibleai.enterprise.security.four_eyes import DEFAULT_DUAL_CONTROL_ACTIONS
from responsibleai.enterprise.security.policy import (
    AuthenticationSecurityPolicy,
    AuthMethod,
    OrgAuthPolicy,
    SensitiveAction,
)
from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter
from responsibleai.enterprise.security.service import (
    IdentitySecurityService,
    _iso,
    _now,
    _sha256_bytes,
)
from responsibleai.enterprise.security.webauthn import b64url_decode, b64url_encode
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import GovernanceStatus, Role
from tests.webauthn_fakes import registration_blob


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
        name="Branch Org",
        slug=f"br-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    return org["id"]


# ── IdentitySecurityService: construction & policy ───────────────────────────


@pytest.mark.asyncio
async def test_post_init_uses_injected_policy_limiter_and_audit(engine) -> None:
    policy = AuthenticationSecurityPolicy()
    limiter = DurableIdentityRateLimiter(engine)
    audit = EnterpriseAuditLog(engine)
    svc = IdentitySecurityService(
        engine,
        policy=policy,
        limiter=limiter,
        audit=audit,
    )
    assert svc.policy is policy
    assert svc.limiter is limiter
    assert svc.audit is audit
    assert svc.oauth is not None
    assert svc.four_eyes is not None


@pytest.mark.asyncio
async def test_raw_id_token_denied_in_production_even_when_flag_true(engine) -> None:
    svc = await _svc(engine, allow_raw_id_token=True, google_client_id="google-client")
    with patch.dict(os.environ, {"WHITEPACT_ENV": "production"}, clear=False):
        assert svc._raw_id_token_permitted() is False
    with pytest.raises(EnterpriseError) as exc:
        await svc.google_login(id_token="unused", nonce="n1")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_org_policy_default_and_database_branches(engine) -> None:
    svc = await _svc(engine)
    default = await svc._org_policy(None)
    assert default == OrgAuthPolicy()

    owner = await _user(engine)
    org_id = await _org(engine, owner)
    missing = await svc._org_policy(org_id)
    assert missing.sso_enforcement == "SSO_OPTIONAL"
    assert missing.dual_control_actions == ()

    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(org_security_policies).values(
                org_id=org_id,
                phishing_resistant_required=1,
                privileged_roles_json='["OWNER"]',
                sso_enforcement="SSO_REQUIRED",
                dual_control_json="[]",
                break_glass_user_id=owner,
                updated_at=now,
            )
        )
    from_row = await svc._org_policy(org_id)
    assert from_row.phishing_resistant_required is True
    assert from_row.break_glass_user_id == owner
    assert from_row.dual_control_actions == tuple(DEFAULT_DUAL_CONTROL_ACTIONS)

    sso_org = await _org(engine, await _user(engine, "sso-only@example.com"))
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organization_sso_configs).values(
                id=str(uuid.uuid4()),
                org_id=sso_org,
                protocol="OIDC",
                issuer="https://idp.example.com",
                client_id="cid",
                client_secret_encrypted=None,
                redirect_uri="https://app/cb",
                enforcement="SSO_REQUIRED",
                provisioning="JIT_OPT_IN",
                created_by=owner,
                created_at=now,
                updated_at=now,
            )
        )
    from_sso = await svc._org_policy(sso_org)
    assert from_sso.sso_enforcement == "SSO_REQUIRED"
    assert from_sso.sso_provisioning == "JIT_OPT_IN"


@pytest.mark.asyncio
async def test_consume_replay_duplicate_denied(engine) -> None:
    svc = await _svc(engine)
    await svc.consume_replay("totp", "timestep-42")
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_replay("totp", "timestep-42")
    assert exc.value.code == CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_begin_webauthn_unknown_ceremony_and_register_without_user(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as unknown:
        await svc.begin_webauthn(user_id="u", session_id="s", ceremony="upgrade")
    assert unknown.value.code == WEBAUTHN_INVALID
    with pytest.raises(EnterpriseError) as need_user:
        await svc.begin_webauthn(user_id=None, session_id="s", ceremony="register")
    assert need_user.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_consume_challenge_fail_closed_branches(engine) -> None:
    user_a = await _user(engine, "a@example.com")
    user_b = await _user(engine, "b@example.com")
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_a)

    begin = await svc.begin_webauthn(
        user_id=user_a, session_id=session.session_id, ceremony="register"
    )
    challenge_b64 = begin["challenge"]

    async with engine.raw.begin() as conn:
        with pytest.raises(EnterpriseError) as missing:
            await svc._consume_challenge(
                conn, challenge_b64=b64url_encode(b"not-in-db"), ceremony="register", user_id=user_a
            )
        assert missing.value.code == CHALLENGE_REPLAY

    async with engine.raw.begin() as conn:
        digest = _sha256_bytes(b64url_decode(challenge_b64))
        await conn.execute(
            update(webauthn_challenges)
            .where(webauthn_challenges.c.challenge_hash == digest)
            .values(expires_at=_iso(_now() - timedelta(minutes=5)))
        )
    async with engine.raw.begin() as conn:
        with pytest.raises(EnterpriseError) as expired:
            await svc._consume_challenge(
                conn, challenge_b64=challenge_b64, ceremony="register", user_id=user_a
            )
        assert expired.value.code == CHALLENGE_REPLAY
        assert "expired" in expired.value.message.lower()

    begin2 = await svc.begin_webauthn(
        user_id=user_a, session_id=session.session_id, ceremony="register"
    )
    async with engine.raw.begin() as conn:
        with pytest.raises(EnterpriseError) as ceremony:
            await svc._consume_challenge(
                conn, challenge_b64=begin2["challenge"], ceremony="authenticate", user_id=user_a
            )
        assert ceremony.value.code == WEBAUTHN_INVALID

    begin3 = await svc.begin_webauthn(
        user_id=user_a, session_id=session.session_id, ceremony="register"
    )
    other_svc = IdentitySecurityService(engine, rp_id="evil.example", origin="https://evil.example")
    async with engine.raw.begin() as conn:
        with pytest.raises(EnterpriseError) as rp:
            await other_svc._consume_challenge(
                conn, challenge_b64=begin3["challenge"], ceremony="register", user_id=user_a
            )
        assert rp.value.code == WEBAUTHN_INVALID

    begin4 = await svc.begin_webauthn(
        user_id=user_b, session_id=session.session_id, ceremony="register"
    )
    async with engine.raw.begin() as conn:
        with pytest.raises(EnterpriseError) as bound:
            await svc._consume_challenge(
                conn, challenge_b64=begin4["challenge"], ceremony="register", user_id=user_a
            )
        assert bound.value.code == WEBAUTHN_INVALID

    auth_begin = await svc.begin_webauthn(
        user_id=user_a, session_id=session.session_id, ceremony="authenticate"
    )
    async with engine.raw.begin() as conn:
        with pytest.raises(EnterpriseError) as cross:
            await svc._consume_challenge(
                conn,
                challenge_b64=auth_begin["challenge"],
                ceremony="authenticate",
                user_id=user_b,
            )
        assert cross.value.code == WEBAUTHN_INVALID


@pytest.mark.asyncio
async def test_finish_registration_user_mismatch_and_step_up_replay(engine) -> None:
    user_id = await _user(engine)
    other = await _user(engine, "other@example.com")
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    begin = await svc.begin_webauthn(
        user_id=user_id, session_id=session.session_id, ceremony="register"
    )
    challenge = b64url_decode(begin["challenge"])
    key = generate_private_key(SECP256R1())
    cdata, adata, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as mismatch:
        await svc.finish_passkey_registration(
            user_id=other,
            session=session,
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            grant=grant,
        )
    assert mismatch.value.code == UNAUTHENTICATED

    grant2 = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    await svc.finish_passkey_registration(
        user_id=user_id,
        session=session,
        client_data_b64=cdata,
        authenticator_data_b64=adata,
        grant=grant2,
    )
    grant3 = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as replay:
        await svc.finish_passkey_registration(
            user_id=user_id,
            session=session,
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            grant=grant3,
        )
    assert replay.value.code == CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_load_session_org_membership_and_governance_denials(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    token, _, _ = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSWORD,),
        org_id=org_id,
        ip_label=None,
        user_agent=None,
    )
    await svc.load_session(f"{token}.csrf")

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(
                web_memberships.c.user_id == owner,
                web_memberships.c.org_id == org_id,
            )
            .values(status="REVOKED")
        )
    with pytest.raises(EnterpriseError) as revoked:
        await svc.load_session(token)
    assert revoked.value.code == UNAUTHENTICATED

    token2, _, _ = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSWORD,),
        org_id=org_id,
        ip_label=None,
        user_agent=None,
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(
                web_memberships.c.user_id == owner,
                web_memberships.c.org_id == org_id,
            )
            .values(status="ACTIVE")
        )
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(governance_status=GovernanceStatus.SUSPENDED.value)
        )
    with pytest.raises(EnterpriseError) as suspended:
        await svc.load_session(token2)
    assert suspended.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_step_up_grant_missing_and_double_consume(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    with pytest.raises(EnterpriseError) as missing:
        await svc.consume_step_up(session, SensitiveAction.ADD_PASSKEY, "missing-grant")
    assert missing.value.code == STEP_UP_REQUIRED

    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    await svc.consume_step_up(session, SensitiveAction.ADD_PASSKEY, grant)
    with pytest.raises(EnterpriseError) as replay:
        await svc.consume_step_up(session, SensitiveAction.ADD_PASSKEY, grant)
    assert replay.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_issue_session_rotate_from_and_raw_token_load(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    token1, _, _ = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    token2, _, assurance = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSWORD,),
        ip_label=None,
        user_agent=None,
        rotate_from=token1,
    )
    loaded = await svc.load_session(token2)
    assert loaded[2].session_id == assurance.session_id


# ── EnterpriseIAM deny paths ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_authorize_cross_tenant_membership_and_missing_org(engine) -> None:
    iam = EnterpriseIAM(engine)
    alice = await _user(engine, "alice@example.com")
    bob = await _user(engine, "bob@example.com")
    org_a = await iam.create_workspace(
        actor_user_id=alice, name="A", slug=f"a-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    org_b = await iam.create_workspace(
        actor_user_id=bob, name="B", slug=f"b-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    actor_a = _actor(alice, org_a["id"], Role.OWNER)
    with pytest.raises(EnterpriseError) as tenant:
        await iam.authorize(actor_a, Permission.ORG_UPDATE_SETTINGS, org_id=org_b["id"])
    assert tenant.value.code == WRONG_TENANT

    revoked = _actor(alice, org_a["id"], Role.OWNER, membership_status="REVOKED")
    with pytest.raises(EnterpriseError) as membership:
        await iam.authorize(revoked, Permission.ORG_VIEW, org_id=org_a["id"])
    assert membership.value.code == MEMBERSHIP_REVOKED

    ghost = _actor(alice, str(uuid.uuid4()), Role.OWNER)
    with pytest.raises(EnterpriseError) as missing:
        await iam.authorize(ghost, Permission.ORG_VIEW, org_id=ghost.org_id)
    assert missing.value.code == WRONG_TENANT


@pytest.mark.asyncio
async def test_authorize_suspended_org_and_environment_scope_denials(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine, "own@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"s-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    viewer = _actor(owner, org["id"], Role.VIEWER)
    with pytest.raises(EnterpriseError) as rbac:
        await iam.authorize(viewer, Permission.ENV_WRITE, org_id=org["id"])
    assert rbac.value.code == FORBIDDEN

    api_actor = Actor(
        actor_type="api_key",
        actor_id="key-1",
        user_id=owner,
        org_id=org["id"],
        role=Role.DEVELOPER,
        membership_status="ACTIVE",
        scopes=frozenset({"governance:read"}),
        environment_id=envs["DEVELOPMENT"]["id"],
    )
    with pytest.raises(EnterpriseError) as scope:
        await iam.authorize(
            api_actor,
            Permission.API_KEYS_CREATE,
            org_id=org["id"],
            required_scope="approvals:write",
        )
    assert scope.value.code == INSUFFICIENT_SCOPE

    await iam.set_environment_status(actor, org["id"], envs["DEVELOPMENT"]["id"], status="DISABLED")
    with pytest.raises(EnterpriseError) as env_disabled:
        await iam.authorize(
            actor,
            Permission.ENV_READ,
            org_id=org["id"],
            environment_id=envs["DEVELOPMENT"]["id"],
        )
    assert env_disabled.value.code == ENVIRONMENT_DISABLED

    bound_key = Actor(
        actor_type="api_key",
        actor_id="key-2",
        user_id=owner,
        org_id=org["id"],
        role=Role.DEVELOPER,
        membership_status="ACTIVE",
        environment_id=envs["DEVELOPMENT"]["id"],
    )
    with pytest.raises(EnterpriseError) as wrong_env:
        await iam.authorize(
            bound_key,
            Permission.ENV_READ,
            org_id=org["id"],
            environment_id=envs["STAGING"]["id"],
        )
    assert wrong_env.value.code == WRONG_ENVIRONMENT

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org["id"])
            .values(governance_status=GovernanceStatus.SUSPENDED.value)
        )
    with pytest.raises(EnterpriseError) as suspended:
        await iam.authorize(actor, Permission.MEMBERS_INVITE, org_id=org["id"])
    assert suspended.value.code == ORG_SUSPENDED

    auditor = _actor(owner, org["id"], Role.AUDITOR)
    await iam.authorize(auditor, Permission.AUDIT_READ, org_id=org["id"])


@pytest.mark.asyncio
async def test_workspace_create_and_settings_noop_branches(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine, "ws@example.com")
    with pytest.raises(EnterpriseError) as kind:
        await iam.create_workspace(
            actor_user_id=owner, name="Bad", slug=f"x-{uuid.uuid4().hex[:8]}", kind="TEAM"
        )
    assert kind.value.code == FORBIDDEN

    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == owner).values(disabled=1))
    with pytest.raises(EnterpriseError) as disabled:
        await iam.create_workspace(
            actor_user_id=owner, name="Nope", slug=f"y-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
        )
    assert disabled.value.code == FORBIDDEN

    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == owner).values(disabled=0))
    org = await iam.create_workspace(
        actor_user_id=owner, name="Good", slug=f"z-{uuid.uuid4().hex[:8]}", kind="INDIVIDUAL"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    unchanged = await iam.update_settings(actor, org["id"], display_name=None, settings=None)
    assert unchanged["id"] == org["id"]


@pytest.mark.asyncio
async def test_transfer_invite_accept_and_role_revoke_denials(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine, "xfer@example.com")
    admin = await _user(engine, "admin@example.com")
    outsider = await _user(engine, "out@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Xfer", slug=f"t-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    owner_actor = _actor(owner, org["id"], Role.OWNER)
    _, invite = await iam.invite_member(
        owner_actor, org["id"], email="admin@example.com", role=Role.ADMIN
    )
    await iam.accept_invitation(token=invite, user_id=admin)
    admin_actor = _actor(admin, org["id"], Role.ADMIN)

    with pytest.raises(EnterpriseError):
        await iam.transfer_ownership(
            admin_actor, org["id"], new_owner_user_id=admin, confirmation="NOPE"
        )
    with pytest.raises(EnterpriseError):
        await iam.transfer_ownership(
            admin_actor, org["id"], new_owner_user_id=outsider, confirmation="TRANSFER_OWNERSHIP"
        )

    with pytest.raises(EnterpriseError):
        await iam.invite_member(owner_actor, org["id"], email="x@example.com", role=Role.OWNER)

    with pytest.raises(EnterpriseError) as not_found:
        await iam.accept_invitation(token="totally-invalid-token", user_id=outsider)
    assert not_found.value.code == FORBIDDEN

    with pytest.raises(EnterpriseError):
        await iam.change_role(admin_actor, org["id"], user_id=admin, role=Role.OWNER)

    with pytest.raises(EnterpriseError):
        await iam.change_role(admin_actor, org["id"], user_id=outsider, role=Role.VIEWER)

    with pytest.raises(EnterpriseError):
        await iam.revoke_member(admin_actor, org["id"], user_id=outsider)


@pytest.mark.asyncio
async def test_environment_mutations_invalid_inputs(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine, "env@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Env", slug=f"e-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    await iam.ensure_default_environments(org["id"])
    await iam.ensure_default_environments(org["id"])

    with pytest.raises(EnterpriseError) as bad_type:
        await iam.create_environment(actor, org["id"], env_type="SANDBOX", name="X")
    assert bad_type.value.code == FORBIDDEN

    envs = await iam.list_environments(actor, org["id"])
    env_id = envs[0]["id"]
    with pytest.raises(EnterpriseError) as bad_status:
        await iam.set_environment_status(actor, org["id"], env_id, status="FROZEN")
    assert bad_status.value.code == FORBIDDEN

    with pytest.raises(EnterpriseError) as missing_env:
        await iam.set_environment_status(actor, org["id"], str(uuid.uuid4()), status="DISABLED")
    assert missing_env.value.code == WRONG_ENVIRONMENT


@pytest.mark.asyncio
async def test_accept_invitation_active_membership_race_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine, "race@example.com")
    member = await _user(engine, "race-member@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Race", slug=f"r-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    _, token = await iam.invite_member(
        actor, org["id"], email="race-member@example.com", role=Role.DEVELOPER
    )
    await iam.accept_invitation(token=token, user_id=member)
    _, token2 = await iam.invite_member(
        actor, org["id"], email="race-member@example.com", role=Role.VIEWER
    )
    with pytest.raises(EnterpriseError) as active:
        await iam.accept_invitation(token=token2, user_id=member)
    assert active.value.code == FORBIDDEN
