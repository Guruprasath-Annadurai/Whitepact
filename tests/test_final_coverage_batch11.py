# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 11 branch-coverage: remaining ``dashboard/app.py`` deny paths,
``enterprise/security/service.py``, ``enterprise/service.py``,
``mcp/governance_integration.py``, and ``db/org_repository.py``."""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from starlette.requests import Request

import responsibleai.dashboard.app as app_module
from responsibleai.dashboard.app import (
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
from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import OrgRepository, _generate_raw_key
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    FORBIDDEN,
    INSUFFICIENT_SCOPE,
    MEMBERSHIP_REVOKED,
    UNAUTHENTICATED,
    WEBAUTHN_INVALID,
    WRONG_ENVIRONMENT,
    WRONG_TENANT,
    EnterpriseError,
)
from responsibleai.enterprise.roles import Permission
from responsibleai.enterprise.security.policy import AuthMethod, SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.governance import WhitePactRuntimeGateway
from responsibleai.mcp.governance_integration import GovernanceServices, apply_governance
from responsibleai.rbac.models import GovernanceStatus, OrgContext, Plan, Role
from tests.org_http_fixtures import seed_org_with_key


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


def _minimal_gov_services(**overrides) -> GovernanceServices:
    base = {
        "gateway": WhitePactRuntimeGateway(),
        "evidence_repo": MagicMock(),
        "approval_repo": MagicMock(),
        "policy_repo": MagicMock(),
        "trust_client": MagicMock(),
    }
    base.update(overrides)
    return GovernanceServices(**base)


async def _org(engine, owner_id: str) -> str:
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner_id,
        name="Batch11 Org",
        slug=f"b11-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    return org["id"]


# ── dashboard/app.py helpers ─────────────────────────────────────────────────


class TestRateLimitKeyAndIdentityResolution:
    def test_rate_limit_key_hashes_bearer_token(self) -> None:
        req = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/orgs",
                "headers": [(b"authorization", b"Bearer secret-token-value")],
                "client": ("203.0.113.1", 1234),
            }
        )
        key = _get_rate_limit_key(req)
        assert key.startswith("key:")

    def test_rate_limit_key_empty_bearer_falls_back_to_ip(self) -> None:
        req = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/orgs",
                "headers": [(b"authorization", b"Bearer    ")],
                "client": ("203.0.113.2", 1234),
            }
        )
        key = _get_rate_limit_key(req)
        assert key.startswith("203.0.113.2")

    async def test_resolve_oidc_skips_rai_prefix(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_oidc_provider", MagicMock())
        assert await _resolve_oidc_context("rai_some_org_key") is None
        monkeypatch.undo()

    async def test_resolve_oidc_invalid_jwt_returns_none(self) -> None:
        provider = MagicMock()
        provider.validate_token = AsyncMock(side_effect=ValueError("bad jwt"))
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_oidc_provider", provider)
        assert await _resolve_oidc_context("eyJhbGciOiJIUzI1NiJ9.e30.sig") is None
        monkeypatch.undo()

    async def test_resolve_saml_wrong_prefix_returns_none(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_saml_config", MagicMock())
        assert await _resolve_saml_context("rai_not_saml") is None
        monkeypatch.undo()

    async def test_resolve_transport_legacy_bootstrap_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
        ctx = await _resolve_transport_identity("bootstrap-test-key")
        assert ctx is not None
        assert ctx.is_legacy is True
        assert ctx.authentication_method == "legacy_static"

    async def test_resolve_transport_unknown_token_returns_none(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "api_keys", [])
        monkeypatch.setattr(app_module, "_oidc_provider", None)
        monkeypatch.setattr(app_module, "_saml_config", None)
        monkeypatch.setattr(app_module, "_org_repo", None)
        assert await _resolve_transport_identity(f"rai_{secrets.token_hex(24)}") is None


class TestMachineScopeEnforcement:
    def test_governance_write_scope_required_for_post(self) -> None:
        ctx = OrgContext(
            key_id="k1",
            role=Role.ADMIN,
            org_id="org-1",
            scopes=frozenset({"governance:read"}),
        )
        req = _scope_request("POST", "/api/governance/policy/rules")
        with pytest.raises(Exception) as exc:
            _enforce_machine_scope(req, ctx)
        assert getattr(exc.value, "status_code", None) == 403
        assert "governance:write" in str(exc.value.detail)

    def test_evidence_read_scope_required_for_get(self) -> None:
        ctx = OrgContext(
            key_id="k1",
            role=Role.ANALYST,
            org_id="org-1",
            scopes=frozenset({"governance:read"}),
        )
        req = _scope_request("GET", "/api/governance/evidence")
        with pytest.raises(Exception) as exc:
            _enforce_machine_scope(req, ctx)
        assert getattr(exc.value, "status_code", None) == 403
        assert "evidence:read" in str(exc.value.detail)

    def test_agents_write_scope_required(self) -> None:
        ctx = OrgContext(
            key_id="k1",
            role=Role.ADMIN,
            org_id="org-1",
            scopes=frozenset({"agents:read"}),
        )
        req = _scope_request("POST", "/api/agents/register")
        with pytest.raises(Exception) as exc:
            _enforce_machine_scope(req, ctx)
        assert getattr(exc.value, "status_code", None) == 403

    def test_legacy_static_skips_scope_gate(self) -> None:
        ctx = OrgContext(
            key_id="legacy:abc",
            role=Role.VIEWER,
            is_legacy=True,
            scopes=frozenset({"legacy:compat"}),
            authentication_method="legacy_static",
        )
        _enforce_machine_scope(_scope_request("POST", "/api/governance/tools/call"), ctx)


class TestDashboardDenyPathsBatch11:
    async def test_viewer_cannot_issue_org_keys(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Keys Viewer Co",
            slug=f"kv-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "child", "role": "ANALYST"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_configure_sso(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="SSO Viewer Co",
            slug=f"sso-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.put(
            f"/api/orgs/{org_id}/sso",
            json={"required": True},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_analyst_cannot_open_billing_portal(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Portal Analyst Co",
            slug=f"portal-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post("/api/billing/portal", json={}, headers=_bearer(raw))
        assert r.status_code == 403

    async def test_analyst_cannot_delete_autonomy_budget(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Budget Analyst Co",
            slug=f"bud-an-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.delete(f"/api/orgs/{org_id}/autonomy-budget", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_admin_cannot_delete_organization(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Delete Admin Co",
            slug=f"del-adm-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.delete(f"/api/orgs/{org_id}", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_scoped_governance_write_cannot_delete_workflow_rule(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="WF Scope Co",
            slug=f"wf-sc-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped = await app_module._org_repo.create_key(
            org_id,
            "gov-read",
            Role.ADMIN,
            scopes=("governance:read",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.delete(
            "/api/governance/workflow-rules/some-rule",
            headers=_bearer(scoped),
        )
        assert r.status_code == 403
        assert "scope" in _http_message(r).lower()

    async def test_scoped_evidence_read_cannot_post_governance_outcome(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Outcome Scope Co",
            slug=f"out-sc-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped = await app_module._org_repo.create_key(
            org_id,
            "ev-read",
            Role.ANALYST,
            scopes=("evidence:read",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.post(
            "/api/governance/evidence/ev-1/outcome",
            json={"status": "SUCCESS"},
            headers=_bearer(scoped),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_post_incidents(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Inc Viewer Co",
            slug=f"inc-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/incidents",
            json={"title": "t", "severity": "low", "description": "d"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_run_eval_compare(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Eval Viewer Co",
            slug=f"eval-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/eval/compare",
            json={"model_a": "m1", "model_b": "m2", "prompt": "p"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_read_governance_policy(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Policy Viewer Co",
            slug=f"pol-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/policy", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_analyst_can_read_governance_policy(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Policy Analyst Co",
            slug=f"pol-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.get("/api/governance/policy", headers=_bearer(raw))
        assert r.status_code == 200
        assert r.json()["org_id"] == _org_id

    async def test_legacy_bootstrap_blocked_from_webhooks_register(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.post(
            "/api/webhooks",
            json={"url": "https://example.com/hook", "events": ["approval.requested"]},
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403

    async def test_legacy_bootstrap_blocked_from_governance_tool_call(
        self, auth_client: AsyncClient
    ) -> None:
        r = await auth_client.post(
            "/api/governance/tools/call",
            json={"name": "rai_health", "arguments": {}, "purpose": "probe"},
            headers=_bearer("bootstrap-test-key"),
        )
        assert r.status_code == 403

    async def test_get_autonomy_budget_cross_tenant_is_404(self, auth_client: AsyncClient) -> None:
        org_id, _kid, raw = await seed_org_with_key(
            name="Budget Tenant Co",
            slug=f"bud-t-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        r = await auth_client.get(f"/api/orgs/{uuid.uuid4()}/autonomy-budget", headers=_bearer(raw))
        assert r.status_code == 404

    async def test_revoke_key_cross_tenant_is_404(self, auth_client: AsyncClient) -> None:
        org_id, key_id, raw = await seed_org_with_key(
            name="Revoke Tenant Co",
            slug=f"rev-t-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        other_org = str(uuid.uuid4())
        r = await auth_client.delete(
            f"/api/orgs/{other_org}/keys/{key_id}",
            headers=_bearer(raw),
        )
        assert r.status_code == 404

    async def test_governance_upstream_list_requires_org_key(self, client: AsyncClient) -> None:
        r = await client.get("/api/governance/upstream/servers")
        assert r.status_code == 400

    async def test_governance_policy_delete_viewer_forbidden(
        self, auth_client: AsyncClient
    ) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Policy Del Viewer Co",
            slug=f"pol-dv-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.delete("/api/governance/policy/rules/some-id", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_post_evaluate_trust(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Evaluate Viewer Co",
            slug=f"eval-tr-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/evaluate",
            json={
                "model": "gpt-4",
                "provider": "openai",
                "fairness": 0.8,
                "privacy": 0.8,
                "security": 0.8,
                "robustness": 0.8,
                "compliance": 0.8,
                "authenticity": 0.8,
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_run_supplychain_scan(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Supply Viewer Co",
            slug=f"sup-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/supplychain/scan",
            json={
                "server_name": "demo",
                "publisher": "test",
                "tools": [{"name": "t", "description": "d"}],
                "check_known_incidents": False,
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_record_cost(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Cost Viewer Co",
            slug=f"cost-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/cost/record",
            json={
                "model": "gpt-4",
                "provider": "openai",
                "input_tokens": 1,
                "output_tokens": 1,
            },
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_web_delete_account_requires_csrf(self, web_client: AsyncClient) -> None:
        r = await web_client.delete("/api/web/account")
        assert r.status_code == 401

    async def test_web_revoke_invitation_requires_csrf(self, web_client: AsyncClient) -> None:
        r = await web_client.delete(f"/api/web/invitations/{uuid.uuid4()}")
        assert r.status_code in (401, 403)


# ── db/org_repository.py ───────────────────────────────────────────────────


class TestOrgRepositoryBatch11:
    def test_generate_raw_key_environment_prefixes(self) -> None:
        assert _generate_raw_key("test").startswith("wp_test_")
        assert _generate_raw_key("live").startswith("wp_live_")
        with pytest.raises(ValueError, match="test.*live"):
            _generate_raw_key("staging")

    async def test_set_governance_status_invalid(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Gov", f"gov-{uuid.uuid4().hex[:8]}")
        with pytest.raises(ValueError, match="invalid governance_status"):
            await repo.set_governance_status(org.id, "NOT_A_STATUS")

    async def test_set_governance_status_missing_org(self, engine) -> None:
        repo = OrgRepository(engine)
        assert (
            await repo.set_governance_status(str(uuid.uuid4()), GovernanceStatus.SUSPENDED) is False
        )

    async def test_update_org_name(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Old Name", f"name-{uuid.uuid4().hex[:8]}")
        assert await repo.update_org_name(org.id, "New Name") is True
        fetched = await repo.get_org(org.id)
        assert fetched is not None
        assert fetched.name == "New Name"

    async def test_apply_paddle_entitlement_rejects_bad_customer_id(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Paddle", f"pdl-{uuid.uuid4().hex[:8]}")
        with pytest.raises(ValueError, match="ctm_"):
            await repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id="bad",
                subscription_id=None,
                plan=Plan.PRO,
                occurred_at=datetime.now(UTC).isoformat(),
            )

    async def test_apply_paddle_entitlement_requires_timestamp(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Paddle2", f"pdl2-{uuid.uuid4().hex[:8]}")
        with pytest.raises(ValueError, match="occurred_at"):
            await repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id="ctm_test",
                subscription_id=None,
                plan=Plan.PRO,
            )

    async def test_get_org_by_paddle_customer(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Paddle3", f"pdl3-{uuid.uuid4().hex[:8]}")
        ts = datetime.now(UTC).isoformat()
        await repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id="ctm_lookup",
            subscription_id="sub_lookup",
            plan=Plan.PRO,
            occurred_at=ts,
        )
        found = await repo.get_org_by_paddle_customer("ctm_lookup")
        assert found is not None
        assert found.id == org.id


# ── mcp/governance_integration.py ───────────────────────────────────────────


class TestGovernanceIntegrationBatch11:
    async def test_apply_governance_suspended_org_blocked(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Suspended", f"sus-{uuid.uuid4().hex[:8]}")
        await repo.set_governance_status(org.id, GovernanceStatus.SUSPENDED)
        ctx = OrgContext(key_id="key-1", role=Role.ANALYST, org_id=org.id, plan=Plan.ENTERPRISE)
        outcome = await apply_governance(
            "rai_health",
            {},
            ctx,
            _minimal_gov_services(org_repo=repo),
            purpose="batch11",
        )
        assert outcome.proceed is False
        assert outcome.blocked_response is not None
        assert outcome.blocked_response["error"] == "organization_not_governable"

    async def test_apply_governance_missing_org_blocked(self, engine) -> None:
        repo = OrgRepository(engine)
        missing = str(uuid.uuid4())
        ctx = OrgContext(key_id="key-1", role=Role.ANALYST, org_id=missing, plan=Plan.ENTERPRISE)
        outcome = await apply_governance(
            "rai_health",
            {},
            ctx,
            _minimal_gov_services(org_repo=repo),
            purpose="batch11",
        )
        assert outcome.proceed is False
        assert outcome.blocked_response["governance_status"] == "UNKNOWN"

    async def test_apply_governance_without_authority_resolver(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Active", f"act-{uuid.uuid4().hex[:8]}")
        ctx = OrgContext(key_id="key-1", role=Role.ANALYST, org_id=org.id, plan=Plan.ENTERPRISE)
        outcome = await apply_governance(
            "rai_health",
            {},
            ctx,
            _minimal_gov_services(org_repo=repo, authority_resolver=None),
            purpose="batch11",
        )
        assert outcome.proceed is False
        assert outcome.blocked_response["error"] == "governance_authority_unavailable"

    async def test_apply_governance_nonce_epoch_must_be_paired(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("Nonce", f"nonce-{uuid.uuid4().hex[:8]}")
        ctx = OrgContext(key_id="key-1", role=Role.ANALYST, org_id=org.id, plan=Plan.ENTERPRISE)
        with pytest.raises(ValueError, match="both nonce and epoch"):
            await apply_governance(
                "rai_health",
                {},
                ctx,
                _minimal_gov_services(org_repo=repo, nonce_repo=MagicMock(), epoch_repo=None),
                purpose="batch11",
            )


# ── enterprise/service.py ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iam_create_workspace_invalid_kind(engine) -> None:
    owner = await _user(engine)
    iam = EnterpriseIAM(engine)
    with pytest.raises(EnterpriseError) as exc:
        await iam.create_workspace(
            actor_user_id=owner,
            name="Bad",
            slug=f"bad-{uuid.uuid4().hex[:8]}",
            kind="PARTNERSHIP",
        )
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_authorize_revoked_membership(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER, membership_status="REVOKED")
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(actor, Permission.ORG_VIEW, org_id=org_id)
    assert exc.value.code == MEMBERSHIP_REVOKED


@pytest.mark.asyncio
async def test_iam_authorize_api_key_missing_scope(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(
        owner,
        org_id,
        Role.OWNER,
        actor_type="api_key",
        scopes=frozenset({"governance:read"}),
    )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(
            actor,
            Permission.ORG_VIEW,
            org_id=org_id,
            required_scope="governance:write",
        )
    assert exc.value.code == INSUFFICIENT_SCOPE


@pytest.mark.asyncio
async def test_iam_authorize_wrong_environment(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(
            actor,
            Permission.ORG_VIEW,
            org_id=org_id,
            environment_id=str(uuid.uuid4()),
        )
    assert exc.value.code == WRONG_ENVIRONMENT


@pytest.mark.asyncio
async def test_iam_update_settings_strips_privileged_keys(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    await iam.update_settings(
        actor,
        org_id,
        display_name=None,
        settings={"plan": "ENTERPRISE", "governance_status": "DISABLED", "timezone": "UTC"},
    )
    org = await iam._load_org(org_id)
    assert org is not None
    assert "plan" not in (org.get("settings_json") or "{}")
    assert "timezone" in (org.get("settings_json") or "{}")


@pytest.mark.asyncio
async def test_iam_change_role_cannot_assign_owner(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    guest = await _user(engine, "guest@example.com")
    org_id = await _org(engine, owner)
    owner_actor = _actor(owner, org_id, Role.OWNER)
    _, token = await iam.invite_member(
        owner_actor, org_id, email="guest@example.com", role=Role.ADMIN
    )
    await iam.accept_invitation(token=token, user_id=guest)
    with pytest.raises(EnterpriseError) as exc:
        await iam.change_role(owner_actor, org_id, user_id=guest, role=Role.OWNER)
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_list_members_wrong_tenant(engine) -> None:
    iam = EnterpriseIAM(engine)
    alice = await _user(engine, "alice@example.com")
    bob = await _user(engine, "bob@example.com")
    org_a = await _org(engine, alice)
    org_b = await _org(engine, bob)
    with pytest.raises(EnterpriseError) as exc:
        await iam.list_members(_actor(alice, org_a, Role.OWNER), org_b)
    assert exc.value.code == WRONG_TENANT


# ── enterprise/security/service.py ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_consume_replay_duplicate(engine) -> None:
    svc = await _svc(engine)
    await svc.consume_replay("test-kind", "replay-key-1")
    with pytest.raises(EnterpriseError):
        await svc.consume_replay("test-kind", "replay-key-1")


@pytest.mark.asyncio
async def test_security_request_recovery_unknown_email_is_silent(engine) -> None:
    svc = await _svc(engine)
    await svc.request_recovery("nobody@example.com")


@pytest.mark.asyncio
async def test_security_begin_webauthn_unknown_ceremony(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.begin_webauthn(user_id=user_id, session_id=None, ceremony="not-real", org_id=None)
    assert exc.value.code == WEBAUTHN_INVALID


@pytest.mark.asyncio
async def test_security_password_login_unverified_email(engine) -> None:
    svc = await _svc(engine)
    web = WebIdentityRepository(engine)
    _user_id, _token = await web.register(
        "Unverified", "unverified@example.com", "Correct-Horse-42!"
    )
    assert await svc.authenticate_password("unverified@example.com", "Correct-Horse-42!") is None


@pytest.mark.asyncio
async def test_security_revoke_all_sessions(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    token1, _, _ = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    token2, _, _ = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSWORD,), ip_label=None, user_agent=None
    )
    await svc.revoke_all_sessions(user_id=user_id)
    with pytest.raises(EnterpriseError) as exc:
        await svc.load_session(token1)
    assert exc.value.code == UNAUTHENTICATED
    with pytest.raises(EnterpriseError):
        await svc.load_session(token2)


@pytest.mark.asyncio
async def test_security_authenticate_passkey_unknown_credential(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.authenticate_passkey(
            client_data_b64="e30",
            authenticator_data_b64="e30",
            signature_b64="e30",
            credential_id="missing-cred",
        )
    assert exc.value.code == WEBAUTHN_INVALID


@pytest.mark.asyncio
async def test_security_consume_step_up_wrong_action_rejected(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id,
        methods=(AuthMethod.PASSKEY_UV,),
        ip_label="203.0.113.1",
        user_agent="test",
    )
    grant = await svc.issue_step_up(session, SensitiveAction.ADD_PASSKEY, org_id=None)
    with pytest.raises(EnterpriseError):
        await svc.consume_step_up(session, SensitiveAction.REMOVE_PASSKEY, grant)


@pytest.mark.asyncio
async def test_iam_list_visible_workspaces_marks_disabled_org(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await iam.deactivate_organization(_actor(owner, org_id, Role.OWNER), org_id)
    visible = await iam.list_visible_workspaces(owner)
    row = next(item for item in visible if item["id"] == org_id)
    assert row["governance_status"] == GovernanceStatus.DISABLED.value


@pytest.mark.asyncio
async def test_iam_wrong_tenant_on_invite(engine) -> None:
    iam = EnterpriseIAM(engine)
    alice = await _user(engine, "alice@example.com")
    bob = await _user(engine, "bob@example.com")
    org_a = await _org(engine, alice)
    org_b = await _org(engine, bob)
    with pytest.raises(EnterpriseError) as exc:
        await iam.invite_member(
            _actor(alice, org_a, Role.OWNER), org_b, email="x@example.com", role=Role.VIEWER
        )
    assert exc.value.code == WRONG_TENANT
