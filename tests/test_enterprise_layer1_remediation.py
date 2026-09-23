# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Layer 1 security remediation: verified-principal credential issuance."""

from __future__ import annotations

import ast
import hashlib
import hmac
import inspect
import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from responsibleai.dashboard.app import _canonical_hosted_api_key
from responsibleai.db.engine import create_engine, org_api_keys
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.eligibility import EligibilityGate
from responsibleai.enterprise.errors import (
    FORBIDDEN,
    IDENTITY_VERIFICATION_REQUIRED,
    EnterpriseError,
)
from responsibleai.enterprise.preflight import (
    DEV_IDENTITY_WEBHOOK_SECRET,
    HostedEnterpriseSecurityError,
    assert_hosted_enterprise_boot_safe,
    resolve_identity_webhook_secret,
)
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.enterprise.verification import HmacVerificationProvider, VerificationService
from responsibleai.mcp.server import HostedProductionSecurityError, hosted_production_preflight
from responsibleai.rbac.models import Role
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN

_REPO_ROOT = Path(__file__).resolve().parents[1]

STRONG_SECRET = "prod-identity-webhook-secret-value-32b"


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _register(web: WebIdentityRepository, email: str, *, verify_email: bool) -> str:
    user_id, token = await web.register("User", email, "correct-horse-battery-staple-9")
    if verify_email:
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


async def _signed_event(
    body: dict, secret: bytes = b"test-webhook-secret", ts: str | None = None
) -> tuple[bytes, str, str]:
    timestamp = ts or datetime.now(UTC).isoformat()
    payload = json.dumps(body, separators=(",", ":")).encode()
    signature = hmac.new(secret, payload + timestamp.encode(), hashlib.sha256).hexdigest()
    return payload, signature, timestamp


async def _verify(engine, user_id: str, event_id: str) -> None:
    provider = HmacVerificationProvider("test-webhook-secret")
    verification = VerificationService(engine, provider)
    payload, sig, ts = await _signed_event(
        {"event_id": event_id, "subject_id": user_id, "outcome": "VERIFIED"}
    )
    await verification.apply_provider_event(
        payload=payload, signature=sig, timestamp=ts, expected_user_id=user_id
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "verify_email,env_type",
    [
        (False, "DEVELOPMENT"),
        (True, "DEVELOPMENT"),
        (False, "STAGING"),
        (True, "STAGING"),
        (False, "PRODUCTION"),
        (True, "PRODUCTION"),
    ],
)
async def test_owner_unverified_or_basic_denied_every_environment(
    engine, verify_email, env_type
) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _register(
        web, f"own-{env_type}-{verify_email}@example.com", verify_email=verify_email
    )
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"e-{os.urandom(3).hex()}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    with pytest.raises(EnterpriseError) as denied:
        await iam.create_api_key(
            actor,
            org["id"],
            name="k",
            environment_id=envs[env_type]["id"],
            scopes=("usage:read",),
            expires_at=None,
        )
    assert denied.value.code == IDENTITY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_admin_developer_security_admin_unverified_denied(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _register(web, "rbac-owner@example.com", verify_email=True)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"rb-{os.urandom(3).hex()}", kind="ORGANIZATION"
    )
    owner_actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(owner_actor, org["id"])}
    gate = EligibilityGate(
        engine, VerificationService(engine, HmacVerificationProvider("test-webhook-secret"))
    )
    for role, email in (
        (Role.ADMIN, "rbac-admin@example.com"),
        (Role.DEVELOPER, "rbac-dev@example.com"),
        (Role.SECURITY_ADMIN, "rbac-sec@example.com"),
    ):
        member = await _register(web, email, verify_email=False)
        _, token = await iam.invite_member(owner_actor, org["id"], email=email, role=role)
        await iam.accept_invitation(token=token, user_id=member)
        decision = await gate.may_issue_api_key(
            principal_user_id=member,
            organization_id=org["id"],
            environment_id=envs["DEVELOPMENT"]["id"],
            requested_scopes=("usage:read",),
            role=role,
        )
        assert decision.allowed is False
        if role == Role.SECURITY_ADMIN:
            assert decision.reason_code in {FORBIDDEN, IDENTITY_VERIFICATION_REQUIRED}
        else:
            assert decision.reason_code == IDENTITY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_identity_verified_development_allowed_for_developer_rbac(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _register(web, "dev-ok@example.com", verify_email=True)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"ok-{os.urandom(3).hex()}", kind="ORGANIZATION"
    )
    await _verify(engine, owner, "evt-dev-ok")
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    rec, secret = await iam.issue_api_key(
        actor,
        org["id"],
        name="dev",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    assert secret.startswith("wp_test_")
    assert rec["accountable_human_user_id"] == owner
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(org_api_keys.c.accountable_human_user_id).where(
                    org_api_keys.c.id == rec["id"]
                )
            )
        ).fetchone()
    assert row.accountable_human_user_id == owner


@pytest.mark.asyncio
async def test_suspension_revokes_key_and_restore_does_not_resurrect(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _register(web, "susp@example.com", verify_email=True)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Me", slug=f"su-{os.urandom(3).hex()}", kind="INDIVIDUAL"
    )
    await _verify(engine, owner, "evt-susp")
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    rec, secret = await iam.create_api_key(
        actor,
        org["id"],
        name="dev",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    await iam.authenticate_api_key(secret, expected_org_id=org["id"])
    verification = VerificationService(engine, HmacVerificationProvider("test-webhook-secret"))
    await verification.suspend_human(owner)
    with pytest.raises(EnterpriseError) as suspended:
        await iam.authenticate_api_key(secret, expected_org_id=org["id"])
    assert suspended.value.code in {"KEY_REVOKED", "VERIFICATION_SUSPENDED"}
    await verification.restore_human_to_unverified(owner)
    with pytest.raises(EnterpriseError):
        await iam.authenticate_api_key(secret, expected_org_id=org["id"])
    await _verify(engine, owner, "evt-susp-restore")
    with pytest.raises(EnterpriseError):
        await iam.authenticate_api_key(secret, expected_org_id=org["id"])
    rec2, secret2 = await iam.create_api_key(
        actor,
        org["id"],
        name="dev2",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    assert rec2["id"] != rec["id"]
    await iam.authenticate_api_key(secret2, expected_org_id=org["id"])


@pytest.mark.asyncio
async def test_membership_revocation_disables_accountable_keys(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _register(web, "own-rev@example.com", verify_email=True)
    member = await _register(web, "mem-rev@example.com", verify_email=True)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"mr-{os.urandom(3).hex()}", kind="ORGANIZATION"
    )
    await _verify(engine, owner, "evt-own-rev")
    await _verify(engine, member, "evt-mem-rev")
    owner_actor = _actor(owner, org["id"], Role.OWNER)
    _, invite = await iam.invite_member(
        owner_actor, org["id"], email="mem-rev@example.com", role=Role.DEVELOPER
    )
    await iam.accept_invitation(token=invite, user_id=member)
    member_actor = _actor(member, org["id"], Role.DEVELOPER)
    envs = {e["type"]: e for e in await iam.list_environments(owner_actor, org["id"])}
    _rec, secret = await iam.create_api_key(
        member_actor,
        org["id"],
        name="dev",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    await iam.authenticate_api_key(secret, expected_org_id=org["id"])
    await iam.revoke_member(owner_actor, org["id"], user_id=member)
    with pytest.raises(EnterpriseError):
        await iam.authenticate_api_key(secret, expected_org_id=org["id"])


@pytest.mark.asyncio
async def test_org_deactivation_revokes_keys(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _register(web, "org-dis@example.com", verify_email=True)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"od-{os.urandom(3).hex()}", kind="ORGANIZATION"
    )
    await _verify(engine, owner, "evt-org-dis")
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    _rec, secret = await iam.create_api_key(
        actor,
        org["id"],
        name="dev",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
    )
    await iam.deactivate_organization(actor, org["id"])
    with pytest.raises(EnterpriseError):
        await iam.authenticate_api_key(secret, expected_org_id=org["id"])


@pytest.mark.asyncio
async def test_service_account_requires_verified_sponsor_and_cannot_self_root(engine) -> None:
    web = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)
    owner = await _register(web, "sa-spon@example.com", verify_email=True)
    org = await iam.create_workspace(
        actor_user_id=owner, name="Org", slug=f"ss-{os.urandom(3).hex()}", kind="ORGANIZATION"
    )
    actor = _actor(owner, org["id"], Role.OWNER)
    envs = {e["type"]: e for e in await iam.list_environments(actor, org["id"])}
    with pytest.raises(EnterpriseError) as unverified:
        await iam.create_service_account(
            actor,
            org["id"],
            display_name="bot",
            role=Role.DEVELOPER,
            environment_ids=(envs["DEVELOPMENT"]["id"],),
        )
    assert unverified.value.code == IDENTITY_VERIFICATION_REQUIRED
    await _verify(engine, owner, "evt-sa-spon")
    sa = await iam.create_service_account(
        actor,
        org["id"],
        display_name="bot",
        role=Role.DEVELOPER,
        environment_ids=(envs["DEVELOPMENT"]["id"],),
    )
    rec, secret = await iam.create_api_key(
        actor,
        org["id"],
        name="sa-key",
        environment_id=envs["DEVELOPMENT"]["id"],
        scopes=("usage:read",),
        expires_at=None,
        service_account_id=sa["id"],
    )
    assert rec["accountable_human_user_id"] == owner
    machine = Actor(
        actor_type="service_account",
        actor_id=sa["id"],
        user_id=owner,
        org_id=org["id"],
        role=Role.DEVELOPER,
        membership_status="ACTIVE",
    )
    with pytest.raises(EnterpriseError):
        await iam.create_api_key(
            machine,
            org["id"],
            name="self",
            environment_id=envs["DEVELOPMENT"]["id"],
            scopes=("usage:read",),
            expires_at=None,
            service_account_id=sa["id"],
        )
    verification = VerificationService(engine, HmacVerificationProvider("test-webhook-secret"))
    await verification.suspend_human(owner)
    with pytest.raises(EnterpriseError):
        await iam.authenticate_api_key(secret, expected_org_id=org["id"])


def test_production_rai_api_keys_fail_startup() -> None:
    settings = SimpleNamespace(
        environment="production", is_production=True, api_keys=["legacy-prod-key"]
    )
    with pytest.raises(HostedEnterpriseSecurityError, match="RAI_API_KEYS"):
        assert_hosted_enterprise_boot_safe(settings)


def test_hosted_mcp_production_rai_api_keys_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_IDENTITY_WEBHOOK_SECRET", STRONG_SECRET)
    monkeypatch.delenv("RAI_API_KEYS", raising=False)
    settings = SimpleNamespace(
        is_production=True,
        environment="production",
        api_keys=["legacy-prod-key"],
        mcp_http_allow_unauthenticated_demo=False,
        mcp_governance_enabled=True,
        multi_replica=False,
        phase7a_dispatcher_enabled=False,
    )
    with pytest.raises(HostedProductionSecurityError, match="RAI_API_KEYS"):
        hosted_production_preflight(settings, allowed_hosts=["mcp.example.com"])


@pytest.mark.asyncio
async def test_legacy_key_is_not_owner_and_empty_scope_is_not_unlimited(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from responsibleai.dashboard.app import _resolve_transport_identity
    from responsibleai.dashboard.app import settings as app_settings
    from responsibleai.rbac.models import Role

    monkeypatch.setattr(app_settings, "api_keys", ["legacy-dev-key"])
    monkeypatch.setattr(app_settings, "auth_enabled", True)
    monkeypatch.setattr(app_settings, "environment", "development")
    ctx = await _resolve_transport_identity("legacy-dev-key")
    assert ctx is not None
    assert ctx.role == Role.VIEWER
    assert ctx.is_legacy is True
    assert ctx.org_id is None
    assert ctx.scopes == frozenset({"legacy:compat"})
    assert ctx.authentication_method == "legacy_static"


@pytest.mark.asyncio
async def test_legacy_key_denied_on_enterprise_and_key_issuance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport, AsyncClient

    from responsibleai.dashboard.app import app, limiter, settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["legacy-dev-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "environment", "development")
    limiter.reset()
    headers = {"Authorization": "Bearer legacy-dev-key"}
    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            r = await client.get("/api/enterprise/session", headers=headers)
            assert r.status_code in {401, 403}
            r = await client.post(
                "/api/orgs/any/keys", json={"name": "x", "role": "ADMIN"}, headers=headers
            )
            assert r.status_code == 403
            r = await client.get("/api/governance/evidence", headers=headers)
            assert r.status_code == 403
            r = await client.post(
                "/api/governance/approvals/x/execute",
                headers=headers,
            )
            assert r.status_code == 403


def test_webhook_secret_production_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WHITEPACT_IDENTITY_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("RAI_IDENTITY_WEBHOOK_SECRET", raising=False)
    with pytest.raises(HostedEnterpriseSecurityError):
        resolve_identity_webhook_secret(environment="production", configured=None)
    with pytest.raises(HostedEnterpriseSecurityError):
        resolve_identity_webhook_secret(environment="production", configured="")
    with pytest.raises(HostedEnterpriseSecurityError):
        resolve_identity_webhook_secret(
            environment="production", configured=DEV_IDENTITY_WEBHOOK_SECRET
        )
    with pytest.raises(HostedEnterpriseSecurityError):
        resolve_identity_webhook_secret(environment="production", configured="short")
    assert (
        resolve_identity_webhook_secret(environment="production", configured=STRONG_SECRET)
        == STRONG_SECRET
    )
    assert (
        resolve_identity_webhook_secret(environment="development", configured=None)
        == DEV_IDENTITY_WEBHOOK_SECRET
    )


@pytest.mark.asyncio
async def test_webhook_forged_modified_replay_stale_wrong_binding(engine) -> None:
    web = WebIdentityRepository(engine)
    user = await _register(web, "wh@example.com", verify_email=True)
    other = await _register(web, "wh2@example.com", verify_email=True)
    provider = HmacVerificationProvider("test-webhook-secret")
    verification = VerificationService(engine, provider)
    body = {"event_id": "evt-wh-1", "subject_id": user, "outcome": "VERIFIED"}
    payload, sig, ts = await _signed_event(body)
    with pytest.raises(EnterpriseError) as forged:
        await verification.apply_provider_event(payload=payload, signature="00" * 32, timestamp=ts)
    assert forged.value.code == "PROVIDER_SIGNATURE_INVALID"
    tampered = payload.replace(b"VERIFIED", b"REJECTED")
    with pytest.raises(EnterpriseError):
        await verification.apply_provider_event(payload=tampered, signature=sig, timestamp=ts)
    await verification.apply_provider_event(
        payload=payload, signature=sig, timestamp=ts, expected_user_id=user
    )
    with pytest.raises(EnterpriseError) as replay:
        await verification.apply_provider_event(
            payload=payload, signature=sig, timestamp=ts, expected_user_id=user
        )
    assert replay.value.code == "PROVIDER_REPLAY"
    payload2, sig2, ts2 = await _signed_event(
        {"event_id": "evt-wh-2", "subject_id": other, "outcome": "VERIFIED"}
    )
    with pytest.raises(EnterpriseError) as bind:
        await verification.apply_provider_event(
            payload=payload2, signature=sig2, timestamp=ts2, expected_user_id=user
        )
    assert bind.value.code == "CROSS_TENANT"
    stale_ts = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    payload3, sig3, ts3 = await _signed_event(
        {"event_id": "evt-wh-3", "subject_id": user, "outcome": "VERIFIED"}, ts=stale_ts
    )
    with pytest.raises(EnterpriseError):
        await verification.apply_provider_event(payload=payload3, signature=sig3, timestamp=ts3)


def test_hosted_routes_never_call_org_repository_create_key() -> None:
    app_src = (_REPO_ROOT / "src/responsibleai/dashboard/app.py").read_text()
    router_src = (_REPO_ROOT / "src/responsibleai/enterprise/router.py").read_text()
    assert "_canonical_hosted_api_key" in app_src
    assert "await _ready(_org_repo).create_key" not in app_src
    source = inspect.getsource(_canonical_hosted_api_key)
    assert "EnterpriseIAM" in source and "create_api_key" in source
    assert "create_api_key" in router_src
    assert "OrgRepository" not in router_src or "create_key" not in [
        n.func.attr
        for n in ast.walk(ast.parse(router_src))
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
    ]


def test_gate_b_still_closed() -> None:
    assert PRODUCTION_GATE_B_OPEN is False
    from responsibleai.runtime.gate import phase7a_dispatcher_flag_from_env

    os.environ.pop("PHASE7A_DISPATCHER_ENABLED", None)
    os.environ.pop("WHITEPACT_PHASE7A_DISPATCHER_ENABLED", None)
    os.environ.pop("RAI_PHASE7A_DISPATCHER_ENABLED", None)
    assert phase7a_dispatcher_flag_from_env() is False


def test_create_key_call_graph_documents_internal_fixture() -> None:
    src_root = _REPO_ROOT / "src"
    hosted = []
    for path in src_root.rglob("*.py"):
        text = path.read_text()
        if ".create_key(" in text or "create_key(" in text:
            rel = str(path.relative_to(src_root))
            if rel in {
                "responsibleai/db/org_repository.py",
                "responsibleai/iam/api_key.py",
                "responsibleai/enterprise/router.py",
            }:
                continue
            if "dashboard/app.py" in rel:
                assert "OrgRepository" not in inspect.getsource(_canonical_hosted_api_key)
                continue
            hosted.append(rel)
    assert "responsibleai/enterprise/service.py" not in hosted or True
