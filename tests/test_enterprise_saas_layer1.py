# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise SaaS Layer 1 security matrix and verified-principal gate."""

from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from responsibleai.db.engine import create_engine, org_api_keys, web_invitations
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.eligibility import EligibilityGate
from responsibleai.enterprise.errors import (
    IDENTITY_VERIFICATION_REQUIRED,
    LAST_OWNER,
    ORGANIZATION_VERIFICATION_REQUIRED,
    EnterpriseError,
)
from responsibleai.enterprise.roles import ROLE_PERMISSIONS, Permission, has_rbac_permission
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.enterprise.verification import HmacVerificationProvider, VerificationService
from responsibleai.rbac.models import Role
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _user(web: WebIdentityRepository, email: str, name: str = "User") -> str:
    user_id, token = await web.register(name, email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


def _actor(user_id: str, org_id: str, role: Role) -> Actor:
    return Actor(
        actor_type="human",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        membership_status="ACTIVE",
    )


async def _signed_event(provider: HmacVerificationProvider, body: dict, ts: str | None = None) -> tuple[bytes, str, str]:
    timestamp = ts or datetime.now(UTC).isoformat()
    payload = json.dumps(body, separators=(",", ":")).encode()
    signature = hmac.new(
        b"test-webhook-secret", payload + timestamp.encode(), hashlib.sha256
    ).hexdigest()
    return payload, signature, timestamp


@pytest.mark.asyncio
async def test_rbac_permission_matrix_covers_every_role_and_permission() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)
    for role in Role:
        for permission in Permission:
            expected = permission in ROLE_PERMISSIONS[role]
            assert has_rbac_permission(role, permission) is expected, (role, permission)
    assert has_rbac_permission(Role.BILLING_ADMIN, Permission.ORG_TRANSFER_OWNERSHIP) is False
    assert has_rbac_permission(Role.VIEWER, Permission.API_KEYS_CREATE) is False
    assert has_rbac_permission(Role.AUDITOR, Permission.MEMBERS_REVOKE) is False
    assert has_rbac_permission(Role.OWNER, Permission.ORG_TRANSFER_OWNERSHIP) is True
    assert PRODUCTION_GATE_B_OPEN is False


@pytest.mark.asyncio
async def test_cross_tenant_enumeration_and_update_denied(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    alice = await _user(web, "alice@example.com", "Alice")
    bob = await _user(web, "bob@example.com", "Bob")
    org_a = await iam.create_workspace(actor_user_id=alice, name="A Co", slug=f"a-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    org_b = await iam.create_workspace(actor_user_id=bob, name="B Co", slug=f"b-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    visible = await iam.list_visible_workspaces(alice)
    assert {row["id"] for row in visible} == {org_a["id"]}
    actor_a = _actor(alice, org_a["id"], Role.OWNER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.update_settings(actor_a, org_b["id"], display_name="Hijack", settings=None)
    assert exc.value.code == "WRONG_TENANT"


@pytest.mark.asyncio
async def test_disabled_org_denies_mutations(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "owner@example.com")
    org = await iam.create_workspace(actor_user_id=owner, name="Org", slug=f"o-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    actor = _actor(owner, org["id"], Role.OWNER)
    await iam.deactivate_organization(actor, org["id"])
    with pytest.raises(EnterpriseError) as exc:
        await iam.update_settings(actor, org["id"], display_name="Nope", settings=None)
    assert exc.value.code == "ORG_DISABLED"


@pytest.mark.asyncio
async def test_last_owner_protection(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "last@example.com")
    org = await iam.create_workspace(actor_user_id=owner, name="Solo", slug=f"s-{uuid.uuid4().hex[:8]}", kind="INDIVIDUAL")
    actor = _actor(owner, org["id"], Role.OWNER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.revoke_member(actor, org["id"], user_id=owner)
    assert exc.value.code == LAST_OWNER


@pytest.mark.asyncio
async def test_invite_theft_replay_expiry_and_revoke(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "own@example.com")
    thief = await _user(web, "thief@example.com")
    invitee = await _user(web, "invitee@example.com")
    org = await iam.create_workspace(actor_user_id=owner, name="Org", slug=f"i-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    actor = _actor(owner, org["id"], Role.OWNER)
    invitation_id, token = await iam.invite_member(actor, org["id"], email="invitee@example.com", role=Role.DEVELOPER)
    with pytest.raises(EnterpriseError):
        await iam.accept_invitation(token=token, user_id=thief)
    org_id = await iam.accept_invitation(token=token, user_id=invitee)
    assert org_id == org["id"]
    with pytest.raises(EnterpriseError) as replay:
        await iam.accept_invitation(token=token, user_id=invitee)
    assert replay.value.code in {"INVITE_REPLAY", "FORBIDDEN"}

    _, token2 = await iam.invite_member(actor, org["id"], email="late@example.com", role=Role.VIEWER)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_invitations)
            .where(web_invitations.c.token_hash == hashlib.sha256(token2.encode()).hexdigest())
            .values(expires_at=(datetime.now(UTC) - timedelta(hours=1)).isoformat())
        )
    late = await _user(web, "late@example.com")
    with pytest.raises(EnterpriseError) as expired:
        await iam.accept_invitation(token=token2, user_id=late)
    assert expired.value.code == "INVITE_EXPIRED"

    _, token3 = await iam.invite_member(actor, org["id"], email="revoked@example.com", role=Role.VIEWER)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_invitations)
            .where(web_invitations.c.token_hash == hashlib.sha256(token3.encode()).hexdigest())
            .values(status="REVOKED")
        )
    revoked_user = await _user(web, "revoked@example.com")
    with pytest.raises(EnterpriseError) as rev:
        await iam.accept_invitation(token=token3, user_id=revoked_user)
    assert rev.value.code == "INVITE_REVOKED"
    assert invitation_id


@pytest.mark.asyncio
async def test_role_escalation_denied(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "esc-owner@example.com")
    dev = await _user(web, "esc-dev@example.com")
    org = await iam.create_workspace(actor_user_id=owner, name="Org", slug=f"e-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION")
    owner_actor = _actor(owner, org["id"], Role.OWNER)
    _, token = await iam.invite_member(owner_actor, org["id"], email="esc-dev@example.com", role=Role.DEVELOPER)
    await iam.accept_invitation(token=token, user_id=dev)
    dev_actor = _actor(dev, org["id"], Role.DEVELOPER)
    with pytest.raises(EnterpriseError):
        await iam.change_role(dev_actor, org["id"], user_id=dev, role=Role.ADMIN)
    with pytest.raises(EnterpriseError):
        await iam.invite_member(dev_actor, org["id"], email="x@example.com", role=Role.ADMIN)


@pytest.mark.asyncio
async def test_plaintext_api_key_never_persisted_and_env_isolation(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "keys@example.com")
    org = await iam.create_workspace(actor_user_id=owner, name="Org", slug=f"k-{uuid.uuid4().hex[:8]}", kind="INDIVIDUAL")
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    provider = HmacVerificationProvider("test-webhook-secret")
    verification = VerificationService(engine, provider)
    payload, sig, ts = await _signed_event(
        provider,
        {
            "event_id": "evt-idv-1",
            "subject_id": owner,
            "outcome": "VERIFIED",
            "assurance_level": "government_id",
        },
    )
    await verification.apply_provider_event(payload=payload, signature=sig, timestamp=ts, expected_user_id=owner)
    record, secret = await iam.create_api_key(
        actor,
        org["id"],
        name="dev",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("governance:read",),
        expires_at=None,
    )
    assert secret.startswith("wp_test_")
    async with engine.raw.connect() as conn:
        dumped = str((await conn.execute(select(org_api_keys))).fetchall())
        hashes = (await conn.execute(select(org_api_keys.c.key_hash))).scalars().all()
    assert secret not in dumped
    assert hashlib.sha256(secret.encode()).hexdigest() in hashes
    with pytest.raises(EnterpriseError) as wrong_env:
        await iam.authenticate_api_key(
            secret,
            expected_org_id=org["id"],
            expected_environment_id=envs["PRODUCTION"]["id"],
        )
    assert wrong_env.value.code == "WRONG_ENVIRONMENT"
    with pytest.raises(EnterpriseError) as scope_exc:
        await iam.authenticate_api_key(
            secret,
            expected_org_id=org["id"],
            expected_environment_id=envs["DEVELOPMENT"]["id"],
            required_scope="approvals:write",
        )
    assert scope_exc.value.code == "INSUFFICIENT_SCOPE"
    await iam.revoke_api_key(actor, org["id"], record["id"])
    with pytest.raises(EnterpriseError) as revoked:
        await iam.authenticate_api_key(secret, expected_org_id=org["id"])
    assert revoked.value.code == "KEY_REVOKED"


@pytest.mark.asyncio
async def test_unverified_and_email_only_production_key_denied(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "emailonly@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Me", slug=f"me-{uuid.uuid4().hex[:8]}", kind="INDIVIDUAL"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    with pytest.raises(EnterpriseError) as unverified_prod:
        await iam.create_api_key(
            actor,
            org["id"],
            name="prod",
            environment_id=envs["PRODUCTION"]["id"],
            scopes=("usage:read",),
            expires_at=None,
        )
    assert unverified_prod.value.code == IDENTITY_VERIFICATION_REQUIRED
    rec, secret = await iam.create_api_key(
        actor,
        org["id"],
        name="dev",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    assert rec["id"]
    assert secret


@pytest.mark.asyncio
async def test_org_production_requires_verified_org_and_verified_issuer(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "corp-owner@example.com")
    admin = await _user(web, "corp-admin@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Corp", slug=f"c-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    owner_actor = _actor(owner, org["id"], Role.OWNER)
    _, token = await iam.invite_member(owner_actor, org["id"], email="corp-admin@example.com", role=Role.ADMIN)
    await iam.accept_invitation(token=token, user_id=admin)
    admin_actor = _actor(admin, org["id"], Role.ADMIN)
    envs = {e["type"]: e for e in await iam.list_environments(owner_actor, org["id"])}
    provider = HmacVerificationProvider("test-webhook-secret")
    verification = VerificationService(engine, provider)

    payload, sig, ts = await _signed_event(
        provider, {"event_id": "evt-owner", "subject_id": owner, "outcome": "VERIFIED"}
    )
    await verification.apply_provider_event(payload=payload, signature=sig, timestamp=ts)

    with pytest.raises(EnterpriseError) as need_org:
        await iam.create_api_key(
            owner_actor,
            org["id"],
            name="prod",
            environment_id=envs["PRODUCTION"]["id"],
            scopes=("usage:read",),
            expires_at=None,
        )
    assert need_org.value.code == ORGANIZATION_VERIFICATION_REQUIRED

    payload, sig, ts = await _signed_event(
        provider,
        {
            "event_id": "evt-org",
            "kind": "organization",
            "org_id": org["id"],
            "outcome": "VERIFIED",
            "accountable_owner_user_id": owner,
            "legal_name": "Corp Inc",
        },
    )
    await verification.apply_provider_event(payload=payload, signature=sig, timestamp=ts, expected_org_id=org["id"])

    with pytest.raises(EnterpriseError) as admin_unverified:
        await iam.create_api_key(
            admin_actor,
            org["id"],
            name="prod",
            environment_id=envs["PRODUCTION"]["id"],
            scopes=("usage:read",),
            expires_at=None,
        )
    assert admin_unverified.value.code == IDENTITY_VERIFICATION_REQUIRED

    payload, sig, ts = await _signed_event(
        provider, {"event_id": "evt-admin", "subject_id": admin, "outcome": "VERIFIED"}
    )
    await verification.apply_provider_event(payload=payload, signature=sig, timestamp=ts)
    rec, secret = await iam.create_api_key(
        admin_actor,
        org["id"],
        name="prod",
        environment_id=envs["PRODUCTION"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    assert rec["accountable_human_user_id"] == admin
    assert secret.startswith("wp_live_")


@pytest.mark.asyncio
async def test_forged_replay_and_cross_tenant_verification_callbacks(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    user = await _user(web, "idv@example.com")
    other = await _user(web, "other@example.com")
    provider = HmacVerificationProvider("test-webhook-secret")
    verification = VerificationService(engine, provider)
    body = {"event_id": "evt-forge", "subject_id": user, "outcome": "VERIFIED"}
    payload, sig, ts = await _signed_event(provider, body)
    with pytest.raises(EnterpriseError) as forged:
        await verification.apply_provider_event(payload=payload, signature="deadbeef", timestamp=ts)
    assert forged.value.code == "PROVIDER_SIGNATURE_INVALID"
    await verification.apply_provider_event(payload=payload, signature=sig, timestamp=ts, expected_user_id=user)
    with pytest.raises(EnterpriseError) as replay:
        await verification.apply_provider_event(payload=payload, signature=sig, timestamp=ts, expected_user_id=user)
    assert replay.value.code == "PROVIDER_REPLAY"
    body2 = {"event_id": "evt-cross", "subject_id": other, "outcome": "VERIFIED"}
    payload, sig, ts = await _signed_event(provider, body2)
    with pytest.raises(EnterpriseError) as cross:
        await verification.apply_provider_event(
            payload=payload, signature=sig, timestamp=ts, expected_user_id=user
        )
    assert cross.value.code == "CROSS_TENANT"


@pytest.mark.asyncio
async def test_service_account_cannot_be_owner_or_unattributable(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "sa-owner@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"sa-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = await iam.list_environments(actor, org["id"])
    with pytest.raises(EnterpriseError):
        await iam.create_service_account(
            actor, org["id"], display_name="bot", role=Role.OWNER, environment_ids=(envs[0]["id"],)
        )
    machine = Actor(
        actor_type="service_account",
        actor_id="sa-x",
        user_id=None,
        org_id=org["id"],
        role=Role.ADMIN,
        membership_status="ACTIVE",
    )
    with pytest.raises(EnterpriseError) as provenance:
        await iam.create_service_account(
            machine, org["id"], display_name="bot2", role=Role.DEVELOPER, environment_ids=()
        )
    assert provenance.value.code == "SERVICE_ACCOUNT_FORBIDDEN"
    sa = await iam.create_service_account(
        actor, org["id"], display_name="deploy", role=Role.DEVELOPER, environment_ids=(envs[0]["id"],)
    )
    assert sa["created_by_user_id"] == owner


@pytest.mark.asyncio
async def test_rotation_overlap_then_revoke(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "rot@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Me", slug=f"r-{uuid.uuid4().hex[:8]}", kind="INDIVIDUAL"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    rec, old_secret = await iam.create_api_key(
        actor,
        org["id"],
        name="dev",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    new_rec, new_secret = await iam.rotate_api_key(actor, org["id"], rec["id"], overlap_seconds=3600)
    assert old_secret != new_secret
    await iam.authenticate_api_key(old_secret, expected_org_id=org["id"])
    await iam.authenticate_api_key(new_secret, expected_org_id=org["id"])
    await iam.revoke_api_key(actor, org["id"], rec["id"])
    with pytest.raises(EnterpriseError):
        await iam.authenticate_api_key(old_secret, expected_org_id=org["id"])
    await iam.authenticate_api_key(new_secret, expected_org_id=org["id"])
    with pytest.raises(EnterpriseError):
        await iam.rotate_api_key(actor, org["id"], rec["id"], overlap_seconds=0)


@pytest.mark.asyncio
async def test_sessions_logout_all_and_revoked_membership(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "sess@example.com")
    member = await _user(web, "sess-m@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"se-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    token, _csrf = await web.create_session(owner, org_id=org["id"])
    principal = await web.get_principal(token)
    assert principal is not None
    await iam.logout_all(owner)
    assert await web.get_principal(token) is None
    owner_actor = _actor(owner, org["id"], Role.OWNER)
    _, invite = await iam.invite_member(owner_actor, org["id"], email="sess-m@example.com", role=Role.VIEWER)
    await iam.accept_invitation(token=invite, user_id=member)
    member_token, _ = await web.create_session(member, org_id=org["id"])
    assert await web.get_principal(member_token) is not None
    await iam.revoke_member(owner_actor, org["id"], user_id=member)
    assert await web.get_principal(member_token) is None


@pytest.mark.asyncio
async def test_verified_owner_still_cannot_open_gate_b() -> None:
    assert PRODUCTION_GATE_B_OPEN is False
    from responsibleai.runtime.gate import phase7a_dispatcher_flag_from_env
    import os

    os.environ.pop("PHASE7A_DISPATCHER_ENABLED", None)
    os.environ.pop("WHITEPACT_PHASE7A_DISPATCHER_ENABLED", None)
    os.environ.pop("RAI_PHASE7A_DISPATCHER_ENABLED", None)
    assert phase7a_dispatcher_flag_from_env() is False


@pytest.mark.asyncio
async def test_invite_token_not_stored_plaintext(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "tok@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"t-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    _id, token = await iam.invite_member(actor, org["id"], email="n@example.com", role=Role.VIEWER)
    async with engine.raw.connect() as conn:
        blob = str((await conn.execute(select(web_invitations))).fetchall())
        hashes = (await conn.execute(select(web_invitations.c.token_hash))).scalars().all()
    assert token not in blob
    assert hashlib.sha256(token.encode()).hexdigest() in hashes


@pytest.mark.asyncio
async def test_eligibility_gate_owner_cannot_bypass_verification(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _user(web, "bypass@example.com")
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"byp-{uuid.uuid4().hex[:8]}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    gate = EligibilityGate(
        engine, VerificationService(engine, HmacVerificationProvider("test-webhook-secret"))
    )
    decision = await gate.may_issue_api_key(
        principal_user_id=owner,
        organization_id=org["id"],
        environment_id=envs["PRODUCTION"]["id"],
        requested_scopes=("governance:execute",),
        role=Role.OWNER,
    )
    assert decision.allowed is False
    assert decision.reason_code in {IDENTITY_VERIFICATION_REQUIRED, ORGANIZATION_VERIFICATION_REQUIRED}
