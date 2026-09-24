# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 16 branch-coverage: remaining arcs in ``dashboard/app.py`` HTTP/startup,
``enterprise/security/service.py``, ``db/web_identity_repository.py``,
``mcp/server.py``, ``data_governance/backup_defense.py``, and
``isolation/container_backend.py`` (OpenSSF gate closure)."""

from __future__ import annotations

import asyncio
import os
import subprocess
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import respx
from asgi_lifespan import LifespanManager
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select, update
from sqlalchemy.exc import SQLAlchemyError
from starlette.requests import Request

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

import responsibleai.dashboard.app as app_module
import responsibleai.mcp.server as mcp_server
from responsibleai.auth.saml import SAMLAssertionClaims
from responsibleai.billing.paddle_service import (
    PaddleBillingError,
    PaddleBillingService,
    PaddleCheckoutRequest,
    PaddleNotConfiguredError,
)
from responsibleai.billing.stripe_service import StripeNotConfiguredError
from responsibleai.dashboard.app import (
    _enforce_machine_scope,
    _get_rate_limit_key,
    _resolve_saml_context,
    app,
    limiter,
    settings,
)
from responsibleai.dashboard.middleware import AuthFailureLimiter
from responsibleai.data_governance.backup_defense import (
    LifecycleRollbackError,
    LifecycleState,
    LifecycleStateRecord,
    MissingLifecycleProviderError,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
    compute_lifecycle_digest,
    reset_restore_readiness_gate,
    resolve_store_b_path,
)
from responsibleai.db.engine import (
    create_engine,
    organizations,
    web_memberships,
    web_sessions,
    web_users,
)
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import (
    DuplicateWebUserError,
    InvitationError,
    WebIdentityRepository,
    hash_password,
    verify_password,
)
from responsibleai.enterprise.errors import (
    AUTHENTICATION_FAILED,
    CHALLENGE_REPLAY,
    FORBIDDEN,
    INSUFFICIENT_SCOPE,
    MEMBERSHIP_REVOKED,
    SECURITY_DOWNGRADE_BLOCKED,
    UNAUTHENTICATED,
    EnterpriseError,
)
from responsibleai.enterprise.roles import Permission
from responsibleai.enterprise.security.policy import AuthMethod, OrgAuthPolicy, SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.mcp.governance_integration import GovernanceOutcome
from responsibleai.mcp.server import _env_bool, _split_csv
from responsibleai.mcp.tools import WHITEPACT_PURPOSE_ARGUMENT
from responsibleai.rbac.models import GovernanceStatus, OrgContext, Plan, Role
from tests.org_http_fixtures import seed_org_with_key
from tests.webauthn_fakes import assertion_blob, registration_blob


@pytest.fixture(autouse=True)
def _reset_dashboard_provider_singletons() -> None:
    yield
    app_module._oidc_provider = None
    app_module._saml_config = None
    app_module._saml_txn_store = None
    app_module._stripe_service = None
    app_module._paddle_billing_service = None


@pytest.fixture()
async def client():
    orig_database_url = settings.database_url
    orig_db_path = settings.db_path
    orig_auto_migrate = settings.auto_migrate

    settings.database_url = None
    settings.db_path = ":memory:"
    settings.auto_migrate = False
    try:
        async with LifespanManager(app, startup_timeout=15) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as ac:
                yield ac
    finally:
        settings.database_url = orig_database_url
        settings.db_path = orig_db_path
        settings.auto_migrate = orig_auto_migrate


@pytest.fixture()
async def auth_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()
    app_module._auth_failure_limiter._failures.clear()

    async with LifespanManager(app, startup_timeout=15) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac

    app_module._auth_failure_limiter._failures.clear()


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


@pytest.fixture
async def web_repo(engine):
    return WebIdentityRepository(engine)


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


def _scope_request(method: str, path: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": []})


async def _verified_user(web: WebIdentityRepository, email: str) -> str:
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


async def _user(engine, email: str = "human@example.com") -> str:
    web = WebIdentityRepository(engine)
    return await _verified_user(web, email)


async def _org(engine, owner_id: str) -> str:
    web = WebIdentityRepository(engine)
    return await web.attach_organization(owner_id, name="Org", slug=f"org-{uuid.uuid4().hex[:8]}")


async def _svc(engine, **kwargs) -> IdentitySecurityService:
    return IdentitySecurityService(engine, rp_id="localhost", origin="http://localhost", **kwargs)


def _actor(
    user_id: str,
    org_id: str,
    role: Role,
    *,
    membership_status: str = "ACTIVE",
) -> Actor:
    return Actor(
        actor_type="human",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        membership_status=membership_status,
    )


def _lifecycle_record(
    tenant_id: str = "org-1",
    state: LifecycleState = LifecycleState.ACTIVE,
    *,
    epoch: int = 1,
    effective_at: str = "2026-01-01T00:00:00+00:00",
    generation_id: str = "gen-1",
) -> LifecycleStateRecord:
    digest = compute_lifecycle_digest(
        tenant_id=tenant_id,
        generation_id=generation_id,
        state=state.value,
        effective_at=effective_at,
        security_epoch=epoch,
    )
    return LifecycleStateRecord(
        tenant_id=tenant_id,
        generation_id=generation_id,
        state=state,
        effective_at=effective_at,
        security_epoch=epoch,
        digest=digest,
    )


# ── mcp/server.py ────────────────────────────────────────────────────────────


def _set_mcp_context(org_ctx: OrgContext | None, governance=None, usage_repo=None):
    org_token = mcp_server._current_org.set(org_ctx)
    gov_token = mcp_server._current_governance.set(governance)
    usage_token = mcp_server._current_usage_repo.set(usage_repo)
    return org_token, gov_token, usage_token


def _reset_mcp_context(tokens) -> None:
    org_token, gov_token, usage_token = tokens
    mcp_server._current_org.reset(org_token)
    mcp_server._current_governance.reset(gov_token)
    mcp_server._current_usage_repo.reset(usage_token)


@pytest.mark.asyncio
async def test_mcp_call_tool_requires_explicit_purpose(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = AsyncMock()
    monkeypatch.setattr(mcp_server, "dispatch_tool", dispatch)
    ctx = OrgContext(key_id="k16", role=Role.ANALYST, org_id="org-16", plan=Plan.ENTERPRISE)
    tokens = _set_mcp_context(ctx, governance=object())
    try:
        _, payload = await mcp_server._call_tool("rai_health", {})
        assert payload["error"] == "governance_purpose_required"
        dispatch.assert_not_awaited()
    finally:
        _reset_mcp_context(tokens)


@pytest.mark.asyncio
async def test_mcp_call_tool_rejects_whitespace_purpose(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = AsyncMock()
    monkeypatch.setattr(mcp_server, "dispatch_tool", dispatch)
    ctx = OrgContext(key_id="k16b", role=Role.ANALYST, org_id="org-16b", plan=Plan.ENTERPRISE)
    tokens = _set_mcp_context(ctx, governance=object())
    try:
        _, payload = await mcp_server._call_tool(
            "rai_health", {WHITEPACT_PURPOSE_ARGUMENT: "   \t  "}
        )
        assert payload["error"] == "governance_purpose_required"
    finally:
        _reset_mcp_context(tokens)


@pytest.mark.asyncio
async def test_mcp_call_tool_rejects_non_string_purpose(monkeypatch: pytest.MonkeyPatch) -> None:
    ctx = OrgContext(key_id="k16c", role=Role.ANALYST, org_id="org-16c", plan=Plan.ENTERPRISE)
    tokens = _set_mcp_context(ctx, governance=object())
    try:
        _, payload = await mcp_server._call_tool(
            "rai_health", {WHITEPACT_PURPOSE_ARGUMENT: {"not": "a string"}}
        )
        assert payload["error"] == "governance_purpose_required"
    finally:
        _reset_mcp_context(tokens)


@pytest.mark.asyncio
async def test_mcp_call_tool_governance_blocked_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.apply_governance",
        AsyncMock(
            return_value=GovernanceOutcome(
                proceed=False,
                arguments={},
                blocked_response={"error": "governance_blocked", "reason": "batch16"},
            )
        ),
    )
    ctx = OrgContext(key_id="k16d", role=Role.ANALYST, org_id="org-16d", plan=Plan.ENTERPRISE)
    tokens = _set_mcp_context(ctx, governance=object())
    try:
        _, payload = await mcp_server._call_tool(
            "rai_health", {WHITEPACT_PURPOSE_ARGUMENT: "batch16-purpose"}
        )
        assert payload["error"] == "governance_blocked"
        assert payload["reason"] == "batch16"
    finally:
        _reset_mcp_context(tokens)


def test_mcp_split_csv_strips_empty_segments() -> None:
    assert _split_csv(" a, ,b,,c ") == ["a", "b", "c"]


@pytest.mark.parametrize(
    ("env", "default", "expected"),
    [
        (None, False, False),
        ("yes", True, True),
        ("off", True, False),
        ("TRUE", False, True),
    ],
)
def test_mcp_env_bool_parsing(
    monkeypatch: pytest.MonkeyPatch, env: str | None, default: bool, expected: bool
) -> None:
    monkeypatch.delenv("RAI_BATCH16_BOOL", raising=False)
    if env is not None:
        monkeypatch.setenv("RAI_BATCH16_BOOL", env)
    assert _env_bool("RAI_BATCH16_BOOL", default=default) is expected


# ── dashboard/app.py lifespan + HTTP ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_lifespan_skips_paddle_when_misconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "saml_idp_entity_id", None)
    monkeypatch.setattr(settings, "oidc_issuer", None)
    monkeypatch.setattr(settings, "paddle_api_key", "pdl_sdbx_test_key")
    monkeypatch.setattr(settings, "paddle_env", "not-a-valid-env")
    app_module._paddle_billing_service = None
    async with LifespanManager(app, startup_timeout=15):
        assert app_module._paddle_billing_service is None


@pytest.mark.asyncio
async def test_lifespan_skips_stripe_when_misconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "saml_idp_entity_id", None)
    monkeypatch.setattr(settings, "oidc_issuer", None)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_batch16")
    monkeypatch.setattr(
        app_module,
        "StripeService",
        MagicMock(side_effect=StripeNotConfiguredError("missing price ids")),
    )
    app_module._stripe_service = None
    async with LifespanManager(app, startup_timeout=15):
        assert app_module._stripe_service is None


@pytest.mark.asyncio
async def test_public_health_and_metrics_endpoints(client: AsyncClient) -> None:
    for path in ("/healthz", "/livez", "/api/health", "/api/metrics"):
        r = await client.get(path)
        assert r.status_code == 200


@pytest.mark.asyncio
async def test_public_robots_and_restore_status(client: AsyncClient) -> None:
    r = await client.get("/robots.txt")
    assert r.status_code == 200
    assert "User-agent" in r.text or "Disallow" in r.text
    r2 = await client.get("/api/v1/restore/status")
    assert r2.status_code == 200


@pytest.mark.parametrize(
    ("method", "path", "scopes", "fragment"),
    [
        ("GET", "/api/governance/delegations", frozenset({"governance:write"}), "governance:read"),
        (
            "POST",
            "/api/governance/workflow-rules",
            frozenset({"evidence:read"}),
            "governance:write",
        ),
        ("GET", "/api/governance/upstream/servers", frozenset({"agents:read"}), "governance:read"),
    ],
)
def test_machine_scope_batch16_missing_scope(
    method: str, path: str, scopes: frozenset[str], fragment: str
) -> None:
    ctx = OrgContext(key_id="k-b16", role=Role.ADMIN, org_id="org-b16", scopes=scopes)
    with pytest.raises(HTTPException) as exc:
        _enforce_machine_scope(_scope_request(method, path), ctx)
    assert exc.value.status_code == 403
    assert fragment in str(exc.value.detail)


class TestDashboardDenyPathsBatch16:
    async def test_viewer_cannot_read_delegation_graph(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Deleg Graph Viewer",
            slug=f"del-g-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/delegations/graph", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_post_workflow_rule(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="WF Post Viewer",
            slug=f"wf-p-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/workflow-rules",
            json={"name": "rule", "sequence": []},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_list_upstream_servers(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Upstream List Viewer",
            slug=f"up-l-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/upstream/servers", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_put_org_sso_settings(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="SSO Viewer",
            slug=f"sso-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/sso",
            json={"sso_required": True},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_post_governance_tool_execute(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Tool Exec Viewer",
            slug=f"tex-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/tools/call",
            json={"tool": "rai_health", "arguments": {}},
            headers=_bearer(raw),
        )
        assert r.status_code == 403


def test_rate_limit_key_non_bearer_authorization_uses_ip() -> None:
    req = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/health",
            "headers": [(b"authorization", b"Basic abc")],
            "client": ("198.18.0.1", 9999),
        }
    )
    assert _get_rate_limit_key(req) == "198.18.0.1"


# ── web_identity_repository.py ───────────────────────────────────────────────


def test_verify_password_rejects_non_scrypt_algorithm() -> None:
    encoded = hash_password("secret-value-16chars!!")
    tampered = encoded.replace("scrypt", "bcrypt", 1)
    assert verify_password("secret-value-16chars!!", tampered) is False


@pytest.mark.asyncio
async def test_register_duplicate_email_raises(web_repo: WebIdentityRepository) -> None:
    await _verified_user(web_repo, "dup@example.com")
    with pytest.raises(DuplicateWebUserError):
        await web_repo.register("Dup", "dup@example.com", "another-password-12")


@pytest.mark.asyncio
async def test_get_principal_denies_suspended_user(web_repo: WebIdentityRepository, engine) -> None:
    user_id = await _verified_user(web_repo, "susp@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="S", slug=f"sus-u-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == user_id)
            .values(verification_status="SUSPENDED")
        )
    assert await web_repo.get_principal(token) is None


@pytest.mark.asyncio
async def test_get_principal_denies_disabled_org(web_repo: WebIdentityRepository, engine) -> None:
    user_id = await _verified_user(web_repo, "disorg@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="D", slug=f"dis-o-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(governance_status="DISABLED")
        )
    assert await web_repo.get_principal(token) is None


@pytest.mark.asyncio
async def test_get_principal_denies_inactive_membership(
    web_repo: WebIdentityRepository, engine
) -> None:
    user_id = await _verified_user(web_repo, "inactive@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="I", slug=f"inact-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(
                web_memberships.c.user_id == user_id,
                web_memberships.c.org_id == org_id,
            )
            .values(status="REVOKED")
        )
    assert await web_repo.get_principal(token) is None


@pytest.mark.asyncio
async def test_switch_organization_success_rotates_session(web_repo: WebIdentityRepository) -> None:
    user_id = await _verified_user(web_repo, "switch-ok@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="Switch Org", slug=f"sw-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=None)
    rotated = await web_repo.switch_organization(token, user_id, org_id)
    assert rotated is not None
    new_token, _csrf = rotated
    principal = await web_repo.get_principal(new_token)
    assert principal is not None
    assert principal.org_id == org_id


@pytest.mark.asyncio
async def test_revoke_invitation_returns_false_for_unknown(web_repo: WebIdentityRepository) -> None:
    owner = await _verified_user(web_repo, "rev-inv@example.com")
    org_id = await web_repo.attach_organization(
        owner, name="R", slug=f"rev-i-{uuid.uuid4().hex[:6]}"
    )
    assert await web_repo.revoke_invitation(str(uuid.uuid4()), org_id) is False


@pytest.mark.asyncio
async def test_accept_invitation_duplicate_membership_raises(
    web_repo: WebIdentityRepository,
) -> None:
    owner = await _verified_user(web_repo, "dup-inv@example.com")
    org_id = await web_repo.attach_organization(
        owner, name="Dup Inv", slug=f"dup-i-{uuid.uuid4().hex[:6]}"
    )
    member = await _verified_user(web_repo, "member@example.com")
    _, invite = await web_repo.create_invitation(
        org_id=org_id,
        email="member@example.com",
        role=Role.VIEWER,
        invited_by_user_id=owner,
    )
    await web_repo.accept_invitation(invite, member)
    _, invite2 = await web_repo.create_invitation(
        org_id=org_id,
        email="member@example.com",
        role=Role.ANALYST,
        invited_by_user_id=owner,
    )
    with pytest.raises(InvitationError, match="cannot be accepted"):
        await web_repo.accept_invitation(invite2, member)


@pytest.mark.asyncio
async def test_update_membership_role_revokes_org_sessions(web_repo: WebIdentityRepository) -> None:
    owner = await _verified_user(web_repo, "role-chg@example.com")
    org_id = await web_repo.attach_organization(
        owner, name="Role", slug=f"role-{uuid.uuid4().hex[:6]}"
    )
    member = await _verified_user(web_repo, "viewer@example.com")
    _, tok = await web_repo.create_invitation(
        org_id=org_id,
        email="viewer@example.com",
        role=Role.VIEWER,
        invited_by_user_id=owner,
    )
    await web_repo.accept_invitation(tok, member)
    session_token, _ = await web_repo.create_session(member, org_id=org_id)
    assert await web_repo.update_membership_role(org_id, member, Role.ANALYST) is True
    assert await web_repo.get_principal(session_token) is None


@pytest.mark.asyncio
async def test_remove_membership_owner_returns_false(web_repo: WebIdentityRepository) -> None:
    owner = await _verified_user(web_repo, "rm-own@example.com")
    org_id = await web_repo.attach_organization(
        owner, name="Own", slug=f"own-rm-{uuid.uuid4().hex[:6]}"
    )
    assert await web_repo.remove_membership(org_id, owner) is False


@pytest.mark.asyncio
async def test_list_organizations_filters_inactive_memberships(
    web_repo: WebIdentityRepository, engine
) -> None:
    user_id = await _verified_user(web_repo, "list-org@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="Listed", slug=f"lst-{uuid.uuid4().hex[:6]}"
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(
                web_memberships.c.user_id == user_id,
                web_memberships.c.org_id == org_id,
            )
            .values(status="REVOKED")
        )
    assert await web_repo.list_organizations(user_id) == []


# ── backup_defense.py ────────────────────────────────────────────────────────


def test_resolve_store_b_path_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    target = tmp_path / "lifecycle" / "store_b.db"
    monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(target))
    resolved = resolve_store_b_path(None)
    assert resolved == target.resolve()


def test_sqlite_lifecycle_noop_on_identical_record(tmp_path: Path) -> None:
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "lifecycle.db")
    record = _lifecycle_record()
    provider.record_state(record)
    provider.record_state(record)
    assert provider.get_state("org-1") is not None


def test_sqlite_lifecycle_state_rollback_rejected(tmp_path: Path) -> None:
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "lifecycle.db")
    provider.record_state(_lifecycle_record(state=LifecycleState.DELETION_IN_PROGRESS))
    with pytest.raises(LifecycleRollbackError, match="rollback rejected"):
        provider.record_state(_lifecycle_record(state=LifecycleState.ACTIVE))


def test_secure_create_store_b_rejects_symlink_path(tmp_path: Path) -> None:
    link = tmp_path / "store_b_link.db"
    real = tmp_path / "real_store.db"
    real.write_text("", encoding="utf-8")
    link.symlink_to(real)
    with pytest.raises(MissingLifecycleProviderError, match="symlink"):
        SqliteDurableLifecycleStateProvider(link)


# ── isolation/container_backend.py ───────────────────────────────────────────


def test_remove_containers_waits_for_stable_absence(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    seen: dict[str, int] = {"wp_iso_test": 0}

    def fake_run(cmd, **_kwargs):
        target = cmd[-1]
        seen[target] = seen.get(target, 0) + 1
        if seen[target] < 3:
            return subprocess.CompletedProcess(args=cmd, returncode=0)
        return subprocess.CompletedProcess(args=cmd, returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    t0 = time.monotonic()
    backend._remove_containers(["wp_iso_test"], stable_seconds=0.05, wait_seconds=2.0)
    assert time.monotonic() - t0 >= 0.05


@pytest.mark.asyncio
async def test_remove_containers_uninterruptible_runs_in_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    called = False

    def fake_remove(targets, *, stable_seconds, wait_seconds):
        nonlocal called
        called = True
        assert targets == ["c-batch16"]

    monkeypatch.setattr(backend, "_remove_containers", fake_remove)
    await backend._remove_containers_uninterruptible(
        ["c-batch16"], stable_seconds=0, wait_seconds=0.01
    )
    assert called is True


@pytest.mark.asyncio
async def test_execute_invalid_json_stdout_is_violation(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)

    class _Proc:
        returncode = 0

        async def communicate(self, input=None):
            return (b"not-json-output", b"")

        async def wait(self):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=_Proc()))
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", AsyncMock())
    from responsibleai.isolation.models import IsolatedExecutionRequest

    req = IsolatedExecutionRequest(
        action_id="act-json",
        organization_id="org-1",
        action_type="noop",
        arguments={},
    )
    outcome = await backend.execute(req)
    assert outcome.violation is not None


# ── enterprise/security/service.py ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_issue_session_gate_b_closed(
    engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("responsibleai.enterprise.security.service.PRODUCTION_GATE_B_OPEN", True)
    svc = await _svc(engine)
    user_id = await _user(engine)
    with pytest.raises(RuntimeError, match="must not open Gate B"):
        await svc.issue_session(
            user_id=user_id,
            methods=(AuthMethod.PASSWORD,),
            ip_label=None,
            user_agent=None,
        )


@pytest.mark.asyncio
async def test_security_remove_totp_blocked_when_last_strong_factor(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    org_id = await _org(engine, user_id)
    await svc.start_totp(user_id)
    async with engine.raw.connect() as conn:
        from sqlalchemy import select

        from responsibleai.db.engine import human_totp_factors

        secret = (
            await conn.execute(
                select(human_totp_factors.c.pending_secret_encrypted).where(
                    human_totp_factors.c.user_id == user_id
                )
            )
        ).scalar()
    import pyotp

    await svc.confirm_totp(user_id, pyotp.TOTP(secret).now())
    _, _, session = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSKEY_UV,),
        ip_label="203.0.113.2",
        user_agent="batch16",
        org_id=org_id,
    )
    grant = await svc.issue_step_up(session, SensitiveAction.DISABLE_MFA, org_id=org_id)
    strict_org = OrgAuthPolicy(phishing_resistant_required=True)
    with patch.object(svc, "_org_policy", AsyncMock(return_value=strict_org)):
        with pytest.raises(EnterpriseError) as exc:
            await svc.remove_totp(user_id=user_id, session=session, grant=grant)
    assert exc.value.code == SECURITY_DOWNGRADE_BLOCKED


@pytest.mark.asyncio
async def test_security_passkey_sign_count_zero_branch(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    private_key = generate_private_key(SECP256R1())
    begin = await svc.begin_webauthn(
        user_id=user_id, session_id=session.session_id, ceremony="register"
    )
    cdata, auth, _, _ = registration_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=b64url_decode(begin["challenge"]),
        private_key=private_key,
    )
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    rec = await svc.finish_passkey_registration(
        user_id=user_id,
        session=session,
        client_data_b64=cdata,
        authenticator_data_b64=auth,
        grant=grant,
    )
    auth_begin = await svc.begin_webauthn(
        user_id=user_id, session_id=None, ceremony="authenticate", org_id=None
    )
    cdata2, auth2, sig2 = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=b64url_decode(auth_begin["challenge"]),
        private_key=private_key,
        sign_count=0,
    )
    token, _csrf, _assurance = await svc.authenticate_passkey(
        client_data_b64=cdata2,
        authenticator_data_b64=auth2,
        signature_b64=sig2,
        credential_id=rec["credential_id"],
    )
    assert token


@pytest.mark.asyncio
async def test_security_break_glass_gate_b_closed(engine, monkeypatch: pytest.MonkeyPatch) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    org_id = await _org(engine, user_id)
    async with engine.raw.begin() as conn:
        from responsibleai.db.engine import org_security_policies

        await conn.execute(
            insert(org_security_policies).values(
                org_id=org_id,
                phishing_resistant_required=0,
                break_glass_user_id=user_id,
                privileged_roles_json='["OWNER"]',
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == user_id)
            .values(verification_status="IDENTITY_VERIFIED")
        )
    _, _, session = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSKEY_UV,),
        ip_label=None,
        user_agent=None,
        org_id=org_id,
    )
    monkeypatch.setattr("responsibleai.enterprise.security.service.PRODUCTION_GATE_B_OPEN", True)
    with pytest.raises(RuntimeError, match="must not open Gate B"):
        await svc.break_glass(user_id=user_id, org_id=org_id, session=session)


# ── enterprise/service.py ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iam_authorize_inactive_human_membership_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER, membership_status="REVOKED")
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(actor, Permission.ORG_VIEW, org_id=org_id)
    assert exc.value.code == MEMBERSHIP_REVOKED


@pytest.mark.asyncio
async def test_iam_authorize_suspended_org_allows_audit_read(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await OrgRepository(engine).set_governance_status(org_id, GovernanceStatus.SUSPENDED)
    actor = _actor(owner, org_id, Role.OWNER)
    await iam.authorize(actor, Permission.AUDIT_READ, org_id=org_id)


@pytest.mark.asyncio
async def test_iam_deny_if_db_fails_maps_sqlalchemy_error(
    engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)

    async def boom(_org_id: str):
        raise SQLAlchemyError("simulated outage")

    monkeypatch.setattr(iam, "_load_org", boom)
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(actor, Permission.ORG_VIEW, org_id=org_id)
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_production_gate_b_open_denies_authorize(
    engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("responsibleai.enterprise.service.PRODUCTION_GATE_B_OPEN", True)
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(_actor(owner, org_id, Role.OWNER), Permission.ORG_VIEW, org_id=org_id)
    assert exc.value.code == FORBIDDEN


# ── batch 16 extension: additional high-yield arcs ───────────────────────────


@pytest.mark.asyncio
async def test_mcp_call_tool_restore_quarantine_blocks_dispatch() -> None:
    reset_restore_readiness_gate(state=RestoreReadinessState.RESTORE_PENDING)
    _, payload = await mcp_server._call_tool("rai_health", {})
    assert payload["error"] == "restore_quarantine"
    assert payload["status"] == "RESTORE_PENDING"


@pytest.mark.asyncio
async def test_mcp_upgrade_required_meters_blocked_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    dispatch = AsyncMock()
    monkeypatch.setattr(mcp_server, "dispatch_tool", dispatch)
    reset_restore_readiness_gate(state=RestoreReadinessState.READY)
    usage = AsyncMock()
    ctx = OrgContext(key_id="k-up", role=Role.ANALYST, org_id="org-up", plan=Plan.FREE)
    tokens = _set_mcp_context(ctx, object(), usage)
    try:
        _, payload = await mcp_server._call_tool("rai_bias_evaluate", {})
        assert payload["error"] == "upgrade_required"
        usage.record_call.assert_awaited_once_with(
            "org-up", "rai_bias_evaluate", "FREE", allowed=False
        )
    finally:
        _reset_mcp_context(tokens)


@pytest.mark.asyncio
async def test_mcp_free_plan_hosted_access_meters_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "dispatch_tool", AsyncMock())
    reset_restore_readiness_gate(state=RestoreReadinessState.READY)
    usage = AsyncMock()
    ctx = OrgContext(key_id="k-free", role=Role.ANALYST, org_id="org-free", plan=Plan.FREE)
    tokens = _set_mcp_context(ctx, object(), usage)
    try:
        _, payload = await mcp_server._call_tool("rai_health", {})
        assert payload["error"] == "hosted_access_unavailable"
        usage.record_call.assert_awaited_once_with("org-free", "rai_health", "FREE", allowed=False)
    finally:
        _reset_mcp_context(tokens)


@pytest.mark.asyncio
async def test_lifespan_production_saml_rejects_memory_sqlite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "responsibleai.enterprise.preflight.assert_hosted_enterprise_boot_safe",
        lambda _settings: None,
    )
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "saml_idp_entity_id", "https://idp.example/metadata")
    monkeypatch.setattr(settings, "oidc_issuer", None)
    with pytest.raises(RuntimeError, match="in-memory SQLite"):
        async with LifespanManager(app, startup_timeout=15):
            pass


@pytest.mark.asyncio
async def test_get_principal_returns_none_when_org_row_missing(
    web_repo: WebIdentityRepository, engine
) -> None:
    user_id = await _verified_user(web_repo, "missing-org@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="Gone", slug=f"gone-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(organizations.delete().where(organizations.c.id == org_id))
    assert await web_repo.get_principal(token) is None


def test_resolve_store_b_path_relative_becomes_absolute(tmp_path: Path) -> None:
    rel = tmp_path / "nested" / "relative.db"
    resolved = resolve_store_b_path(rel)
    assert resolved.is_absolute()
    assert resolved.name == "relative.db"


@pytest.mark.asyncio
async def test_iam_update_settings_noop_returns_current_org(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    before = await iam._load_org(org_id)
    result = await iam.update_settings(
        _actor(owner, org_id, Role.OWNER),
        org_id,
        display_name=None,
        settings=None,
    )
    assert result["id"] == org_id
    assert result["name"] == before["name"]


@pytest.mark.asyncio
async def test_iam_transfer_ownership_requires_confirmation_phrase(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    member = await _user(engine, "member-transfer@example.com")
    org_id = await _org(engine, owner)
    with pytest.raises(EnterpriseError) as exc:
        await iam.transfer_ownership(
            _actor(owner, org_id, Role.OWNER),
            org_id,
            new_owner_user_id=member,
            confirmation="WRONG",
        )
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_transfer_ownership_rejects_non_member_target(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    stranger = await _user(engine, "stranger@example.com")
    org_id = await _org(engine, owner)
    with pytest.raises(EnterpriseError) as exc:
        await iam.transfer_ownership(
            _actor(owner, org_id, Role.OWNER),
            org_id,
            new_owner_user_id=stranger,
            confirmation="TRANSFER_OWNERSHIP",
        )
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_security_load_session_idle_timeout(engine) -> None:
    from responsibleai.db.web_identity_repository import _hash

    svc = await _svc(engine)
    user_id = await _user(engine)
    token, csrf, _ = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSWORD,),
        ip_label=None,
        user_agent=None,
    )
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_sessions)
            .where(web_sessions.c.token_hash == _hash(token))
            .values(inactivity_expires_at=past)
        )
    with pytest.raises(EnterpriseError) as exc:
        await svc.load_session(f"{token}.{csrf}")
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_security_issue_session_rotates_prior_token(engine) -> None:
    from responsibleai.db.web_identity_repository import _hash

    svc = await _svc(engine)
    user_id = await _user(engine)
    old_token, _, _ = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSWORD,),
        ip_label=None,
        user_agent=None,
    )
    new_token, _, _ = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSWORD,),
        ip_label=None,
        user_agent=None,
        rotate_from=old_token,
    )
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(web_sessions.c.revoked).where(web_sessions.c.token_hash == _hash(old_token))
            )
        ).fetchone()
    assert row is not None
    assert row.revoked == 1
    await svc.load_session(new_token)


@pytest.mark.asyncio
async def test_security_consume_recovery_code_replay_denied(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSKEY_UV,),
        ip_label="203.0.113.3",
        user_agent="batch16",
    )
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=None)
    codes = await svc.issue_recovery_codes(user_id, session=session, grant=grant)
    await svc.consume_recovery_code(user_id, codes[0])
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_code(user_id, codes[0])
    assert exc.value.code in {CHALLENGE_REPLAY, UNAUTHENTICATED, AUTHENTICATION_FAILED}


def test_remove_containers_exits_when_targets_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")

    def fake_run(cmd, **_kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    backend._remove_containers(["wp_iso_absent"], stable_seconds=0.1, wait_seconds=0.2)


@pytest.mark.asyncio
async def test_auth_failure_limiter_durable_unavailable_is_503() -> None:
    limiter = AuthFailureLimiter(max_failures=2, window_seconds=30.0)
    durable = AsyncMock()
    durable.current_count = AsyncMock(
        side_effect=EnterpriseError("IDENTITY_PROTECTION_UNAVAILABLE", "down", 503)
    )
    limiter.attach_durable(durable, require_durable=False)
    with pytest.raises(HTTPException) as exc:
        await limiter.is_blocked("203.0.113.9")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_auth_failure_limiter_record_failure_swallows_rate_limited() -> None:
    limiter = AuthFailureLimiter(max_failures=2, window_seconds=30.0)
    durable = AsyncMock()
    durable.check = AsyncMock(side_effect=EnterpriseError("RATE_LIMITED", "slow down", 429))
    limiter.attach_durable(durable, require_durable=False)
    await limiter.record_failure("203.0.113.10")


@pytest.mark.asyncio
async def test_auth_failure_limiter_require_durable_without_backend() -> None:
    limiter = AuthFailureLimiter(max_failures=2, window_seconds=30.0)
    limiter._require_durable = True
    with pytest.raises(HTTPException) as exc:
        await limiter.is_blocked("203.0.113.11")
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_resolve_saml_maps_developer_role(engine) -> None:
    repo = OrgRepository(engine)
    org = await repo.create_org("SAML Dev", f"saml-dev-{uuid.uuid4().hex[:8]}")
    claims = SAMLAssertionClaims(
        sub="saml-dev-user",
        org_id=org.id,
        roles=["DEVELOPER", "bogus"],
        email="dev@example.com",
    )
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(app_module, "_saml_config", MagicMock())
    monkeypatch.setattr(app_module, "_org_repo", repo)
    monkeypatch.setattr(app_module, "validate_session_token", lambda _cfg, _tok: claims)
    ctx = await _resolve_saml_context("wp_saml.valid.token")
    assert ctx is not None
    assert ctx.role == Role.DEVELOPER
    monkeypatch.undo()


@pytest.mark.asyncio
async def test_iam_accept_invitation_reactivates_revoked_membership(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    member = await _user(engine, "reactivate@example.com")
    org_id = await _org(engine, owner)
    _, invite_token = await iam.invite_member(
        _actor(owner, org_id, Role.OWNER),
        org_id,
        email="reactivate@example.com",
        role=Role.VIEWER,
    )
    await iam.accept_invitation(token=invite_token, user_id=member)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(
                web_memberships.c.org_id == org_id,
                web_memberships.c.user_id == member,
            )
            .values(status="REVOKED")
        )
    _, invite2 = await iam.invite_member(
        _actor(owner, org_id, Role.OWNER),
        org_id,
        email="reactivate@example.com",
        role=Role.ANALYST,
    )
    rejoined = await iam.accept_invitation(token=invite2, user_id=member)
    assert rejoined == org_id


@pytest.mark.asyncio
@respx.mock
async def test_paddle_portal_accepts_string_general_url() -> None:
    from httpx import Response

    service = PaddleBillingService(
        "pdl_sdbx_apikey_batch16",
        {Plan.PRO: "pri_test"},
        environment="sandbox",
    )
    respx.post("https://sandbox-api.paddle.com/customers/ctm_str/portal-sessions").mock(
        return_value=Response(
            200,
            json={"data": {"urls": {"general": "https://portal.example/overview"}}},
        )
    )
    url = await service.create_portal_session("ctm_str")
    assert url == "https://portal.example/overview"


def test_paddle_rejects_empty_api_key() -> None:
    with pytest.raises(PaddleNotConfiguredError):
        PaddleBillingService("   ", {Plan.PRO: "pri"}, environment="sandbox")


def test_paddle_resolve_price_id_missing_plan() -> None:
    service = PaddleBillingService(
        "pdl_sdbx_key_batch16",
        {},
        environment="sandbox",
    )
    with pytest.raises(PaddleBillingError, match="No Paddle price"):
        service.resolve_price_id(Plan.ENTERPRISE)


# ── enterprise/router.py web actor + tenant guard ────────────────────────────


def _enterprise_request(
    *,
    method: str = "GET",
    cookies: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
) -> Request:
    cookie_map = cookies or {}
    header_map = {k.lower(): v for k, v in (headers or {}).items()}
    req = MagicMock(spec=Request)
    req.method = method
    req.cookies = MagicMock()
    req.cookies.get = lambda key, default="": cookie_map.get(key, default)
    req.headers = MagicMock()
    req.headers.get = lambda key, default="": header_map.get(key.lower(), default)
    return req


@pytest.mark.asyncio
async def test_enterprise_web_actor_requires_session_cookie(engine, monkeypatch) -> None:
    from responsibleai.enterprise.router import _web_actor

    monkeypatch.setattr("responsibleai.enterprise.router.get_enterprise_engine", lambda: engine)
    with pytest.raises(EnterpriseError) as exc:
        await _web_actor(_enterprise_request())
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_enterprise_web_actor_post_requires_csrf(engine, monkeypatch) -> None:
    from responsibleai.enterprise.router import _web_actor

    monkeypatch.setattr("responsibleai.enterprise.router.get_enterprise_engine", lambda: engine)
    web = WebIdentityRepository(engine)
    user_id = await _verified_user(web, "csrf-router@example.com")
    org_id = await web.attach_organization(
        user_id, name="CSRF Org", slug=f"csrf-r-{uuid.uuid4().hex[:6]}"
    )
    token, csrf = await web.create_session(user_id, org_id=org_id)
    with pytest.raises(EnterpriseError) as exc:
        await _web_actor(
            _enterprise_request(
                method="POST",
                cookies={"wp_session": token, "wp_csrf": csrf},
                headers={},
            )
        )
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_enterprise_require_org_allows_cross_tenant_viewer(engine, monkeypatch) -> None:
    from responsibleai.enterprise.router import _require_org

    monkeypatch.setattr("responsibleai.enterprise.router.get_enterprise_engine", lambda: engine)
    web = WebIdentityRepository(engine)
    owner_a = await _verified_user(web, "owner-a@example.com")
    owner_b = await _verified_user(web, "owner-b@example.com")
    org_a = await web.attach_organization(
        owner_a, name="Org A", slug=f"orga-{uuid.uuid4().hex[:6]}"
    )
    org_b = await web.attach_organization(
        owner_b, name="Org B", slug=f"orgb-{uuid.uuid4().hex[:6]}"
    )
    _, invite = await web.create_invitation(
        org_id=org_b,
        email="owner-a@example.com",
        role=Role.VIEWER,
        invited_by_user_id=owner_b,
    )
    await web.accept_invitation(invite, owner_a)
    token, csrf = await web.create_session(owner_a, org_id=org_a)
    actor = await _require_org(
        _enterprise_request(
            cookies={"wp_session": token, "wp_csrf": csrf},
            headers={"X-WP-CSRF": csrf},
        ),
        org_b,
    )
    assert actor.org_id == org_b
    assert actor.role == Role.VIEWER


# ── net/egress.py extra validation branches ───────────────────────────────────


def test_egress_rejects_empty_url() -> None:
    from responsibleai.net.egress import InvalidURLError, normalize_and_validate_url

    with pytest.raises(InvalidURLError):
        normalize_and_validate_url("")


def test_egress_rejects_whitespace_in_url() -> None:
    from responsibleai.net.egress import InvalidURLError, normalize_and_validate_url

    with pytest.raises(InvalidURLError):
        normalize_and_validate_url("http://example.com/\n")


def test_egress_rejects_forbidden_localhost_name() -> None:
    from responsibleai.net.egress import ForbiddenDestinationError, normalize_and_validate_url

    with pytest.raises(ForbiddenDestinationError):
        normalize_and_validate_url("http://localhost/admin")


@pytest.mark.asyncio
async def test_step_up_missing_proof_issues_nonce(engine) -> None:
    from responsibleai.iam.enums import PrivilegeRiskTier
    from responsibleai.iam.errors import StepUpRequiredError
    from responsibleai.iam.step_up import StepUpVerifier

    verifier = StepUpVerifier(engine)
    with pytest.raises(StepUpRequiredError) as exc:
        await verifier.verify_and_consume_step_up(
            org_id="org-step",
            principal_id="principal-1",
            action="privileged.change",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
            proof=None,
        )
    assert exc.value.required_nonce


@pytest.mark.asyncio
async def test_step_up_invalid_auth_time_rejected(engine) -> None:
    from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
    from responsibleai.iam.errors import StepUpVerificationFailedError
    from responsibleai.iam.models import StepUpProof
    from responsibleai.iam.step_up import StepUpVerifier

    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id="org-step",
        principal_id="principal-1",
        action="privileged.change",
    )
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.OIDC_AUTH_TIME,
        auth_time="not-a-timestamp",
        token_or_code="valid-token-1234567890",
        claims={"auth_time": 1},
    )
    with pytest.raises(StepUpVerificationFailedError, match="auth_time"):
        await verifier.verify_and_consume_step_up(
            org_id="org-step",
            principal_id="principal-1",
            action="privileged.change",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_step_up_oidc_missing_auth_time_claim(engine) -> None:
    from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
    from responsibleai.iam.errors import StepUpVerificationFailedError
    from responsibleai.iam.models import StepUpProof
    from responsibleai.iam.step_up import StepUpVerifier

    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id="org-step",
        principal_id="principal-1",
        action="privileged.change",
    )
    now = datetime.now(UTC).isoformat()
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.OIDC_AUTH_TIME,
        auth_time=now,
        token_or_code="missing_auth_time",
        claims={},
    )
    with pytest.raises(StepUpVerificationFailedError, match="auth_time"):
        await verifier.verify_and_consume_step_up(
            org_id="org-step",
            principal_id="principal-1",
            action="privileged.change",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_enterprise_web_actor_requires_active_org_membership(engine, monkeypatch) -> None:
    from responsibleai.enterprise.router import _web_actor

    monkeypatch.setattr("responsibleai.enterprise.router.get_enterprise_engine", lambda: engine)
    web = WebIdentityRepository(engine)
    user_id = await _verified_user(web, "no-org@example.com")
    token, csrf = await web.create_session(user_id, org_id=None)
    with pytest.raises(EnterpriseError) as exc:
        await _web_actor(_enterprise_request(cookies={"wp_session": token, "wp_csrf": csrf}))
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_enterprise_web_actor_csrf_hash_mismatch(engine, monkeypatch) -> None:
    from responsibleai.enterprise.router import _web_actor

    monkeypatch.setattr("responsibleai.enterprise.router.get_enterprise_engine", lambda: engine)
    web = WebIdentityRepository(engine)
    user_id = await _verified_user(web, "csrf-bad@example.com")
    org_id = await web.attach_organization(
        user_id, name="Bad CSRF", slug=f"csrf-b-{uuid.uuid4().hex[:6]}"
    )
    token, csrf = await web.create_session(user_id, org_id=org_id)
    with pytest.raises(EnterpriseError) as exc:
        await _web_actor(
            _enterprise_request(
                method="POST",
                cookies={"wp_session": token, "wp_csrf": csrf},
                headers={"X-WP-CSRF": "wrong-csrf-value"},
            )
        )
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_enterprise_require_org_denies_non_member(engine, monkeypatch) -> None:
    from responsibleai.enterprise.router import _require_org

    monkeypatch.setattr("responsibleai.enterprise.router.get_enterprise_engine", lambda: engine)
    web = WebIdentityRepository(engine)
    owner = await _verified_user(web, "solo@example.com")
    other = await _verified_user(web, "other@example.com")
    org_a = await web.attach_organization(
        owner, name="Solo Org", slug=f"solo-{uuid.uuid4().hex[:6]}"
    )
    _org_b = await web.attach_organization(
        other, name="Other Org", slug=f"other-{uuid.uuid4().hex[:6]}"
    )
    token, csrf = await web.create_session(owner, org_id=org_a)
    with pytest.raises(EnterpriseError) as exc:
        await _require_org(
            _enterprise_request(
                cookies={"wp_session": token, "wp_csrf": csrf},
                headers={"X-WP-CSRF": csrf},
            ),
            _org_b,
        )
    assert exc.value.code == "WRONG_TENANT"


@pytest.mark.asyncio
async def test_step_up_recovery_ceremony_rejected(engine) -> None:
    from responsibleai.iam.enums import PrivilegeRiskTier
    from responsibleai.iam.errors import StepUpVerificationFailedError
    from responsibleai.iam.models import StepUpProof
    from responsibleai.iam.step_up import StepUpVerifier

    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id="org-step",
        principal_id="principal-1",
        action="privileged.change",
    )
    proof = StepUpProof(
        nonce=nonce,
        method="RECOVERY_CEREMONY",
        auth_time=datetime.now(UTC).isoformat(),
        token_or_code="recovery-token",
    )
    with pytest.raises(StepUpVerificationFailedError, match="Recovery ceremony"):
        await verifier.verify_and_consume_step_up(
            org_id="org-step",
            principal_id="principal-1",
            action="privileged.change",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_step_up_webauthn_unsupported_stub_rejected(engine) -> None:
    from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
    from responsibleai.iam.errors import StepUpVerificationFailedError
    from responsibleai.iam.models import StepUpProof
    from responsibleai.iam.step_up import StepUpVerifier

    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id="org-step",
        principal_id="principal-1",
        action="privileged.change",
    )
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.WEBAUTHN,
        auth_time=datetime.now(UTC).isoformat(),
        token_or_code="unsupported_stub",
    )
    with pytest.raises(StepUpVerificationFailedError, match="Unsupported WebAuthn"):
        await verifier.verify_and_consume_step_up(
            org_id="org-step",
            principal_id="principal-1",
            action="privileged.change",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_synthetic_counter_increment_and_ack_lost(engine) -> None:
    from responsibleai.governance.synthetic_counter import (
        SyntheticAcknowledgementLostError,
        bind_counter_engine,
        increment,
        snapshot,
    )

    bind_counter_engine(engine)
    state = await snapshot("org-synth")
    assert state["counter"] == 0
    updated = await increment("org-synth")
    assert updated["counter"] == 1
    with pytest.raises(SyntheticAcknowledgementLostError):
        await increment("org-synth", fail_after_effect=True)


@pytest.mark.asyncio
async def test_synthetic_counter_forbidden_in_production(engine, monkeypatch) -> None:
    from responsibleai.governance.synthetic_counter import bind_counter_engine, increment

    bind_counter_engine(engine)
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    with pytest.raises(RuntimeError, match="forbidden in production"):
        await increment("org-synth-prod")


@pytest.mark.asyncio
async def test_synthetic_counter_snapshot_requires_bound_engine() -> None:
    from responsibleai.governance.synthetic_counter import bind_counter_engine, snapshot

    bind_counter_engine(None)
    with pytest.raises(RuntimeError, match="not bound"):
        await snapshot("org-x")


@pytest.mark.asyncio
async def test_step_up_stale_auth_time_rejected(engine) -> None:
    from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
    from responsibleai.iam.errors import StepUpVerificationFailedError
    from responsibleai.iam.models import StepUpProof
    from responsibleai.iam.step_up import StepUpVerifier

    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id="org-step",
        principal_id="principal-1",
        action="privileged.change",
    )
    stale = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.OIDC_AUTH_TIME,
        auth_time=stale,
        token_or_code="valid-token-1234567890",
        claims={"auth_time": stale},
    )
    with pytest.raises(StepUpVerificationFailedError, match="freshness window"):
        await verifier.verify_and_consume_step_up(
            org_id="org-step",
            principal_id="principal-1",
            action="privileged.change",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_synthetic_counter_requires_organization_id(engine) -> None:
    from responsibleai.governance.synthetic_counter import bind_counter_engine, increment

    bind_counter_engine(engine)
    with pytest.raises(ValueError, match="organization_id"):
        await increment("")


@pytest.mark.asyncio
async def test_iam_change_role_admin_cannot_assign_admin(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    admin_user = await _user(engine, "admin-peer@example.com")
    viewer_user = await _user(engine, "viewer-peer@example.com")
    org_id = await _org(engine, owner)
    _, t1 = await iam.invite_member(
        _actor(owner, org_id, Role.OWNER), org_id, email="admin-peer@example.com", role=Role.ADMIN
    )
    await iam.accept_invitation(token=t1, user_id=admin_user)
    _, t2 = await iam.invite_member(
        _actor(owner, org_id, Role.OWNER), org_id, email="viewer-peer@example.com", role=Role.VIEWER
    )
    await iam.accept_invitation(token=t2, user_id=viewer_user)
    with pytest.raises(EnterpriseError) as exc:
        await iam.change_role(
            _actor(admin_user, org_id, Role.ADMIN),
            org_id,
            user_id=viewer_user,
            role=Role.ADMIN,
        )
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_authorize_api_key_missing_scope_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    repo = OrgRepository(engine)
    key_rec, _raw = await repo.create_key(org_id, "scoped", Role.ADMIN, scopes=("governance:read",))
    actor = Actor(
        actor_type="api_key",
        actor_id=key_rec.id,
        user_id=None,
        org_id=org_id,
        role=Role.ADMIN,
        membership_status="ACTIVE",
        scopes=frozenset({"governance:read"}),
    )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(
            actor,
            Permission.ORG_UPDATE_SETTINGS,
            org_id=org_id,
            required_scope="governance:write",
        )
    assert exc.value.code == INSUFFICIENT_SCOPE


@pytest.mark.asyncio
async def test_mcp_quota_exceeded_meters_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(mcp_server, "dispatch_tool", AsyncMock())
    reset_restore_readiness_gate(state=RestoreReadinessState.READY)
    usage = AsyncMock()
    usage.count_since = AsyncMock(return_value=999_999)
    ctx = OrgContext(key_id="k-quota", role=Role.ANALYST, org_id="org-quota", plan=Plan.PRO)
    tokens = _set_mcp_context(ctx, object(), usage)
    try:
        _, payload = await mcp_server._call_tool("rai_health", {})
        assert payload["error"] == "quota_exceeded"
        usage.record_call.assert_awaited()
    finally:
        _reset_mcp_context(tokens)


@pytest.mark.asyncio
@respx.mock
async def test_paddle_post_non_json_response_raises() -> None:
    from httpx import Response

    service = PaddleBillingService(
        "pdl_sdbx_apikey_batch16b",
        {Plan.PRO: "pri_test"},
        environment="sandbox",
    )
    respx.post("https://sandbox-api.paddle.com/transactions").mock(
        return_value=Response(200, text="not-json")
    )
    with pytest.raises(PaddleBillingError, match="non-JSON"):
        await service.create_checkout_session(
            PaddleCheckoutRequest(
                org_id="org-1",
                plan=Plan.PRO,
                success_url="https://example.com/success",
            )
        )


# ── single-branch completions (1–2 arcs each) ─────────────────────────────────


def test_rbac_equal_timestamp_rejects_canceled_to_active() -> None:
    from responsibleai.rbac.models import Plan, is_equal_timestamp_transition_allowed

    assert is_equal_timestamp_transition_allowed(Plan.PRO, "canceled", Plan.PRO, "active") is False


def test_rbac_get_plan_rank_invalid_string_returns_zero() -> None:
    from responsibleai.rbac.models import get_plan_rank

    assert get_plan_rank("NOT_A_REAL_PLAN") == 0


def test_enterprise_has_rbac_permission_none_role() -> None:
    from responsibleai.enterprise.roles import Permission, has_rbac_permission

    assert has_rbac_permission(None, Permission.ORG_VIEW) is False


def test_enterprise_role_privilege_unknown_role_returns_zero() -> None:
    from responsibleai.enterprise.roles import role_privilege

    assert role_privilege("NOT_A_ROLE") == 0


@pytest.mark.asyncio
async def test_synthetic_counter_increment_requires_bound_engine() -> None:
    from responsibleai.governance.synthetic_counter import bind_counter_engine, increment

    bind_counter_engine(None)
    with pytest.raises(RuntimeError, match="not bound"):
        await increment("org-unbound")


def test_rbac_equal_timestamp_rejects_plan_upgrade() -> None:
    from responsibleai.rbac.models import Plan, is_equal_timestamp_transition_allowed

    assert (
        is_equal_timestamp_transition_allowed(Plan.FREE, "active", Plan.ENTERPRISE, "active")
        is False
    )


def test_enterprise_runtime_configure_idempotent(engine) -> None:
    from responsibleai.enterprise.runtime import configure_enterprise, get_enterprise_engine

    configure_enterprise(engine)
    assert get_enterprise_engine() is engine


def test_tool_trust_tier_mapping_branches() -> None:
    from responsibleai.governance.tool_trust import ToolTrustTier, _tier_for_score

    assert _tier_for_score(0, has_been_scanned=True) == ToolTrustTier.BLOCKED
    assert _tier_for_score(90, has_been_scanned=True) == ToolTrustTier.TRUSTED
    assert _tier_for_score(90, has_been_scanned=False) == ToolTrustTier.PROVISIONAL
    assert _tier_for_score(55, has_been_scanned=False) == ToolTrustTier.PROVISIONAL
    assert _tier_for_score(15, has_been_scanned=True) == ToolTrustTier.UNTRUSTED


@pytest.mark.asyncio
async def test_mcp_governance_blocked_default_error_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "responsibleai.mcp.governance_integration.apply_governance",
        AsyncMock(
            return_value=GovernanceOutcome(proceed=False, arguments={}, blocked_response=None)
        ),
    )
    ctx = OrgContext(key_id="k-block", role=Role.ANALYST, org_id="org-block", plan=Plan.ENTERPRISE)
    tokens = _set_mcp_context(ctx, object())
    try:
        _, payload = await mcp_server._call_tool(
            "rai_health", {WHITEPACT_PURPOSE_ARGUMENT: "batch16-blocked-default"}
        )
        assert payload["error"] == "governance_blocked"
    finally:
        _reset_mcp_context(tokens)


def test_egress_rejects_unsupported_scheme() -> None:
    from responsibleai.net.egress import InvalidURLError, normalize_and_validate_url

    with pytest.raises(InvalidURLError, match="scheme"):
        normalize_and_validate_url("ftp://files.example.com/data")


def test_egress_rejects_missing_hostname() -> None:
    from responsibleai.net.egress import InvalidURLError, normalize_and_validate_url

    with pytest.raises(InvalidURLError, match="hostname"):
        normalize_and_validate_url("https:///no-host")


def test_is_address_allowed_rejects_metadata_ipv6() -> None:
    from responsibleai.net.egress import DestinationPolicy, is_address_allowed

    assert is_address_allowed("::ffff:169.254.169.254", DestinationPolicy.PUBLIC_ONLY) is False


# ── batch 16 closure: remaining high-yield branch arcs ─────────────────────


@pytest.mark.asyncio
async def test_mcp_upgrade_required_without_org_id_skips_metering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_server, "dispatch_tool", AsyncMock())
    reset_restore_readiness_gate(state=RestoreReadinessState.READY)
    usage = AsyncMock()
    ctx = OrgContext(key_id="k-no-org", role=Role.ANALYST, org_id=None, plan=Plan.FREE)
    tokens = _set_mcp_context(ctx, object(), usage)
    try:
        _, payload = await mcp_server._call_tool("rai_bias_evaluate", {})
        assert payload["error"] == "upgrade_required"
        usage.record_call.assert_not_awaited()
    finally:
        _reset_mcp_context(tokens)


@pytest.mark.asyncio
async def test_mcp_hosted_denied_without_usage_repo_skips_metering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mcp_server, "dispatch_tool", AsyncMock())
    reset_restore_readiness_gate(state=RestoreReadinessState.READY)
    ctx = OrgContext(key_id="k-free2", role=Role.ANALYST, org_id="org-free2", plan=Plan.FREE)
    tokens = _set_mcp_context(ctx, object(), usage_repo=None)
    try:
        _, payload = await mcp_server._call_tool("rai_health", {})
        assert payload["error"] == "hosted_access_unavailable"
    finally:
        _reset_mcp_context(tokens)


@pytest.fixture()
async def _batch16_mcp_oauth_http(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import Settings
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    monkeypatch.setenv("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "100")
    issuer = "https://batch16.test"
    oauth_settings = Settings(
        mcp_oauth_issuer=issuer,
        mcp_oauth_resource_uri=f"{issuer}/mcp",
        mcp_oauth_scopes=["whitepact:review", "offline_access"],
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: oauth_settings)
    built = _build_http_app()
    manager = LifespanManager(built)
    await manager.__aenter__()
    try:
        yield manager.app
    finally:
        await manager.__aexit__(None, None, None)
        await engine.close()


@pytest.mark.asyncio
async def test_mcp_oauth_register_rejects_oversized_raw_body(
    _batch16_mcp_oauth_http, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("WHITEPACT_MCP_TRUST_FORWARDED_HEADERS", "true")
    huge = b"x" * 20_000
    async with AsyncClient(
        transport=ASGITransport(app=_batch16_mcp_oauth_http),
        base_url="https://batch16.test",
    ) as client:
        r = await client.post(
            "/oauth/register",
            content=huge,
            headers={
                "content-type": "application/json",
                "x-forwarded-for": "203.0.113.44, 198.51.100.1",
            },
        )
    assert r.status_code == 413


@pytest.mark.asyncio
async def test_mcp_oauth_token_rejects_invalid_content_length(
    _batch16_mcp_oauth_http,
) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_batch16_mcp_oauth_http),
        base_url="https://batch16.test",
    ) as client:
        r = await client.post(
            "/oauth/token",
            content=b"grant_type=authorization_code",
            headers={
                "content-type": "application/x-www-form-urlencoded",
                "content-length": "not-a-number",
                "authorization": "Bearer super-secret-batch16-token",
            },
        )
    assert r.status_code in {400, 413}


@pytest.mark.asyncio
async def test_mcp_oauth_revoke_invalid_form_body_is_400(_batch16_mcp_oauth_http) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=_batch16_mcp_oauth_http),
        base_url="https://batch16.test",
    ) as client:
        r = await client.post(
            "/oauth/revoke",
            content=b"\xff\xfe",
            headers={"content-type": "application/x-www-form-urlencoded"},
        )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_mcp_openai_challenge_not_configured_returns_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module
    from responsibleai.dashboard.config import Settings
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    issuer = "https://batch16-nochallenge.test"
    oauth_settings = Settings(
        mcp_oauth_issuer=issuer,
        mcp_oauth_resource_uri=f"{issuer}/mcp",
        mcp_oauth_scopes=["whitepact:review", "offline_access"],
        openai_apps_challenge_token="",
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: oauth_settings)
    built = _build_http_app()
    async with AsyncClient(
        transport=ASGITransport(app=built),
        base_url=issuer,
    ) as client:
        r = await client.get("/.well-known/openai-apps-challenge")
    assert r.status_code == 404
    await engine.close()


@pytest.mark.asyncio
async def test_switch_organization_invalid_session_token_returns_none(
    web_repo: WebIdentityRepository,
) -> None:
    user_id = await _verified_user(web_repo, "bad-switch@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="Sw", slug=f"bad-sw-{uuid.uuid4().hex[:6]}"
    )
    assert await web_repo.switch_organization("not-a-real-token", user_id, org_id) is None


@pytest.mark.asyncio
async def test_switch_organization_unknown_membership_returns_none(
    web_repo: WebIdentityRepository,
) -> None:
    user_id = await _verified_user(web_repo, "nomem@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="One", slug=f"one-{uuid.uuid4().hex[:6]}"
    )
    other_org = await web_repo.attach_organization(
        user_id, name="Two", slug=f"two-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=org_id)
    async with web_repo._engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(
                web_memberships.c.user_id == user_id,
                web_memberships.c.org_id == other_org,
            )
            .values(status="REVOKED")
        )
    assert await web_repo.switch_organization(token, user_id, other_org) is None


@pytest.mark.asyncio
async def test_transfer_ownership_same_user_is_noop(web_repo: WebIdentityRepository) -> None:
    owner = await _verified_user(web_repo, "self-xfer@example.com")
    org_id = await web_repo.attach_organization(
        owner, name="Self", slug=f"self-xf-{uuid.uuid4().hex[:6]}"
    )
    assert (
        await web_repo.transfer_organization_ownership(
            org_id=org_id, current_owner_id=owner, new_owner_id=owner
        )
        is True
    )


@pytest.mark.asyncio
async def test_transfer_ownership_missing_target_member_returns_false(
    web_repo: WebIdentityRepository,
) -> None:
    owner = await _verified_user(web_repo, "xfer-miss@example.com")
    org_id = await web_repo.attach_organization(
        owner, name="Xfer", slug=f"xfer-m-{uuid.uuid4().hex[:6]}"
    )
    stranger = await _verified_user(web_repo, "stranger@example.com")
    assert (
        await web_repo.transfer_organization_ownership(
            org_id=org_id, current_owner_id=owner, new_owner_id=stranger
        )
        is False
    )


@pytest.mark.asyncio
async def test_remove_membership_success_revokes_sessions(web_repo: WebIdentityRepository) -> None:
    owner = await _verified_user(web_repo, "rm-ok@example.com")
    org_id = await web_repo.attach_organization(
        owner, name="Rm", slug=f"rm-ok-{uuid.uuid4().hex[:6]}"
    )
    member = await _verified_user(web_repo, "rm-member@example.com")
    _, invite = await web_repo.create_invitation(
        org_id=org_id,
        email="rm-member@example.com",
        role=Role.VIEWER,
        invited_by_user_id=owner,
    )
    await web_repo.accept_invitation(invite, member)
    session_token, _ = await web_repo.create_session(member, org_id=org_id)
    assert await web_repo.remove_membership(org_id, member) is True
    assert await web_repo.get_principal(session_token) is None


def test_resolve_store_b_rejects_forbidden_well_known_filename(tmp_path: Path) -> None:
    bad = tmp_path / "whitepact_store_b_lifecycle.db"
    with pytest.raises(MissingLifecycleProviderError, match="well-known"):
        resolve_store_b_path(bad)


def test_in_memory_lifecycle_provider_rejects_state_rollback() -> None:
    from responsibleai.data_governance.backup_defense import InMemoryLifecycleStateProvider

    provider = InMemoryLifecycleStateProvider()
    base = _lifecycle_record(state=LifecycleState.DELETION_IN_PROGRESS)
    provider.record_state(base)
    worse = _lifecycle_record(state=LifecycleState.ACTIVE)
    with pytest.raises(LifecycleRollbackError):
        provider.record_state(worse)


def test_in_memory_lifecycle_provider_unavailable_record_raises() -> None:
    from responsibleai.data_governance.backup_defense import (
        InMemoryLifecycleStateProvider,
        StoreBUnavailableError,
    )

    provider = InMemoryLifecycleStateProvider()
    provider.set_available(False)
    with pytest.raises(StoreBUnavailableError):
        provider.record_state(_lifecycle_record())


def test_remove_containers_stable_window_elapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    clock = {"now": 0.0}

    def fake_monotonic():
        clock["now"] += 0.6
        return clock["now"]

    def fake_run(cmd, **_kwargs):
        return subprocess.CompletedProcess(args=cmd, returncode=1)

    monkeypatch.setattr(time, "monotonic", fake_monotonic)
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    backend._remove_containers(["wp_iso_stable"], stable_seconds=1.0, wait_seconds=5.0)


@pytest.mark.asyncio
async def test_container_execute_reads_cidfile_for_cleanup(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.isolation.models import IsolatedExecutionRequest

    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)
    removed: list[list[str]] = []

    async def capture_remove(targets, *, stable_seconds, wait_seconds):
        removed.append(list(targets))

    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", capture_remove)

    class _Proc:
        returncode = 0

        async def communicate(self, input=None):
            return (b'{"status":"success","result":{}}', b"")

        async def wait(self):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=_Proc()))

    from responsibleai.isolation.container_backend import EphemeralWorkspace

    real_enter = EphemeralWorkspace.__enter__

    def _enter_with_cid(self):
        workspace = real_enter(self)
        (workspace.path / ".container.cid").write_text(
            "abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx1234yzab",
            encoding="utf-8",
        )
        return workspace

    monkeypatch.setattr(EphemeralWorkspace, "__enter__", _enter_with_cid)
    req = IsolatedExecutionRequest(
        action_id="act-cid",
        organization_id="org-cid",
        action_type="noop",
        arguments={},
    )
    outcome = await backend.execute(req)
    assert outcome.violation is None
    assert removed and "abcd1234efgh5678ijkl9012mnop3456qrst7890uvwx1234yzab" in removed[0]
