# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 13 branch-coverage: remaining ``dashboard/app.py`` and
``enterprise/security/service.py`` gaps per BRANCH_COVERAGE_GAP_REPORT.md."""

from __future__ import annotations

import os
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pyotp
import pytest
from asgi_lifespan import LifespanManager
from cryptography.hazmat.primitives.asymmetric.ec import SECP256R1, generate_private_key
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy import insert, select, update
from starlette.requests import Request

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

import responsibleai.dashboard.app as app_module
from responsibleai.auth.oidc import JWTClaims
from responsibleai.auth.saml import SAMLAssertionClaims
from responsibleai.dashboard.app import (
    _enforce_legacy_static_compat,
    _enforce_machine_scope,
    _get_rate_limit_key,
    _resolve_oidc_context,
    _resolve_saml_context,
    _resolve_transport_identity,
    app,
    limiter,
    settings,
)
from responsibleai.dashboard.signup_guard import SignupRateWindow
from responsibleai.db.engine import (
    create_engine,
    human_totp_factors,
    org_security_policies,
    provider_identities,
    web_users,
)
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    AUTHENTICATION_ASSURANCE_TOO_LOW,
    CHALLENGE_REPLAY,
    EnterpriseError,
)
from responsibleai.enterprise.preflight import HostedEnterpriseSecurityError
from responsibleai.enterprise.security.oidc import OIDCTokenValidator, VerifiedIDToken
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.service import (
    GOOGLE_PROVIDER,
    IdentitySecurityService,
    _iso,
    _unverified_iss,
)
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.enterprise.service import EnterpriseIAM
from responsibleai.rbac.models import OrgContext, Role
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


@pytest.fixture()
async def web_client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "auto_migrate", False)
    monkeypatch.setattr(settings, "auth_enabled", False)
    monkeypatch.setattr(settings, "web_auth_dev_tokens", True)
    monkeypatch.setattr(settings, "web_session_secure", False)
    monkeypatch.setattr(settings, "web_verification_delivery_url", None)
    monkeypatch.setattr(
        app_module, "_signup_window", SignupRateWindow(max_per_window=30, window_seconds=3600.0)
    )
    monkeypatch.setattr(limiter, "enabled", False)

    async with LifespanManager(app, startup_timeout=15) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as ac:
            yield ac


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


def _http_message(response) -> str:
    body = response.json()
    message = body.get("message", body.get("detail", ""))
    if isinstance(message, dict):
        return str(message.get("message", message))
    return message if isinstance(message, str) else str(message)


def _scope_request(method: str, path: str) -> Request:
    return Request({"type": "http", "method": method, "path": path, "headers": []})


async def _user(engine, email: str = "human@example.com") -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


async def _svc(engine, **kwargs) -> IdentitySecurityService:
    return IdentitySecurityService(engine, rp_id="localhost", origin="http://localhost", **kwargs)


async def _org(engine, owner_id: str) -> str:
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner_id,
        name="Batch13 Org",
        slug=f"b13-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    return org["id"]


async def _break_glass_policy(engine, org_id: str, user_id: str) -> None:
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(org_security_policies).values(
                org_id=org_id,
                phishing_resistant_required=0,
                privileged_roles_json='["OWNER"]',
                sso_enforcement="SSO_OPTIONAL",
                dual_control_json="[]",
                break_glass_user_id=user_id,
                updated_at=now,
            )
        )
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == user_id)
            .values(verification_status="IDENTITY_VERIFIED")
        )


# ── dashboard/app.py helpers ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path", "scopes", "required_fragment"),
    [
        ("GET", "/api/governance/evidence", frozenset({"governance:read"}), "evidence:read"),
        (
            "POST",
            "/api/governance/policy/rules",
            frozenset({"governance:read"}),
            "governance:write",
        ),
        ("GET", "/api/governance/policy", frozenset({"agents:write"}), "governance:read"),
        ("POST", "/api/agents/register", frozenset({"agents:read"}), "agents:write"),
        ("GET", "/api/agents/list", frozenset({"agents:write"}), "agents:read"),
    ],
)
def test_machine_scope_missing_scope_raises(
    method: str, path: str, scopes: frozenset[str], required_fragment: str
) -> None:
    ctx = OrgContext(key_id="k1", role=Role.ADMIN, org_id="org-1", scopes=scopes)
    with pytest.raises(HTTPException) as exc:
        _enforce_machine_scope(_scope_request(method, path), ctx)
    assert exc.value.status_code == 403
    assert required_fragment in str(exc.value.detail)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("POST", "/api/enterprise/audit"),
        ("GET", "/api/web/session"),
        ("GET", "/api/governance/policy"),
        ("POST", "/api/orgs/org-1/keys"),
        ("POST", "/api/governance/tools/call/execute"),
        ("POST", "/api/governance/upstream/dispatch"),
    ],
)
def test_legacy_static_compat_blocks_sensitive_paths(method: str, path: str) -> None:
    with pytest.raises(HTTPException) as exc:
        _enforce_legacy_static_compat(_scope_request(method, path))
    assert exc.value.status_code == 403
    assert "LEGACY_CREDENTIAL_FORBIDDEN" in str(exc.value.detail)


class TestIdentityResolutionBatch13:
    async def test_resolve_oidc_maps_matching_admin_role(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("OIDC Org", f"oidc13-{uuid.uuid4().hex[:8]}")
        provider = MagicMock()
        provider.validate_token = AsyncMock(
            return_value=JWTClaims(sub="user-oidc", org_id=org.id, roles=["bogus", "ADMIN"])
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_oidc_provider", provider)
        monkeypatch.setattr(app_module, "_org_repo", repo)
        ctx = await _resolve_oidc_context("eyJhbGciOiJIUzI1NiJ9.e30.sig")
        assert ctx is not None
        assert ctx.role == Role.ADMIN
        assert ctx.org_name == org.name
        monkeypatch.undo()

    async def test_resolve_oidc_unknown_role_defaults_viewer(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("OIDC Viewer", f"oidcv-{uuid.uuid4().hex[:8]}")
        provider = MagicMock()
        provider.validate_token = AsyncMock(
            return_value=JWTClaims(sub="user-oidc", org_id=org.id, roles=["not-a-real-role"])
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_oidc_provider", provider)
        monkeypatch.setattr(app_module, "_org_repo", repo)
        ctx = await _resolve_oidc_context("eyJhbGciOiJIUzI1NiJ9.e30.sig")
        assert ctx is not None
        assert ctx.role == Role.VIEWER
        monkeypatch.undo()

    async def test_resolve_saml_maps_session_to_org_context(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("SAML Org", f"saml13-{uuid.uuid4().hex[:8]}")
        claims = SAMLAssertionClaims(
            sub="saml-user",
            org_id=org.id,
            roles=["ANALYST"],
            email="saml@example.com",
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_saml_config", MagicMock())
        monkeypatch.setattr(app_module, "_org_repo", repo)
        monkeypatch.setattr(app_module, "validate_session_token", lambda _cfg, _tok: claims)
        ctx = await _resolve_saml_context("wp_saml.valid.token")
        assert ctx is not None
        assert ctx.role == Role.ANALYST
        assert ctx.authentication_method == "saml"
        monkeypatch.undo()

    async def test_resolve_transport_rejects_legacy_key_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "api_keys", ["legacy-prod-key"])
        monkeypatch.setattr(settings, "environment", "production")
        with pytest.raises(HostedEnterpriseSecurityError):
            await _resolve_transport_identity("legacy-prod-key")

    async def test_rate_limit_key_without_client_uses_starlette_default(self) -> None:
        req = Request({"type": "http", "method": "GET", "path": "/api/health", "headers": []})
        key = _get_rate_limit_key(req)
        assert key is not None


class TestDashboardDenyPathsBatch13:
    async def test_viewer_cannot_list_org_api_keys(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Keys List Viewer",
            slug=f"klv-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get(f"/api/orgs/{org_id}/keys", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_start_billing_checkout(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Checkout Viewer",
            slug=f"chk-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/billing/checkout",
            json={"plan": "PRO", "org_email": "pay@example.com"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_analyst_cannot_create_org(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Create Org Analyst",
            slug=f"corg-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/orgs",
            json={"name": "Child", "slug": f"child-{uuid.uuid4().hex[:8]}"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_analyst_cannot_revoke_org_api_key(self, auth_client: AsyncClient) -> None:
        org_id, key_id, raw = await seed_org_with_key(
            name="Revoke Key Analyst",
            slug=f"revk-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.delete(f"/api/orgs/{org_id}/keys/{key_id}", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_run_eval_benchmark(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Benchmark Viewer",
            slug=f"bench-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/eval/benchmark",
            json={"suite": "safety", "model": "gpt-4", "provider": "openai"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_scan_dataset(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Dataset Viewer",
            slug=f"data-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/eval/dataset-scan",
            json={"dataset_uri": "s3://bucket/data.jsonl"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_run_leaderboard(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Leaderboard Viewer",
            slug=f"lb-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/leaderboard/run",
            json={"model": "gpt-4", "provider": "openai"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_analyst_cannot_read_billing_mcp_usage_top(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="MCP Top Analyst",
            slug=f"mcpt-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get("/api/billing/usage/mcp/top", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_query_audit_entries(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit Entries Viewer",
            slug=f"aud-e-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/audit", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_list_webhooks(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Webhook Viewer",
            slug=f"wh-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/webhooks", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_scoped_agents_write_cannot_get_governance_policy(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Agents Scope",
            slug=f"ag-sc-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped = await app_module._org_repo.create_key(
            org_id,
            "agents-write",
            Role.ADMIN,
            scopes=("agents:write",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.get("/api/governance/policy", headers=_bearer(scoped))
        assert r.status_code == 403
        assert "governance:read" in _http_message(r)

    async def test_sso_required_lists_configured_oidc_provider(
        self, auth_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "oidc_issuer", "https://idp.example.com")
        monkeypatch.setattr(settings, "oidc_client_id", "dashboard-client")
        app_module._oidc_provider = None
        org_id, _kid, raw = await seed_org_with_key(
            name="SSO List Co",
            slug=f"sso-list-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        await app_module._org_repo.set_sso_required(org_id, True)
        r = await auth_client.get(f"/api/orgs/{org_id}", headers=_bearer(raw))
        assert r.status_code == 403
        assert "/api/auth/login" in _http_message(r)

    async def test_ready_endpoint_reports_status(self, client: AsyncClient) -> None:
        r = await client.get("/readyz")
        assert r.status_code in (200, 503)

    async def test_branding_endpoint_public(self, client: AsyncClient) -> None:
        r = await client.get("/api/branding")
        assert r.status_code == 200

    async def test_drift_check_unknown_model_returns_payload(self, client: AsyncClient) -> None:
        r = await client.get("/api/drift/unknown-model/openai")
        assert r.status_code == 200


class TestDashboardWebConsoleBatch13:
    async def test_web_logout_all_requires_csrf(self, web_client: AsyncClient) -> None:
        r = await web_client.post("/api/web/auth/logout-all")
        assert r.status_code in (401, 403)

    async def test_web_api_keys_list_requires_session(self, web_client: AsyncClient) -> None:
        r = await web_client.get("/api/web/api-keys")
        assert r.status_code == 401

    async def test_web_billing_checkout_requires_session(self, web_client: AsyncClient) -> None:
        r = await web_client.post("/api/web/billing/checkout", json={"plan": "PRO"})
        assert r.status_code == 401

    async def test_web_members_list_requires_session(self, web_client: AsyncClient) -> None:
        r = await web_client.get("/api/web/members")
        assert r.status_code == 401


# ── enterprise/security/service.py ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_start_totp_existing_active_user_keeps_status(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    async with engine.raw.connect() as conn:
        secret = (
            await conn.execute(
                select(human_totp_factors.c.pending_secret_encrypted).where(
                    human_totp_factors.c.user_id == user_id
                )
            )
        ).scalar()
    await svc.confirm_totp(user_id, pyotp.TOTP(secret).now())
    again = await svc.start_totp(user_id)
    assert again["status"] == "PENDING"
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(human_totp_factors).where(human_totp_factors.c.user_id == user_id)
            )
        ).fetchone()
    assert row.status == "ACTIVE"
    assert row.pending_secret_encrypted is not None


@pytest.mark.asyncio
async def test_security_verify_totp_success_updates_timestep(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    async with engine.raw.connect() as conn:
        secret = (
            await conn.execute(
                select(human_totp_factors.c.pending_secret_encrypted).where(
                    human_totp_factors.c.user_id == user_id
                )
            )
        ).scalar()
    await svc.confirm_totp(user_id, pyotp.TOTP(secret).now())
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(human_totp_factors)
            .where(human_totp_factors.c.user_id == user_id)
            .values(last_timestep=None)
        )
    code = pyotp.TOTP(secret).now()
    await svc.verify_totp(user_id, code)
    with pytest.raises(EnterpriseError) as replay:
        await svc.verify_totp(user_id, code)
    assert replay.value.code == CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_security_authenticate_password_success_with_membership(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    result = await svc.authenticate_password(
        "human@example.com", "correct-horse-battery-staple-9", org_id=org_id
    )
    assert result is not None
    token, _csrf, assurance = result
    loaded = await svc.load_session(token)
    assert loaded[2].org_id == org_id


@pytest.mark.asyncio
async def test_security_google_login_personal_without_org(engine) -> None:
    svc = await _svc(engine, google_client_id="google-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="google-sub-personal",
        audience="google-client",
        email="personal@gmail.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="nonce-1",
        expires_at=int(time.time()) + 120,
        raw={},
    )
    with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
        out = await svc.google_login(id_token="header.payload.sig", nonce="nonce-1")
    assert out["status"] == "UNLINKED_PROVIDER"


@pytest.mark.asyncio
async def test_security_microsoft_login_organizational_without_org(engine) -> None:
    svc = await _svc(engine, microsoft_client_id="ms-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer="https://login.microsoftonline.com/tenant/v2.0",
        subject="ms-sub",
        audience="ms-client",
        email="user@contoso.com",
        hosted_domain=None,
        tenant_id="contoso-tenant",
        nonce="nonce-2",
        expires_at=int(time.time()) + 120,
        raw={},
    )
    with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
        out = await svc.microsoft_login(id_token="a.b.c", nonce="nonce-2")
    assert out["status"] == "UNLINKED_PROVIDER"
    assert out["account_kind"] == "ORGANIZATIONAL"


@pytest.mark.asyncio
async def test_security_linked_provider_login_without_org_id(engine) -> None:
    user_id = await _user(engine, "linked13@example.com")
    svc = await _svc(engine)
    now = _iso()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(provider_identities).values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                provider=GOOGLE_PROVIDER,
                subject="google-sub-linked13",
                tenant_id="",
                hosted_domain=None,
                account_kind="PERSONAL",
                email_at_link="linked13@example.com",
                status="ACTIVE",
                created_at=now,
            )
        )
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject="google-sub-linked13",
        audience="c",
        email="linked13@example.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    out = await svc._complete_provider_login(
        provider=GOOGLE_PROVIDER,
        claims=claims,
        account_kind="PERSONAL",
        org_id=None,
        method=AuthMethod.GOOGLE_OIDC,
    )
    assert out["status"] == "AUTHENTICATED"
    assert "session_token" in out


@pytest.mark.asyncio
async def test_security_begin_hosted_oauth_google_configured(engine) -> None:
    svc = await _svc(
        engine,
        google_client_id="g-id",
        google_client_secret="g-secret",
        hosted_redirect_uri="https://app.example/cb",
    )
    svc.oauth.begin = AsyncMock(return_value={"authorization_url": "https://auth.example"})
    out = await svc.begin_hosted_oauth(provider="google", redirect_uri=None)
    assert "authorization_url" in out
    svc.oauth.begin.assert_awaited_once()


@pytest.mark.asyncio
async def test_security_issue_recovery_codes_with_step_up(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=None)
    codes = await svc.issue_recovery_codes(user_id, session=session, grant=grant)
    assert len(codes) >= 8
    await svc.consume_recovery_code(user_id, codes[0])


@pytest.mark.asyncio
async def test_security_break_glass_success(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await _break_glass_policy(engine, org_id, owner)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org_id,
        ip_label="203.0.113.1",
        user_agent="test",
    )
    out = await svc.break_glass(org_id=org_id, user_id=owner, session=session)
    assert out["status"] == "BREAK_GLASS_ACTIVE"


@pytest.mark.asyncio
async def test_security_domain_challenge_dns_success(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    dns_records: list[str] = []
    svc = await _svc(engine, txt_lookup=lambda _domain: dns_records)
    _, _, session = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org_id,
        ip_label=None,
        user_agent=None,
    )
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id)
    token = await svc.start_domain_challenge(
        org_id=org_id,
        domain="example.com",
        method="DNS_TXT",
        session=session,
        grant=grant,
    )
    dns_records.append(f"whitepact-verify={token}")
    await svc.complete_domain_challenge(
        org_id=org_id, domain="example.com", method="DNS_TXT", token=token
    )


@pytest.mark.asyncio
async def test_security_evaluate_role_change_allows_member_role(engine) -> None:
    user_id = await _user(engine)
    org_id = await _org(engine, user_id)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSWORD,),
        org_id=org_id,
        ip_label=None,
        user_agent=None,
    )
    await svc.evaluate_role_change(session, new_role="MEMBER", org_id=org_id)


@pytest.mark.asyncio
async def test_security_unverified_iss_accepts_microsoft_token() -> None:
    import base64
    import json

    payload = (
        base64.urlsafe_b64encode(
            json.dumps({"iss": "https://login.microsoftonline.com/tenant/v2.0"}).encode()
        )
        .rstrip(b"=")
        .decode()
    )
    token = f"eyJhbGciOiJub25lIn0.{payload}.sig"
    assert "login.microsoftonline.com" in _unverified_iss(token)


@pytest.mark.asyncio
async def test_security_passkey_register_and_authenticate_round_trip(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    begin = await svc.begin_webauthn(
        user_id=user_id, session_id=session.session_id, ceremony="register"
    )
    challenge = b64url_decode(begin["challenge"])
    key = generate_private_key(SECP256R1())
    cdata, adata, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    rec = await svc.finish_passkey_registration(
        user_id=user_id,
        session=session,
        client_data_b64=cdata,
        authenticator_data_b64=adata,
        grant=grant,
    )
    auth_begin = await svc.begin_webauthn(
        user_id=user_id, session_id=None, ceremony="authenticate", org_id=None
    )
    auth_challenge = b64url_decode(auth_begin["challenge"])
    acdata, aadata, sig = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=auth_challenge,
        private_key=key,
        sign_count=1,
    )
    token, _csrf, _assurance = await svc.authenticate_passkey(
        client_data_b64=acdata,
        authenticator_data_b64=aadata,
        signature_b64=sig,
        credential_id=rec["credential_id"],
    )
    await svc.load_session(token)


@pytest.mark.asyncio
async def test_security_remove_passkey_when_multiple_exist(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )

    async def _add_passkey(label: str) -> str:
        begin = await svc.begin_webauthn(
            user_id=user_id, session_id=session.session_id, ceremony="register"
        )
        challenge = b64url_decode(begin["challenge"])
        key = generate_private_key(SECP256R1())
        cdata, adata, _, _ = registration_blob(
            rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
        )
        grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
        rec = await svc.finish_passkey_registration(
            user_id=user_id,
            session=session,
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            display_name=label,
            grant=grant,
        )
        return rec["id"]

    first = await _add_passkey("primary")
    second = await _add_passkey("backup")
    grant_rm = await svc.issue_step_up(session, SensitiveAction.REMOVE_PASSKEY, org_id=None)
    await svc.remove_passkey(
        user_id=user_id, credential_row_id=second, session=session, grant=grant_rm
    )
    remaining = await svc.list_passkeys(user_id)
    assert len(remaining) == 1
    assert remaining[0]["id"] == first


@pytest.mark.asyncio
async def test_security_consume_step_up_assurance_too_low(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_step_up(session, SensitiveAction.ADD_PASSKEY, grant)
    assert exc.value.code == AUTHENTICATION_ASSURANCE_TOO_LOW


@pytest.mark.asyncio
async def test_security_request_recovery_non_privileged_user(engine) -> None:
    await _user(engine)
    svc = await _svc(engine)
    await svc.request_recovery("human@example.com")
    assert getattr(svc, "last_recovery_token_for_tests", None)


@pytest.mark.asyncio
async def test_security_consume_recovery_token_non_privileged(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.request_recovery("human@example.com")
    token = svc.last_recovery_token_for_tests
    assert token
    recovered = await svc.consume_recovery_token(token)
    assert recovered == user_id


@pytest.mark.asyncio
async def test_security_link_provider_success(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    grant = await svc.issue_step_up(session, SensitiveAction.LINK_GOOGLE, org_id=None)
    claims = VerifiedIDToken(
        issuer="https://accounts.google.com",
        subject=f"google-{uuid.uuid4().hex[:8]}",
        audience="client",
        email="human@example.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n",
        expires_at=int(time.time()) + 60,
        raw={},
    )
    await svc.link_provider(
        session=session,
        provider="GOOGLE",
        claims=claims,
        grant=grant,
        account_kind="PERSONAL",
    )


@pytest.mark.asyncio
async def test_security_begin_webauthn_authenticate_without_user(engine) -> None:
    svc = await _svc(engine)
    out = await svc.begin_webauthn(
        user_id=None, session_id=None, ceremony="authenticate", org_id=None
    )
    assert "challenge" in out
