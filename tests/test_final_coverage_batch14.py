# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 14 branch-coverage: remaining ``dashboard/app.py`` and
``enterprise/security/service.py`` deny paths per BRANCH_COVERAGE_GAP_REPORT.md."""

from __future__ import annotations

import os
import time
import uuid
from unittest.mock import AsyncMock, patch

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
    web_users,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    AUTHENTICATION_FAILED,
    BREAK_GLASS_DENIED,
    CHALLENGE_REPLAY,
    COMPANY_VERIFICATION_REQUIRED,
    MFA_REQUIRED,
    PASSKEY_REQUIRED,
    PROVIDER_TOKEN_INVALID,
    RECOVERY_REVIEW_REQUIRED,
    STEP_UP_REQUIRED,
    UNAUTHENTICATED,
    WEBAUTHN_INVALID,
    EnterpriseError,
)
from responsibleai.enterprise.security.oidc import OIDCTokenValidator, VerifiedIDToken
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.service import (
    IdentitySecurityService,
    _iso,
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
        name="Batch14 Org",
        slug=f"b14-{uuid.uuid4().hex[:8]}",
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


async def _passkey_session(svc: IdentitySecurityService, user_id: str, org_id: str | None = None):
    return await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSKEY_UV,),
        org_id=org_id,
        ip_label="203.0.113.4",
        user_agent="batch14",
    )


async def _register_passkey(svc: IdentitySecurityService, user_id: str, session) -> tuple:
    begin = await svc.begin_webauthn(
        user_id=user_id, session_id=session.session_id, ceremony="register"
    )
    challenge = b64url_decode(begin["challenge"])
    key = generate_private_key(SECP256R1())
    cdata, adata, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=session.org_id)
    rec = await svc.finish_passkey_registration(
        user_id=user_id,
        session=session,
        client_data_b64=cdata,
        authenticator_data_b64=adata,
        grant=grant,
    )
    return rec, key


# ── dashboard/app.py helpers ─────────────────────────────────────────────────


def test_rate_limit_key_hashes_bearer_token() -> None:
    req = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/health",
            "headers": [(b"authorization", b"Bearer org-secret-key-value")],
        }
    )
    key = _get_rate_limit_key(req)
    assert key is not None
    assert key.startswith("key:")


def test_rate_limit_key_empty_bearer_falls_back_to_ip() -> None:
    req = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/health",
            "headers": [(b"authorization", b"Bearer   ")],
            "client": ("203.0.113.5", 1234),
        }
    )
    key = _get_rate_limit_key(req)
    assert key is not None
    assert not key.startswith("key:")


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/enterprise/audit"),
        ("POST", "/api/web/onboarding"),
        ("POST", "/api/orgs/org-1/service-account/tokens"),
        ("GET", "/api/governance/approvals"),
        ("POST", "/api/governance/upstream/dispatch"),
        ("POST", "/api/orgs/org-1/keys"),
        ("PATCH", "/api/governance/workflow-rules/r1"),
        ("POST", "/api/governance/tools/call/execute"),
    ],
)
def test_legacy_static_compat_extra_blocked_paths(method: str, path: str) -> None:
    with pytest.raises(HTTPException) as exc:
        _enforce_legacy_static_compat(_scope_request(method, path))
    assert exc.value.status_code == 403
    assert "LEGACY_CREDENTIAL_FORBIDDEN" in str(exc.value.detail)


@pytest.mark.parametrize(
    ("method", "path", "scopes", "fragment"),
    [
        ("POST", "/api/governance/delegations", frozenset({"governance:read"}), "governance:write"),
        (
            "GET",
            "/api/governance/intent-contracts",
            frozenset({"governance:write"}),
            "governance:read",
        ),
        (
            "POST",
            "/api/governance/authority-passports",
            frozenset({"governance:read"}),
            "governance:write",
        ),
        ("GET", "/api/governance/evidence/verify", frozenset({"agents:write"}), "evidence:read"),
    ],
)
def test_machine_scope_batch14_missing_scope(
    method: str, path: str, scopes: frozenset[str], fragment: str
) -> None:
    ctx = OrgContext(key_id="k-b14", role=Role.ADMIN, org_id="org-b14", scopes=scopes)
    with pytest.raises(HTTPException) as exc:
        _enforce_machine_scope(_scope_request(method, path), ctx)
    assert exc.value.status_code == 403
    assert fragment in str(exc.value.detail)


class TestIdentityResolutionBatch14:
    async def test_resolve_oidc_returns_none_without_provider(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_oidc_provider", None)
        assert await _resolve_oidc_context("eyJhbGciOiJIUzI1NiJ9.e30.sig") is None
        monkeypatch.undo()

    async def test_resolve_saml_returns_none_without_config(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_saml_config", None)
        assert await _resolve_saml_context("wp_saml.token.value") is None
        monkeypatch.undo()

    async def test_resolve_transport_legacy_key_in_development(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "api_keys", ["dev-legacy-key"])
        monkeypatch.setattr(settings, "environment", "development")
        ctx = await _resolve_transport_identity("dev-legacy-key")
        assert ctx is not None
        assert ctx.is_legacy is True


class TestDashboardDenyPathsBatch14:
    async def test_viewer_cannot_post_guardrails_scan(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Scan Viewer",
            slug=f"scan-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post("/api/scan", json={"text": "hello"}, headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_verify_governance_evidence_chain(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Evidence Verify Viewer",
            slug=f"evv-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/evidence/verify", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_list_governance_evidence(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Evidence List Viewer",
            slug=f"evl-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/evidence", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_export_audit_log(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Audit Export Viewer",
            slug=f"aex-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/audit/export", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_issue_org_api_key(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Issue Key Viewer",
            slug=f"iss-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "blocked", "role": "VIEWER"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_configure_org_mfa(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="MFA Viewer",
            slug=f"mfa-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/mfa",
            json={"mfa_required": True},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_read_authority_ceiling(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Ceiling Viewer",
            slug=f"ceil-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get(f"/api/orgs/{org_id}/authority-ceiling", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_read_billing_mcp_usage(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="MCP Usage Viewer",
            slug=f"mcpu-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/billing/usage/mcp", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_read_eval_results(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Eval Results Viewer",
            slug=f"evalr-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/eval/results", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_analyst_cannot_post_leaderboard_model(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="LB Model Analyst",
            slug=f"lbm-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/leaderboard/models",
            json={"model": "gpt-4", "provider": "openai"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_analyst_cannot_list_incident_db_pending(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Incident Pending Analyst",
            slug=f"incp-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get("/api/incident-db/pending", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_analyst_cannot_put_autonomy_budget(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Budget Analyst",
            slug=f"bud-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/autonomy-budget",
            json={"monthly_actions": 100},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_admin_cannot_open_billing_portal(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Portal Admin",
            slug=f"port-ad-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post("/api/billing/portal", json={}, headers=_bearer(raw))
        assert r.status_code == 403

    async def test_scoped_evidence_read_cannot_post_policy_rule(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Policy Scope",
            slug=f"pol-sc-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped = await app_module._org_repo.create_key(
            org_id,
            "evidence-read-only",
            Role.ADMIN,
            scopes=("evidence:read",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.post(
            "/api/governance/policy/rules",
            json={"name": "rule", "condition": "true", "action": "ALLOW"},
            headers=_bearer(scoped),
        )
        assert r.status_code == 403
        assert "governance:write" in _http_message(r)

    async def test_cross_tenant_org_mfa_update_is_404(self, auth_client: AsyncClient) -> None:
        org_a, _kid_a, raw_a = await seed_org_with_key(
            name="Org A MFA",
            slug=f"orga-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        org_b, _kid_b, _raw_b = await seed_org_with_key(
            name="Org B MFA",
            slug=f"orgb-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_b}/mfa",
            json={"mfa_required": True},
            headers=_bearer(raw_a),
        )
        assert r.status_code == 404

    async def test_viewer_cannot_call_upstream_tool(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Upstream Call Viewer",
            slug=f"upc-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            f"/api/governance/upstream/servers/{uuid.uuid4()}/call",
            json={"tool": "demo", "arguments": {}},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_certify_trust_index_passport(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Trust Cert Viewer",
            slug=f"tstc-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/trust-index/certify/wp-passport-demo",
            headers=_bearer(raw),
        )
        assert r.status_code == 403


class TestDashboardWebConsoleBatch14:
    async def test_web_invitations_list_requires_session(self, web_client: AsyncClient) -> None:
        r = await web_client.get("/api/web/invitations")
        assert r.status_code == 401

    async def test_web_organization_patch_requires_session(self, web_client: AsyncClient) -> None:
        r = await web_client.patch("/api/web/organization", json={"display_name": "X"})
        assert r.status_code == 401

    async def test_web_billing_portal_requires_session(self, web_client: AsyncClient) -> None:
        r = await web_client.post("/api/web/billing/portal", json={})
        assert r.status_code == 401


# ── enterprise/security/service.py deny paths ────────────────────────────────


@pytest.mark.asyncio
async def test_security_verify_totp_invalid_code_denied(engine) -> None:
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
    with pytest.raises(EnterpriseError) as exc:
        await svc.verify_totp(user_id, "000000")
    assert exc.value.code == AUTHENTICATION_FAILED


@pytest.mark.asyncio
async def test_security_verify_totp_without_enrollment_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.verify_totp(user_id, "123456")
    assert exc.value.code == MFA_REQUIRED


@pytest.mark.asyncio
async def test_security_confirm_totp_wrong_code_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    await svc.start_totp(user_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.confirm_totp(user_id, "000000")
    assert exc.value.code == AUTHENTICATION_FAILED


@pytest.mark.asyncio
async def test_security_google_login_raw_token_not_permitted_denied(engine) -> None:
    svc = await _svc(engine, google_client_id="google-client", allow_raw_id_token=False)
    with pytest.raises(EnterpriseError) as exc:
        await svc.google_login(id_token="a.b.c", nonce="n1")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_security_begin_hosted_oauth_google_missing_secret_denied(engine) -> None:
    svc = await _svc(engine, google_client_id="g-id", google_client_secret=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.begin_hosted_oauth(provider="google", redirect_uri="https://app/cb")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_security_consume_step_up_missing_grant_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_step_up(session, SensitiveAction.ADD_PASSKEY, "missing-grant-token")
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_consume_step_up_wrong_session_denied(engine) -> None:
    user_a = await _user(engine, "alice@example.com")
    user_b = await _user(engine, "bob@example.com")
    svc = await _svc(engine)
    _, _, session_a = await _passkey_session(svc, user_a)
    _, _, session_b = await _passkey_session(svc, user_b)
    grant = await svc.issue_step_up(session_a, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_step_up(session_b, SensitiveAction.ADD_PASSKEY, grant)
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_require_step_up_without_grant_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.require_step_up(
            session, SensitiveAction.CHANGE_RECOVERY_METHODS, org_id=None, grant=None
        )
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_evaluate_role_change_owner_requires_passkey(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSWORD,),
        org_id=org_id,
        ip_label=None,
        user_agent=None,
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.evaluate_role_change(session, new_role="OWNER", org_id=org_id)
    assert exc.value.code == PASSKEY_REQUIRED


@pytest.mark.asyncio
async def test_security_break_glass_wrong_principal_denied(engine) -> None:
    owner = await _user(engine)
    intruder = await _user(engine, "intruder@example.com")
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, intruder, org_id=org_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.break_glass(org_id=org_id, user_id=intruder, session=session)
    assert exc.value.code == BREAK_GLASS_DENIED


@pytest.mark.asyncio
async def test_security_break_glass_password_session_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await _break_glass_policy(engine, org_id, owner)
    svc = await _svc(engine)
    _, _, session = await svc.issue_session(
        user_id=owner,
        methods=(AuthMethod.PASSWORD,),
        org_id=org_id,
        ip_label=None,
        user_agent=None,
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.break_glass(org_id=org_id, user_id=owner, session=session)
    assert exc.value.code == PASSKEY_REQUIRED


@pytest.mark.asyncio
async def test_security_start_domain_challenge_unsupported_method_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, owner, org_id=org_id)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.start_domain_challenge(
            org_id=org_id,
            domain="example.com",
            method="EMAIL",
            session=session,
            grant=grant,
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_security_complete_domain_challenge_bad_token_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine, txt_lookup=lambda _d: [])
    _, _, session = await _passkey_session(svc, owner, org_id=org_id)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id)
    token = await svc.start_domain_challenge(
        org_id=org_id,
        domain="example.com",
        method="DNS_TXT",
        session=session,
        grant=grant,
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.complete_domain_challenge(
            org_id=org_id, domain="example.com", method="DNS_TXT", token=token + "x"
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_security_complete_domain_https_well_known_failure_denied(engine) -> None:
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    svc = await _svc(engine, well_known_lookup=lambda _d: "wrong-body")
    _, _, session = await _passkey_session(svc, owner, org_id=org_id)
    grant = await svc.issue_step_up(session, SensitiveAction.CHANGE_COMPANY_DOMAIN, org_id=org_id)
    token = await svc.start_domain_challenge(
        org_id=org_id,
        domain="example.com",
        method="HTTPS_WELL_KNOWN",
        session=session,
        grant=grant,
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.complete_domain_challenge(
            org_id=org_id,
            domain="example.com",
            method="HTTPS_WELL_KNOWN",
            token=token,
        )
    assert exc.value.code == COMPANY_VERIFICATION_REQUIRED


@pytest.mark.asyncio
async def test_security_consume_recovery_token_passkey_path_denied(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.consume_recovery_token("token", passkey_ok=True)
    assert exc.value.code == RECOVERY_REVIEW_REQUIRED


@pytest.mark.asyncio
async def test_security_authenticate_passkey_disabled_user_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    rec, key = await _register_passkey(svc, user_id, session)
    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == user_id).values(disabled=1))
    auth_begin = await svc.begin_webauthn(
        user_id=None, session_id=None, ceremony="authenticate", org_id=None
    )
    challenge = b64url_decode(auth_begin["challenge"])
    acdata, aadata, sig = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=challenge,
        private_key=key,
        sign_count=1,
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.authenticate_passkey(
            client_data_b64=acdata,
            authenticator_data_b64=aadata,
            signature_b64=sig,
            credential_id=rec["credential_id"],
        )
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_security_authenticate_passkey_expected_user_mismatch_denied(engine) -> None:
    user_id = await _user(engine)
    other = await _user(engine, "other@example.com")
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    rec, key = await _register_passkey(svc, user_id, session)
    auth_begin = await svc.begin_webauthn(
        user_id=None, session_id=None, ceremony="authenticate", org_id=None
    )
    challenge = b64url_decode(auth_begin["challenge"])
    acdata, aadata, sig = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=challenge,
        private_key=key,
        sign_count=1,
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.authenticate_passkey(
            client_data_b64=acdata,
            authenticator_data_b64=aadata,
            signature_b64=sig,
            credential_id=rec["credential_id"],
            expected_user_id=other,
        )
    assert exc.value.code == WEBAUTHN_INVALID


@pytest.mark.asyncio
async def test_security_authenticate_passkey_stale_sign_counter_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    rec, key = await _register_passkey(svc, user_id, session)
    auth_begin = await svc.begin_webauthn(
        user_id=None, session_id=None, ceremony="authenticate", org_id=None
    )
    challenge = b64url_decode(auth_begin["challenge"])
    acdata, aadata, sig = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=challenge,
        private_key=key,
        sign_count=1,
    )
    await svc.authenticate_passkey(
        client_data_b64=acdata,
        authenticator_data_b64=aadata,
        signature_b64=sig,
        credential_id=rec["credential_id"],
    )
    auth_begin2 = await svc.begin_webauthn(
        user_id=None, session_id=None, ceremony="authenticate", org_id=None
    )
    challenge2 = b64url_decode(auth_begin2["challenge"])
    acdata2, aadata2, sig2 = assertion_blob(
        rp_id="localhost",
        origin="http://localhost",
        challenge=challenge2,
        private_key=key,
        sign_count=0,
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.authenticate_passkey(
            client_data_b64=acdata2,
            authenticator_data_b64=aadata2,
            signature_b64=sig2,
            credential_id=rec["credential_id"],
        )
    assert exc.value.code == WEBAUTHN_INVALID


@pytest.mark.asyncio
async def test_security_finish_passkey_duplicate_credential_denied(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
    rec, key = await _register_passkey(svc, user_id, session)
    begin = await svc.begin_webauthn(
        user_id=user_id, session_id=session.session_id, ceremony="register"
    )
    challenge = b64url_decode(begin["challenge"])
    cdata, adata, _, _ = registration_blob(
        rp_id="localhost", origin="http://localhost", challenge=challenge, private_key=key
    )
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError) as exc:
        await svc.finish_passkey_registration(
            user_id=user_id,
            session=session,
            client_data_b64=cdata,
            authenticator_data_b64=adata,
            grant=grant,
        )
    assert exc.value.code == WEBAUTHN_INVALID


@pytest.mark.asyncio
async def test_security_microsoft_login_not_configured_denied(engine) -> None:
    svc = await _svc(engine, allow_raw_id_token=True)
    with pytest.raises(EnterpriseError) as exc:
        await svc.microsoft_login(id_token="a.b.c", nonce="n2")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_security_google_login_unexpected_issuer_denied(engine) -> None:
    svc = await _svc(engine, google_client_id="google-client", allow_raw_id_token=True)
    claims = VerifiedIDToken(
        issuer="https://evil.example.com",
        subject="sub",
        audience="google-client",
        email="user@example.com",
        hosted_domain=None,
        tenant_id=None,
        nonce="n3",
        expires_at=int(time.time()) + 120,
        raw={},
    )
    with patch.object(OIDCTokenValidator, "validate", AsyncMock(return_value=claims)):
        with pytest.raises(EnterpriseError) as exc:
            await svc.google_login(id_token="hdr.payload.sig", nonce="n3")
    assert exc.value.code == PROVIDER_TOKEN_INVALID


@pytest.mark.asyncio
async def test_security_link_provider_requires_step_up_grant(engine) -> None:
    user_id = await _user(engine)
    svc = await _svc(engine)
    _, _, session = await _passkey_session(svc, user_id)
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
    with pytest.raises(EnterpriseError) as exc:
        await svc.link_provider(
            session=session,
            provider="GOOGLE",
            claims=claims,
            grant=None,
            account_kind="PERSONAL",
        )
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_verify_totp_replay_same_timestep_denied(engine) -> None:
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
    with pytest.raises(EnterpriseError) as exc:
        await svc.verify_totp(user_id, code)
    assert exc.value.code == CHALLENGE_REPLAY
