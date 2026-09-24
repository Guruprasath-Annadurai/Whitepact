# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-coverage campaign batch 7: remaining ``dashboard/app.py`` routes,
``enterprise/security/service.py``, ``enterprise/service.py``, and
``runtime/authority_kernel.py`` error paths."""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

import responsibleai.dashboard.app as app_module
from responsibleai.dashboard.app import (
    _get_rate_limit_key,
    _safe_billing_return_url,
    app,
    limiter,
    settings,
)
from responsibleai.dashboard.signup_guard import SignupRateWindow
from responsibleai.db.engine import create_engine, organizations, web_invitations, web_users
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    FORBIDDEN,
    INSUFFICIENT_SCOPE,
    INVITE_EXPIRED,
    INVITE_REVOKED,
    LAST_OWNER,
    ORG_DISABLED,
    ORG_SUSPENDED,
    STEP_UP_REQUIRED,
    UNAUTHENTICATED,
    WRONG_TENANT,
    EnterpriseError,
)
from responsibleai.enterprise.roles import Permission
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.service import (
    IdentitySecurityService,
    _hash,
    _iso,
    _now,
)
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import GovernanceStatus, Plan, Role
from responsibleai.runtime.authority_kernel import (
    Phase7AAuthorityKernel,
    QueueTicket,
    _is_deadlock,
    retry_pre_effect,
)
from responsibleai.runtime.errors import (
    AuthorityKernelError,
    CrossTenantAccessError,
    PreEffectCasRejected,
    UncertainExternalEffectError,
)
from tests.org_http_fixtures import seed_org_with_key
from tests.pg_test_url import isolated_pg_url

# ── Shared fixtures ──────────────────────────────────────────────────────────


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


@pytest.fixture
async def pg_url() -> AsyncGenerator[str, None]:
    async for url in isolated_pg_url("wp_batch7_kern"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        yield url


def _bearer(raw: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {raw}"}


async def _user(engine, email: str = "human@example.com") -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


async def _svc(engine, **kwargs) -> IdentitySecurityService:
    return IdentitySecurityService(engine, rp_id="localhost", origin="http://localhost", **kwargs)


def _actor(
    user_id: str,
    org_id: str,
    role: Role,
    *,
    membership_status: str = "ACTIVE",
    actor_type: str = "human",
    scopes: frozenset[str] = frozenset(),
) -> Actor:
    return Actor(
        actor_type=actor_type,
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        membership_status=membership_status,
        scopes=scopes,
    )


async def _org(engine, owner_id: str) -> str:
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner_id,
        name="Batch7 Org",
        slug=f"b7-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    return org["id"]


async def _web_session_with_org(web_client: AsyncClient, email: str) -> tuple[str, str]:
    from urllib.parse import parse_qs, urlparse

    reg = await web_client.post(
        "/api/web/auth/register",
        json={
            "full_name": "Batch Seven User",
            "email": email,
            "password": "Correct-Horse-42!",
            "accepted_terms": True,
        },
    )
    assert reg.status_code == 202
    token = parse_qs(urlparse(reg.json()["verification_url"]).query)["token"][0]
    assert (await web_client.post("/api/web/auth/verify", json={"token": token})).status_code == 200
    login = await web_client.post(
        "/api/web/auth/login",
        json={"email": email, "password": "Correct-Horse-42!"},
    )
    assert login.status_code == 200
    csrf = web_client.cookies.get("wp_csrf", "")
    onboard = await web_client.post(
        "/api/web/onboarding",
        headers={"X-WP-CSRF": csrf},
        json={"organization_name": "Batch Seven Org", "use_case": "coverage"},
    )
    assert onboard.status_code == 200
    return csrf, web_client.cookies.get("wp_session", "")


async def _pg_org(engine, name: str = "B7"):
    repo = OrgRepository(engine)
    return await repo.create_org(name, f"b7-{uuid.uuid4().hex[:10]}", plan=Plan.ENTERPRISE)


def _issue_kwargs(org_id: str, **extra):
    payload = '{"action_type":"tool"}'
    kw = dict(
        organization_id=org_id,
        principal_id="principal-1",
        agent_id="agent-1",
        identity_id="identity-1",
        intent="declared purpose",
        action_type="rai_trust_score",
        target="rai_trust_score",
        action_digest="d" * 64,
        canonical_action_payload=payload,
        approved_arguments={"text": "redacted"},
        idempotency_key=uuid.uuid4().hex,
        target_fingerprint="fp-1",
        caller_organization_id=org_id,
    )
    kw.update(extra)
    return kw


async def _ready_claim(kernel: Phase7AAuthorityKernel, org_id: str, worker: str = "worker-a"):
    issued = await kernel.issue(**_issue_kwargs(org_id))
    await kernel.acquire_lease(
        request_id=issued.request_id, worker_id=worker, organization_id=org_id
    )
    await kernel.admit(request_id=issued.request_id, worker_id=worker, organization_id=org_id)
    claim = await kernel.claim_backend_start(
        request_id=issued.request_id, worker_id=worker, organization_id=org_id
    )
    return issued, claim


class MemoryTransport:
    def __init__(self) -> None:
        self.tickets: list[QueueTicket] = []
        self.fail = False

    def enqueue(self, ticket: QueueTicket) -> None:
        if self.fail:
            raise RuntimeError("redis down")
        self.tickets.append(ticket)


# ── dashboard/app.py: public HTML & ops aliases ─────────────────────────────


class TestDashboardPublicHtmlAndOps:
    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/signup",
            "/status",
            "/leaderboard",
            "/registry",
            "/assess",
            "/trust/legacy",
            "/incident-db",
            "/incident-db/report",
            "/dashboard/settings",
            "/dashboard/billing",
        ],
    )
    async def test_public_html_pages_return_200(self, client: AsyncClient, path: str) -> None:
        r = await client.get(path)
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")

    @pytest.mark.parametrize(
        "path",
        [
            "/health",
            "/healthz",
            "/ready",
            "/readyz",
            "/metrics",
            "/api/metrics",
        ],
    )
    async def test_ops_probe_endpoints_respond(self, client: AsyncClient, path: str) -> None:
        r = await client.get(path)
        assert r.status_code in (200, 503)

    @pytest.mark.parametrize(
        "core_path",
        [
            "/api/health",
            "/api/branding",
            "/api/billing/plans",
            "/api/leaderboard",
            "/api/trust-index/registry",
        ],
    )
    async def test_v1_prefix_rewrites_core_api(self, client: AsyncClient, core_path: str) -> None:
        r = await client.get(f"/api/v1{core_path[len('/api') :]}")
        assert r.status_code == 200

    async def test_sitemap_and_llms_txt_public(self, client: AsyncClient) -> None:
        assert (await client.get("/sitemap.xml")).status_code == 200
        body = (await client.get("/llms.txt")).text
        assert "WhitePact" in body or "trust" in body.lower()

    async def test_validation_envelope_on_malformed_json(self, client: AsyncClient) -> None:
        r = await client.post(
            "/api/evaluate",
            content=b"{not-json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code == 422
        assert r.json()["error"] == "validation_error"


class TestDashboardAppHelpers:
    def test_rate_limit_key_uses_bearer_hash(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [(b"authorization", b"Bearer secret-token-value")],
            "client": ("203.0.113.1", 0),
        }
        req = Request(scope)
        assert _get_rate_limit_key(req).startswith("key:")

    def test_rate_limit_key_falls_back_to_ip_without_bearer(self) -> None:
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "client": ("203.0.113.2", 0),
        }
        req = Request(scope)
        key = _get_rate_limit_key(req)
        assert key.startswith("key:") is False

    def test_safe_billing_return_url_rejects_foreign_origin(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "web_public_url", "https://app.whitepact.test")
        with pytest.raises(Exception) as exc:
            _safe_billing_return_url("https://evil.example/steal")
        assert getattr(exc.value, "status_code", None) == 422

    def test_safe_billing_return_url_uses_fallback_when_empty(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "web_public_url", "https://app.whitepact.test")
        assert _safe_billing_return_url(None).endswith("/dashboard/billing")


# ── dashboard/app.py: web console deny & read paths ───────────────────────────


class TestWebConsoleBatch7:
    async def test_web_api_keys_list_requires_session(self, web_client: AsyncClient) -> None:
        assert (await web_client.get("/api/web/api-keys")).status_code == 401

    async def test_web_create_api_key_requires_csrf(self, web_client: AsyncClient) -> None:
        email = f"keys-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        r = await web_client.post("/api/web/api-keys", json={"name": "dev", "environment": "DEV"})
        assert r.status_code == 403

    async def test_web_rotate_missing_key_is_forbidden(self, web_client: AsyncClient) -> None:
        email = f"rot-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post(
            "/api/web/api-keys/missing-id/rotate",
            headers={"X-WP-CSRF": csrf},
        )
        assert r.status_code == 403

    async def test_web_revoke_missing_key_is_404(self, web_client: AsyncClient) -> None:
        email = f"rev-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.delete(
            "/api/web/api-keys/missing-id",
            headers={"X-WP-CSRF": csrf},
        )
        assert r.status_code == 404

    async def test_web_invitations_list_and_create_require_csrf(
        self, web_client: AsyncClient
    ) -> None:
        email = f"inv-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        assert (
            await web_client.get("/api/web/invitations", headers={"X-WP-CSRF": csrf})
        ).status_code == 200
        r = await web_client.post(
            "/api/web/invitations",
            json={"email": "guest@example.com", "role": "DEVELOPER"},
        )
        assert r.status_code == 403
        ok = await web_client.post(
            "/api/web/invitations",
            headers={"X-WP-CSRF": csrf},
            json={"email": "guest@example.com", "role": "VIEWER"},
        )
        assert ok.status_code == 202

    async def test_web_accept_invitation_invalid_token(self, web_client: AsyncClient) -> None:
        email = f"acc-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post(
            "/api/web/invitations/accept",
            headers={"X-WP-CSRF": csrf},
            json={"token": "not-a-real-invite"},
        )
        assert r.status_code in (400, 403, 404, 422)

    async def test_web_members_list_and_patch_requires_csrf(self, web_client: AsyncClient) -> None:
        email = f"mem-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        members = await web_client.get("/api/web/members", headers={"X-WP-CSRF": csrf})
        assert members.status_code == 200
        assert len(members.json()["members"]) >= 1
        member_id = members.json()["members"][0]["id"]
        r = await web_client.patch(
            f"/api/web/members/{member_id}",
            json={"role": "ADMIN"},
        )
        assert r.status_code == 403

    async def test_web_transfer_ownership_to_self_rejected(self, web_client: AsyncClient) -> None:
        email = f"xfer-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        session = await web_client.get("/api/web/session", headers={"X-WP-CSRF": csrf})
        owner_id = session.json()["user"]["id"]
        r = await web_client.post(
            "/api/web/organizations/transfer-ownership",
            headers={"X-WP-CSRF": csrf},
            json={"new_owner_user_id": owner_id, "confirmation": "TRANSFER OWNERSHIP"},
        )
        assert r.status_code == 400

    async def test_web_logout_all_requires_csrf(self, web_client: AsyncClient) -> None:
        email = f"loa-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        assert (await web_client.post("/api/web/auth/logout-all")).status_code == 403

    async def test_web_dashboard_summary_and_security_domain(self, web_client: AsyncClient) -> None:
        email = f"sum-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        summary = await web_client.get("/api/web/dashboard/summary")
        assert summary.status_code == 200
        assert "pending_approvals" in summary.json()
        security = await web_client.get("/api/web/dashboard/security")
        assert security.status_code == 200
        assert security.json()["domain"] == "security"

    async def test_web_evidence_verify_and_list(self, web_client: AsyncClient) -> None:
        email = f"ev-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        verify = await web_client.get("/api/web/evidence/verify")
        assert verify.status_code == 200
        assert "chain_intact" in verify.json()
        listed = await web_client.get("/api/web/evidence", params={"limit": 5})
        assert listed.status_code == 200
        assert listed.json()["limit"] == 5

    async def test_web_billing_checkout_unconfigured_is_503(self, web_client: AsyncClient) -> None:
        email = f"bill-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post(
            "/api/web/billing/checkout",
            headers={"X-WP-CSRF": csrf},
            json={"plan": "PRO"},
        )
        assert r.status_code == 503

    async def test_web_billing_portal_unconfigured_is_503(self, web_client: AsyncClient) -> None:
        email = f"portal-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post(
            "/api/web/billing/portal",
            headers={"X-WP-CSRF": csrf},
            json={},
        )
        assert r.status_code in (404, 503)

    async def test_web_approval_resolve_missing_is_404(self, web_client: AsyncClient) -> None:
        email = f"apr-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post(
            "/api/web/approvals/missing-approval/resolve",
            headers={"X-WP-CSRF": csrf},
            json={"outcome": "APPROVED", "notes": "n/a"},
        )
        assert r.status_code == 404

    async def test_web_approval_execute_missing_is_404(self, web_client: AsyncClient) -> None:
        email = f"exe-{uuid.uuid4().hex}@example.com"
        csrf, _ = await _web_session_with_org(web_client, email)
        r = await web_client.post(
            "/api/web/approvals/missing-approval/execute",
            headers={"X-WP-CSRF": csrf},
            json={},
        )
        assert r.status_code == 404

    async def test_v1_web_session_alias(self, web_client: AsyncClient) -> None:
        email = f"v1-{uuid.uuid4().hex}@example.com"
        await _web_session_with_org(web_client, email)
        r = await web_client.get("/api/v1/web/session")
        assert r.status_code == 200
        assert r.json()["user"]["email"] == email


class TestOrgApiBatch7:
    async def test_authority_ceiling_get_requires_org_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/orgs/some-org/authority-ceiling")
        assert r.status_code in (400, 401, 404)

    async def test_autonomy_budget_put_invalid_body(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Budget Co",
            slug=f"budget-{uuid.uuid4().hex[:8]}",
            key_name="owner",
            role=Role.OWNER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/autonomy-budget",
            json={"monthly_actions": -1},
            headers=_bearer(raw),
        )
        assert r.status_code == 422

    async def test_cost_record_requires_auth_when_enabled(self, auth_client: AsyncClient) -> None:
        r = await auth_client.post(
            "/api/cost/record",
            json={
                "model": "gpt-4",
                "provider": "openai",
                "input_tokens": 1,
                "output_tokens": 1,
            },
        )
        assert r.status_code == 401

    async def test_cost_summary_days_out_of_range(self, client: AsyncClient) -> None:
        r = await client.get("/api/cost/summary", params={"days": 0})
        assert r.status_code == 400

    async def test_trust_index_check_missing_provider_is_422(self, client: AsyncClient) -> None:
        r = await client.get("/api/trust-index/check", params={"model": "only-model"})
        assert r.status_code == 422

    async def test_eval_regression_returns_empty_baselines(self, client: AsyncClient) -> None:
        r = await client.get("/api/eval/regression/never-seen-model")
        assert r.status_code == 200
        body = r.json()
        assert body["has_baseline"] is False

    async def test_governance_upstream_register_empty_name_is_422(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Upstream Co",
            slug=f"up-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers",
            json={"name": "", "url": "https://example.com/mcp"},
            headers=_bearer(raw),
        )
        assert r.status_code == 422


# ── enterprise/service.py ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iam_authorize_disabled_org_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(
                governance_status=GovernanceStatus.DISABLED.value,
                deactivated_at=_iso(),
            )
        )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(actor, Permission.ORG_VIEW, org_id=org_id)
    assert exc.value.code == ORG_DISABLED


@pytest.mark.asyncio
async def test_iam_authorize_suspended_allows_audit_read(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    auditor = _actor(owner, org_id, Role.AUDITOR)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(governance_status=GovernanceStatus.SUSPENDED.value)
        )
    await iam.authorize(auditor, Permission.AUDIT_READ, org_id=org_id)
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(auditor, Permission.MEMBERS_INVITE, org_id=org_id)
    assert exc.value.code == ORG_SUSPENDED


@pytest.mark.asyncio
async def test_iam_list_visible_workspaces_active_only(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    visible = await iam.list_visible_workspaces(owner)
    assert any(row["id"] == org_id for row in visible)


@pytest.mark.asyncio
async def test_iam_invite_cannot_assign_owner_role(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    with pytest.raises(EnterpriseError):
        await iam.invite_member(actor, org_id, email="x@example.com", role=Role.OWNER)


@pytest.mark.asyncio
async def test_iam_admin_cannot_invite_equal_role(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    admin = await _user(engine, "admin@example.com")
    org_id = await _org(engine, owner)
    owner_actor = _actor(owner, org_id, Role.OWNER)
    _, token = await iam.invite_member(
        owner_actor, org_id, email="admin@example.com", role=Role.ADMIN
    )
    await iam.accept_invitation(token=token, user_id=admin)
    admin_actor = _actor(admin, org_id, Role.ADMIN)
    with pytest.raises(EnterpriseError):
        await iam.invite_member(admin_actor, org_id, email="peer@example.com", role=Role.ADMIN)


@pytest.mark.asyncio
async def test_iam_accept_invitation_revoked_and_expired(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    guest = await _user(engine, "guest@example.com")
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    inv_id, token = await iam.invite_member(
        actor, org_id, email="guest@example.com", role=Role.DEVELOPER
    )
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_invitations).where(web_invitations.c.id == inv_id).values(status="REVOKED")
        )
    with pytest.raises(EnterpriseError) as revoked:
        await iam.accept_invitation(token=token, user_id=guest)
    assert revoked.value.code == INVITE_REVOKED

    _, token2 = await iam.invite_member(actor, org_id, email="guest@example.com", role=Role.VIEWER)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_invitations)
            .where(web_invitations.c.token_hash == _hash(token2))
            .values(expires_at=_iso(_now() - timedelta(hours=1)))
        )
    with pytest.raises(EnterpriseError) as expired:
        await iam.accept_invitation(token=token2, user_id=guest)
    assert expired.value.code == INVITE_EXPIRED


@pytest.mark.asyncio
async def test_iam_accept_invitation_wrong_account_email(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    other = await _user(engine, "other@example.com")
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    _, token = await iam.invite_member(
        actor, org_id, email="invitee@example.com", role=Role.DEVELOPER
    )
    with pytest.raises(EnterpriseError) as wrong:
        await iam.accept_invitation(token=token, user_id=other)
    assert wrong.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_revoke_last_owner_forbidden(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.revoke_member(actor, org_id, user_id=owner)
    assert exc.value.code == LAST_OWNER


@pytest.mark.asyncio
async def test_iam_create_api_key_unknown_scope_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    envs = await iam.list_environments(actor, org_id)
    env_id = envs[0]["id"]
    allowed = MagicMock()
    allowed.allowed = True
    allowed.reason_code = "OK"
    allowed.message = "ok"
    allowed.accountable_human_user_id = owner
    with patch(
        "responsibleai.enterprise.eligibility.EligibilityGate.may_issue_api_key",
        return_value=allowed,
    ):
        with pytest.raises(EnterpriseError) as exc:
            await iam.create_api_key(
                actor,
                org_id,
                name="scoped",
                environment_id=env_id,
                scopes=("not:a-real-scope",),
                expires_at=None,
            )
    assert exc.value.code == INSUFFICIENT_SCOPE


@pytest.mark.asyncio
async def test_iam_rotate_missing_key_wrong_tenant(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.rotate_api_key(actor, org_id, str(uuid.uuid4()))
    assert exc.value.code == WRONG_TENANT


@pytest.mark.asyncio
async def test_iam_deactivate_organization_revokes_sessions(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    await iam.deactivate_organization(actor, org_id)
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(actor, Permission.ORG_VIEW, org_id=org_id)
    assert exc.value.code == ORG_DISABLED


# ── enterprise/security/service.py ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_authenticate_password_wrong_credentials(engine) -> None:
    svc = await _svc(engine)
    await _user(engine)
    assert await svc.authenticate_password("human@example.com", "wrong-password") is None
    ok = await svc.authenticate_password("human@example.com", "correct-horse-battery-staple-9")
    assert ok is not None
    assert ok[0]


@pytest.mark.asyncio
async def test_security_load_session_invalid_token(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.load_session("totally-invalid-session-token")
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_security_list_passkeys_empty(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    assert await svc.list_passkeys(user_id) == []


@pytest.mark.asyncio
async def test_security_totp_confirm_wrong_code(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    await svc.start_totp(user_id)
    with pytest.raises(EnterpriseError):
        await svc.confirm_totp(user_id, "000000")


@pytest.mark.asyncio
async def test_security_verify_totp_without_enrollment(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    with pytest.raises(EnterpriseError):
        await svc.verify_totp(user_id, "123456")


@pytest.mark.asyncio
async def test_security_remove_totp_requires_step_up(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.remove_totp(user_id=user_id, session=session, grant=None)
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_consume_recovery_code_invalid(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    with pytest.raises(EnterpriseError):
        await svc.consume_recovery_code(user_id, "not-a-valid-code")


@pytest.mark.asyncio
async def test_security_revoke_session_idempotent(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    token, _, assurance = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    await svc.revoke_session(user_id=user_id, session_id=assurance.session_id)
    await svc.revoke_session(user_id=user_id, session_id=assurance.session_id)
    with pytest.raises(EnterpriseError):
        await svc.load_session(token)


@pytest.mark.asyncio
async def test_security_require_step_up_issues_grant_when_missing(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.require_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None, grant=None)
    assert exc.value.code == STEP_UP_REQUIRED
    assert ":" in exc.value.message


@pytest.mark.asyncio
async def test_security_disabled_user_cannot_password_login(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == user_id).values(disabled=1))
    assert (
        await svc.authenticate_password("human@example.com", "correct-horse-battery-staple-9")
        is None
    )


# ── runtime/authority_kernel.py ──────────────────────────────────────────────


def test_is_deadlock_detects_sqlstate_and_message() -> None:
    class Orig:
        sqlstate = "40P01"

    assert _is_deadlock(OperationalError("stmt", None, Orig())) is True

    class OrigSer:
        sqlstate = "40001"

    assert _is_deadlock(OperationalError("stmt", None, OrigSer())) is True
    assert _is_deadlock(OperationalError("deadlock detected", None, object())) is True
    assert _is_deadlock(OperationalError("connection reset", None, object())) is False


@pytest.mark.asyncio
async def test_kernel_acquire_lease_inactive_org(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await OrgRepository(engine).set_governance_status(org.id, GovernanceStatus.SUSPENDED)
        with pytest.raises(AuthorityKernelError, match="ACTIVE"):
            await kernel.acquire_lease(
                request_id=issued.request_id, worker_id="w1", organization_id=org.id
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_admit_inactive_org(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        await kernel.acquire_lease(
            request_id=issued.request_id, worker_id="w1", organization_id=org.id
        )
        await OrgRepository(engine).set_governance_status(org.id, GovernanceStatus.SUSPENDED)
        with pytest.raises(AuthorityKernelError, match="ACTIVE"):
            await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_admit_when_attempt_not_leased(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        with pytest.raises(AuthorityKernelError, match="lease"):
            await kernel.admit(request_id=issued.request_id, worker_id="w1", organization_id=org.id)
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_issue_cross_tenant_caller(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org_a = await _pg_org(engine, "A")
        org_b = await _pg_org(engine, "B")
        kernel = Phase7AAuthorityKernel(engine)
        with pytest.raises(CrossTenantAccessError):
            await kernel.issue(**_issue_kwargs(org_a.id, caller_organization_id=org_b.id))
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_external_fingerprint_mismatch(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        with pytest.raises(PreEffectCasRejected, match="fingerprint"):
            await kernel.claim_external_effect_transmission(
                claim, action_digest=claim.action_digest, target_fingerprint="other-fp"
            )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_mark_uncertain_idempotent_when_already_uncertain(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        _, claim = await _ready_claim(kernel, org.id)
        await kernel.claim_external_effect_transmission(
            claim, action_digest=claim.action_digest, target_fingerprint="fp-1"
        )
        with pytest.raises(UncertainExternalEffectError):
            await kernel.mark_external_uncertain(claim, reason="timeout")
        await kernel.mark_external_uncertain(claim, reason="timeout again")
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_publish_outbox_success_and_none_when_empty(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        await kernel.issue(**_issue_kwargs(org.id))
        transport = MemoryTransport()
        ticket = await kernel.publish_outbox(publisher_id="pub-b7", transport=transport)
        assert ticket is not None
        assert len(transport.tickets) == 1
        empty = await kernel.publish_outbox(publisher_id="pub-b7", transport=transport)
        assert empty is None
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_kernel_publish_outbox_enqueue_failure_returns_pending(pg_url: str) -> None:
    engine = create_engine(pg_url)
    try:
        org = await _pg_org(engine)
        kernel = Phase7AAuthorityKernel(engine)
        issued = await kernel.issue(**_issue_kwargs(org.id))
        transport = MemoryTransport()
        transport.fail = True
        with pytest.raises(AuthorityKernelError, match="Redis"):
            await kernel.publish_outbox(publisher_id="pub-b7", transport=transport)
        row = await kernel.claim_outbox_row(publisher_id="pub-b7")
        assert row is not None
        assert row["request_id"] == issued.request_id
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_retry_pre_effect_deadlock_then_success() -> None:
    class Orig:
        sqlstate = "40P01"

    calls = {"n": 0}

    async def flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise OperationalError("deadlock", None, Orig())
        return "ok"

    assert await retry_pre_effect(flaky, retries=3) == "ok"
    assert calls["n"] == 2
