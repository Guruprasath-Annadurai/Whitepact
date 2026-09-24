# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Batch 12 branch-coverage: ``dashboard/app.py`` SAML/OIDC startup and governance
deny paths, ``enterprise/security/service.py``, ``enterprise/service.py``,
``sovereign/cli_core.py``, and ``isolation/container_backend.py``."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import click
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

import responsibleai.dashboard.app as app_module
from responsibleai.auth.oidc import JWTClaims
from responsibleai.dashboard.app import (
    _enforce_machine_scope,
    _get_rate_limit_key,
    _resolve_oidc_context,
    _resolve_saml_context,
    app,
    limiter,
    settings,
)
from responsibleai.db.engine import create_engine
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.errors import (
    API_KEY_ISSUANCE_NOT_ALLOWED,
    ENVIRONMENT_DISABLED,
    FORBIDDEN,
    INVITE_REPLAY,
    LAST_OWNER,
    ORG_DISABLED,
    ORG_SUSPENDED,
    STEP_UP_REQUIRED,
    UNAUTHENTICATED,
    WRONG_TENANT,
    EnterpriseError,
)
from responsibleai.enterprise.roles import Permission
from responsibleai.enterprise.security.policy import AuthMethod
from responsibleai.enterprise.security.service import IdentitySecurityService
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    IsolationBackendUnavailableError,
    IsolationPolicyViolationError,
)
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
    ResourceLimits,
)
from responsibleai.rbac.models import GovernanceStatus, OrgContext, Role
from responsibleai.sovereign import cli_core
from responsibleai.sovereign.exit_codes import (
    EXIT_GOVERNANCE,
    EXIT_INVALID,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    EXIT_UNKNOWN,
)
from tests.org_http_fixtures import seed_org_with_key


@pytest.fixture(autouse=True)
def _reset_dashboard_provider_singletons() -> None:
    """Lifespan tests in this module must not leak OIDC/SAML into later suites."""
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


async def _org(engine, owner_id: str) -> str:
    iam = EnterpriseIAM(engine)
    org = await iam.create_workspace(
        actor_user_id=owner_id,
        name="Batch12 Org",
        slug=f"b12-{uuid.uuid4().hex[:8]}",
        kind="ORGANIZATION",
    )
    return org["id"]


def _minimal_manifest(path: Path, org_id: str = "org-cli") -> Path:
    path.write_text(
        f"""schema_version: "1.0"
organization_id: {org_id}
environment: development
actors: []
capabilities: []
""",
        encoding="utf-8",
    )
    return path


# ── sovereign/cli_core.py ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"disposition": "DENY"}, EXIT_GOVERNANCE),
        ({"status": "denied"}, EXIT_GOVERNANCE),
        ({"disposition": "APPROVAL_REQUIRED"}, EXIT_UNKNOWN),
        ({"status": "approval_required"}, EXIT_UNKNOWN),
        ({"disposition": "UNKNOWN"}, EXIT_UNKNOWN),
        ({"disposition": "UNAVAILABLE"}, EXIT_UNAVAILABLE),
        ({"disposition": "ALLOW"}, EXIT_OK),
        ({}, EXIT_OK),
    ],
)
def test_disposition_exit_maps_payload(payload: dict, expected: int) -> None:
    assert cli_core.disposition_exit(payload) == expected


def test_emit_json_mode_writes_json(capsys: pytest.CaptureFixture[str]) -> None:
    cli_core.emit({"ok": True}, "ignored", json_mode=True)
    out = capsys.readouterr().out.strip()
    assert json.loads(out)["ok"] is True


def test_emit_human_mode_writes_text(capsys: pytest.CaptureFixture[str]) -> None:
    cli_core.emit({"ok": True}, "hello sovereign", json_mode=False)
    assert capsys.readouterr().out.strip() == "hello sovereign"


def test_ctx_from_defaults_environment() -> None:
    ctx = cli_core.ctx_from("org-abc")
    assert ctx.organization_id == "org-abc"
    assert ctx.environment == "development"


@pytest.mark.asyncio
async def test_cmd_status_returns_ok() -> None:
    assert await cli_core.cmd_status(json_mode=True) == EXIT_OK


@pytest.mark.asyncio
async def test_cmd_sandbox_returns_ok() -> None:
    assert await cli_core.cmd_sandbox(json_mode=False) == EXIT_OK


@pytest.mark.asyncio
async def test_cmd_explain_requires_target() -> None:
    assert await cli_core.cmd_explain("org-1", None, None, json_mode=True) == EXIT_INVALID


@pytest.mark.asyncio
async def test_cmd_doctor_warns_without_org() -> None:
    assert await cli_core.cmd_doctor(None, None, json_mode=True) == EXIT_OK


@pytest.mark.asyncio
async def test_cmd_doctor_fails_on_bad_manifest(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [a, mapping", encoding="utf-8")
    assert await cli_core.cmd_doctor("org-1", bad, json_mode=True) == EXIT_INVALID


@pytest.mark.asyncio
async def test_cmd_doctor_passes_valid_manifest(tmp_path: Path) -> None:
    manifest = _minimal_manifest(tmp_path / "whitepact.yaml")
    assert await cli_core.cmd_doctor("org-cli", manifest, json_mode=True) == EXIT_OK


@pytest.mark.asyncio
async def test_cmd_capsule_validate_requires_org_or_file() -> None:
    assert await cli_core.cmd_capsule_validate(None, None, json_mode=True) == EXIT_INVALID


@pytest.mark.asyncio
async def test_cmd_policy_test_requires_cases() -> None:
    assert await cli_core.cmd_policy_test("org-1", None, None, json_mode=True) == EXIT_INVALID


@pytest.mark.asyncio
async def test_cmd_policy_lint_invalid_rule_json() -> None:
    rules = json.dumps([{"not_a_rule": True}])
    with pytest.raises(click.ClickException, match="invalid policy rule"):
        await cli_core.cmd_policy_lint("org-1", None, rules, json_mode=True)


def test_load_rules_requires_file_or_inline() -> None:
    with pytest.raises(click.ClickException, match="rules-file"):
        cli_core._load_rules(None, None)


@pytest.mark.asyncio
async def test_cmd_xray_emits_redacted_payload() -> None:
    assert await cli_core.cmd_xray("org-xray", json_mode=True) == EXIT_OK


@pytest.mark.asyncio
async def test_cmd_trace_unknown_evidence_raises() -> None:
    from responsibleai.sovereign.errors import SovereignTenantIsolationError

    with pytest.raises(SovereignTenantIsolationError, match="trace not found"):
        await cli_core.cmd_trace("org-trace", "missing-evidence", json_mode=True)


@pytest.mark.asyncio
async def test_cmd_capsule_validate_with_org() -> None:
    assert await cli_core.cmd_capsule_validate(None, "org-cap", json_mode=True) == EXIT_OK


def test_run_async_maps_click_exception_to_invalid(capsys: pytest.CaptureFixture[str]) -> None:
    async def _boom() -> int:
        raise click.ClickException("bad input")

    with pytest.raises(SystemExit) as exc:
        cli_core.run_async(_boom())
    assert exc.value.code == EXIT_INVALID
    assert "bad input" in capsys.readouterr().out


# ── dashboard/app.py lifespan & identity ─────────────────────────────────────


class TestDashboardLifespanBatch12:
    @pytest.mark.asyncio
    async def test_oidc_provider_initialized_on_startup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "saml_idp_entity_id", None)
        monkeypatch.setattr(settings, "oidc_issuer", "https://idp.example.com")
        monkeypatch.setattr(settings, "oidc_client_id", "dashboard-client")
        app_module._oidc_provider = None
        async with LifespanManager(app, startup_timeout=15):
            assert app_module._oidc_provider is not None
            assert app_module._oidc_provider.issuer == "https://idp.example.com"

    @pytest.mark.asyncio
    async def test_saml_config_initialized_when_secret_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "oidc_issuer", None)
        monkeypatch.setattr(settings, "saml_idp_entity_id", "https://idp.example/metadata")
        monkeypatch.setattr(settings, "saml_session_secret", "test-session-secret-value")
        app_module._saml_config = None
        async with LifespanManager(app, startup_timeout=15):
            assert app_module._saml_config is not None

    @pytest.mark.asyncio
    async def test_paddle_init_skipped_when_misconfigured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "saml_idp_entity_id", None)
        monkeypatch.setattr(settings, "oidc_issuer", None)
        monkeypatch.setattr(settings, "paddle_api_key", "")
        app_module._paddle_billing_service = None
        async with LifespanManager(app, startup_timeout=15):
            assert app_module._paddle_billing_service is None

    @pytest.mark.asyncio
    async def test_stripe_initialized_in_non_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "environment", "development")
        monkeypatch.setattr(settings, "saml_idp_entity_id", None)
        monkeypatch.setattr(settings, "oidc_issuer", None)
        monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_batch12")
        monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test")
        stub = MagicMock(name="stripe_service_stub")
        monkeypatch.setattr(app_module, "StripeService", lambda **_kwargs: stub)
        app_module._stripe_service = None
        async with LifespanManager(app, startup_timeout=15):
            assert app_module._stripe_service is stub

    @pytest.mark.asyncio
    async def test_stripe_ignored_in_production_logs_only(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "responsibleai.enterprise.preflight.assert_hosted_enterprise_boot_safe",
            lambda _settings: None,
        )
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "saml_idp_entity_id", None)
        monkeypatch.setattr(settings, "oidc_issuer", None)
        monkeypatch.setattr(settings, "stripe_secret_key", "sk_live_ignored")
        monkeypatch.setattr(app_module._webhook_manager, "load_configs", AsyncMock(return_value=0))
        app_module._stripe_service = None
        async with LifespanManager(app, startup_timeout=15):
            assert app_module._stripe_service is None

    @pytest.mark.asyncio
    async def test_multi_replica_warning_on_sqlite_memory(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "multi_replica", True)
        monkeypatch.setattr(settings, "saml_idp_entity_id", None)
        monkeypatch.setattr(settings, "oidc_issuer", None)
        async with LifespanManager(app, startup_timeout=15):
            pass


def test_limiter_module_uses_redis_storage_when_configured() -> None:
    """Cover redis ``storage_uri`` branch without reloading ``app`` (reload poisons suite)."""
    import subprocess

    script = """
import os
os.environ["RAI_REDIS_URL"] = "redis://127.0.0.1:6379/0"
os.environ.setdefault("RAI_DB_PATH", ":memory:")
import slowapi
captured = {}
real = slowapi.Limiter
def factory(**kwargs):
    captured.update(kwargs)
    return real(**{k: v for k, v in kwargs.items() if k != "storage_uri"})
slowapi.Limiter = factory
import responsibleai.dashboard.app as m
assert captured.get("storage_uri") == "redis://127.0.0.1:6379/0"
assert m.limiter is not None
"""
    subprocess.run([sys.executable, "-c", script], check=True, capture_output=True)


class TestOidcSamlResolutionBatch12:
    async def test_resolve_oidc_returns_none_without_provider(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_oidc_provider", None)
        assert await _resolve_oidc_context("eyJhbGciOiJIUzI1NiJ9.e30.sig") is None
        monkeypatch.undo()

    async def test_resolve_oidc_maps_admin_role(self, engine) -> None:
        repo = OrgRepository(engine)
        org = await repo.create_org("OIDC Org", f"oidc-{uuid.uuid4().hex[:8]}")
        provider = MagicMock()
        provider.validate_token = AsyncMock(
            return_value=JWTClaims(sub="user-1", org_id=org.id, roles=["ADMIN"])
        )
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_oidc_provider", provider)
        monkeypatch.setattr(app_module, "_org_repo", repo)
        ctx = await _resolve_oidc_context("jwt-shaped-token")
        assert ctx is not None
        assert ctx.role == Role.ADMIN
        assert ctx.authentication_method == "oidc"
        monkeypatch.undo()

    async def test_resolve_saml_returns_none_without_config(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_saml_config", None)
        assert await _resolve_saml_context("wp_saml.fake.token") is None
        monkeypatch.undo()

    async def test_resolve_saml_invalid_session_token_returns_none(self) -> None:
        monkeypatch = pytest.MonkeyPatch()
        monkeypatch.setattr(app_module, "_saml_config", MagicMock())
        assert await _resolve_saml_context("wp_saml.not-a-valid-session") is None
        monkeypatch.undo()

    def test_rate_limit_key_without_bearer_uses_client_ip(self) -> None:
        req = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/api/health",
                "headers": [],
                "client": ("198.51.100.9", 4321),
            }
        )
        assert _get_rate_limit_key(req) == "198.51.100.9"


class TestMachineScopeBatch12:
    def test_governance_write_scope_cannot_read_policy(self) -> None:
        ctx = OrgContext(
            key_id="k1",
            role=Role.ADMIN,
            org_id="org-1",
            scopes=frozenset({"governance:write"}),
        )
        with pytest.raises(Exception) as exc:
            _enforce_machine_scope(_scope_request("GET", "/api/governance/policy"), ctx)
        assert getattr(exc.value, "status_code", None) == 403

    def test_governance_read_scope_cannot_post_workflow_rule(self) -> None:
        ctx = OrgContext(
            key_id="k1",
            role=Role.ADMIN,
            org_id="org-1",
            scopes=frozenset({"governance:read"}),
        )
        with pytest.raises(Exception) as exc:
            _enforce_machine_scope(_scope_request("POST", "/api/governance/workflow-rules"), ctx)
        assert "governance:write" in str(exc.value.detail)

    def test_agents_read_scope_cannot_register_agent(self) -> None:
        ctx = OrgContext(
            key_id="k1",
            role=Role.DEVELOPER,
            org_id="org-1",
            scopes=frozenset({"agents:read"}),
        )
        with pytest.raises(Exception) as exc:
            _enforce_machine_scope(_scope_request("POST", "/api/agents/register"), ctx)
        assert "agents:write" in str(exc.value.detail)

    def test_empty_scopes_skip_machine_scope_gate(self) -> None:
        ctx = OrgContext(key_id="k1", role=Role.VIEWER, org_id="org-1", scopes=frozenset())
        _enforce_machine_scope(_scope_request("POST", "/api/governance/tools/call"), ctx)


class TestDashboardGovernanceDenyBatch12:
    async def test_viewer_cannot_list_governance_approvals(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Approvals Viewer",
            slug=f"app-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/approvals", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_reorder_policy_rules(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Reorder Viewer",
            slug=f"reord-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/policy/reorder",
            json={"rule_ids": ["r1"]},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_list_workflow_rules(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="WF Viewer",
            slug=f"wf-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/workflow-rules", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_create_delegation(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Deleg Viewer",
            slug=f"del-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/delegations",
            json={"identity_id": "agent-1", "parent_identity_id": "human-1"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_list_upstream_tools(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Upstream Viewer",
            slug=f"up-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.get("/api/governance/upstream/tools", headers=_bearer(raw))
        assert r.status_code == 403

    async def test_viewer_cannot_register_upstream_server(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Upstream Reg Viewer",
            slug=f"upreg-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers",
            json={"name": "demo", "url": "https://example.com/mcp"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_create_intent_contract(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Intent Viewer",
            slug=f"intent-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/intent-contracts",
            json={"agent_id": "agent-1", "purpose": "test"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_viewer_cannot_issue_authority_passport(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Passport Viewer",
            slug=f"pass-v-{uuid.uuid4().hex[:8]}",
            key_name="viewer",
            role=Role.VIEWER,
        )
        r = await auth_client.post(
            "/api/governance/authority-passports",
            json={"subject_identity_id": "agent-1", "capabilities": []},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_analyst_cannot_resolve_approval(self, auth_client: AsyncClient) -> None:
        _org_id, _kid, raw = await seed_org_with_key(
            name="Resolve Analyst",
            slug=f"res-a-{uuid.uuid4().hex[:8]}",
            key_name="analyst",
            role=Role.ANALYST,
        )
        r = await auth_client.post(
            "/api/governance/approvals/fake-id/resolve",
            json={"decision": "APPROVE"},
            headers=_bearer(raw),
        )
        assert r.status_code == 403

    async def test_scoped_governance_write_cannot_get_evidence_bundle(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Bundle Scope",
            slug=f"bnd-sc-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped = await app_module._org_repo.create_key(
            org_id,
            "gov-write-only",
            Role.ADMIN,
            scopes=("governance:write",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.get("/api/governance/evidence/bundle", headers=_bearer(scoped))
        assert r.status_code == 403
        assert "evidence:read" in _http_message(r)

    async def test_scoped_governance_read_cannot_post_upstream_server(
        self, auth_client: AsyncClient
    ) -> None:
        org_id, _kid, _ = await seed_org_with_key(
            name="Upstream Scope",
            slug=f"up-sc-{uuid.uuid4().hex[:8]}",
            key_name="admin",
            role=Role.ADMIN,
        )
        _rec, scoped = await app_module._org_repo.create_key(
            org_id,
            "gov-read-only",
            Role.ADMIN,
            scopes=("governance:read",),
            internal_unverified_fixture=True,
        )
        r = await auth_client.post(
            "/api/governance/upstream/servers",
            json={"name": "demo", "url": "https://example.com/mcp"},
            headers=_bearer(scoped),
        )
        assert r.status_code == 403


# ── enterprise/service.py ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_iam_authorize_suspended_org_blocks_settings_update(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    repo = OrgRepository(engine)
    await repo.set_governance_status(org_id, GovernanceStatus.SUSPENDED)
    actor = _actor(owner, org_id, Role.OWNER)
    with pytest.raises(EnterpriseError) as exc:
        await iam.update_settings(actor, org_id, display_name="Renamed", settings=None)
    assert exc.value.code == ORG_SUSPENDED


@pytest.mark.asyncio
async def test_iam_authorize_suspended_org_allows_org_view(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    repo = OrgRepository(engine)
    await repo.set_governance_status(org_id, GovernanceStatus.SUSPENDED)
    actor = _actor(owner, org_id, Role.OWNER)
    await iam.authorize(actor, Permission.ORG_VIEW, org_id=org_id)


@pytest.mark.asyncio
async def test_iam_authorize_disabled_org_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    await iam.deactivate_organization(_actor(owner, org_id, Role.OWNER), org_id)
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(_actor(owner, org_id, Role.OWNER), Permission.ORG_VIEW, org_id=org_id)
    assert exc.value.code == ORG_DISABLED


@pytest.mark.asyncio
async def test_iam_list_environments_wrong_tenant_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    alice = await _user(engine, "alice@example.com")
    bob = await _user(engine, "bob@example.com")
    org_a = await _org(engine, alice)
    org_b = await _org(engine, bob)
    with pytest.raises(EnterpriseError) as exc:
        await iam.list_environments(_actor(alice, org_a, Role.OWNER), org_b)
    assert exc.value.code == WRONG_TENANT


@pytest.mark.asyncio
async def test_iam_create_workspace_disabled_user_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    async with engine.raw.begin() as conn:
        from sqlalchemy import update

        from responsibleai.db.engine import web_users

        await conn.execute(update(web_users).where(web_users.c.id == owner).values(disabled=1))
    with pytest.raises(EnterpriseError) as exc:
        await iam.create_workspace(
            actor_user_id=owner,
            name="Blocked",
            slug=f"blk-{uuid.uuid4().hex[:8]}",
            kind="INDIVIDUAL",
        )
    assert exc.value.code == FORBIDDEN


@pytest.mark.asyncio
async def test_iam_authorize_disabled_environment_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    envs = await iam.list_environments(_actor(owner, org_id, Role.OWNER), org_id)
    env_id = envs[0]["id"]
    async with engine.raw.begin() as conn:
        from sqlalchemy import update

        from responsibleai.db.engine import enterprise_environments

        await conn.execute(
            update(enterprise_environments)
            .where(enterprise_environments.c.id == env_id)
            .values(status="DISABLED")
        )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authorize(
            _actor(owner, org_id, Role.OWNER),
            Permission.ORG_VIEW,
            org_id=org_id,
            environment_id=env_id,
        )
    assert exc.value.code == ENVIRONMENT_DISABLED


@pytest.mark.asyncio
async def test_iam_revoke_last_owner_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    with pytest.raises(EnterpriseError) as exc:
        await iam.revoke_member(_actor(owner, org_id, Role.OWNER), org_id, user_id=owner)
    assert exc.value.code == LAST_OWNER


@pytest.mark.asyncio
async def test_iam_invite_replay_after_accept(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    guest = await _user(engine, "guest@example.com")
    org_id = await _org(engine, owner)
    actor = _actor(owner, org_id, Role.OWNER)
    _, token = await iam.invite_member(actor, org_id, email="guest@example.com", role=Role.VIEWER)
    await iam.accept_invitation(token=token, user_id=guest)
    with pytest.raises(EnterpriseError) as exc:
        await iam.accept_invitation(token=token, user_id=guest)
    assert exc.value.code == INVITE_REPLAY


@pytest.mark.asyncio
async def test_iam_create_api_key_denies_machine_actor(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    envs = await iam.list_environments(_actor(owner, org_id, Role.OWNER), org_id)
    env_id = envs[0]["id"]
    api_actor = Actor(
        actor_type="api_key",
        actor_id="key-1",
        user_id=owner,
        org_id=org_id,
        role=Role.DEVELOPER,
        membership_status="ACTIVE",
        environment_id=env_id,
    )
    with pytest.raises(EnterpriseError) as exc:
        await iam.create_api_key(
            api_actor,
            org_id,
            name="nested",
            environment_id=env_id,
            scopes=("governance:read",),
            expires_at=None,
        )
    assert exc.value.code == API_KEY_ISSUANCE_NOT_ALLOWED


@pytest.mark.asyncio
async def test_iam_authenticate_api_key_wrong_org_denied(engine) -> None:
    iam = EnterpriseIAM(engine)
    owner = await _user(engine)
    org_id = await _org(engine, owner)
    repo = OrgRepository(engine)
    _record, secret = await repo.create_key(
        org_id, "batch12", Role.ADMIN, internal_unverified_fixture=True
    )
    with pytest.raises(EnterpriseError) as exc:
        await iam.authenticate_api_key(secret, expected_org_id=str(uuid.uuid4()))
    assert exc.value.code == WRONG_TENANT


# ── enterprise/security/service.py ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_security_load_session_unknown_token(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.load_session("not-a-real-session-token")
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_security_authenticate_password_wrong_password(engine) -> None:
    svc = await _svc(engine)
    await _user(engine)
    assert await svc.authenticate_password("human@example.com", "wrong-password-99") is None


@pytest.mark.asyncio
async def test_security_begin_webauthn_register_requires_user(engine) -> None:
    svc = await _svc(engine)
    with pytest.raises(EnterpriseError) as exc:
        await svc.begin_webauthn(user_id=None, session_id=None, ceremony="register", org_id=None)
    assert exc.value.code == UNAUTHENTICATED


@pytest.mark.asyncio
async def test_security_issue_recovery_codes_requires_step_up(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    _, _, session = await svc.issue_session(
        user_id=user_id, methods=(AuthMethod.PASSKEY_UV,), ip_label=None, user_agent=None
    )
    with pytest.raises(EnterpriseError) as exc:
        await svc.issue_recovery_codes(user_id, session=session, grant=None)
    assert exc.value.code == STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_security_consume_recovery_code_invalid(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    with pytest.raises(EnterpriseError):
        await svc.consume_recovery_code(user_id, "not-a-valid-code")


@pytest.mark.asyncio
async def test_security_revoke_session_unknown_id_is_idempotent(engine) -> None:
    svc = await _svc(engine)
    user_id = await _user(engine)
    await svc.revoke_session(user_id=user_id, session_id=str(uuid.uuid4()))


# ── isolation/container_backend.py ───────────────────────────────────────────


def test_is_available_true_for_executable_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = tmp_path / "docker"
    fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(return_value=subprocess.CompletedProcess(args=[], returncode=0)),
    )
    assert DockerContainerBackend(docker_cmd=str(fake)).is_available() is True


def test_remove_containers_tolerates_rm_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")

    def fake_run(cmd, **_k):
        if "rm" in cmd:
            raise OSError("rm failed")
        return subprocess.CompletedProcess(args=cmd, returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.time.monotonic",
        lambda: 1000.0,
    )
    backend._remove_containers(["c1"], stable_seconds=0, wait_seconds=0.01)


@pytest.mark.asyncio
async def test_execute_mock_success_path(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)

    class _Proc:
        returncode = 0

        async def communicate(self, input=None):
            return (b'{"status":"success","result":{"echo":true}}', b"")

        async def wait(self):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=_Proc()))
    monkeypatch.setattr(
        backend,
        "_remove_containers_uninterruptible",
        AsyncMock(),
    )
    req = IsolatedExecutionRequest(
        action_id="act-ok",
        organization_id="org-1",
        action_type="noop",
        arguments={},
        workspace_files={
            "runner.py": 'import json; print(json.dumps({"status":"success","result":{}}))'
        },
    )
    outcome = await backend.execute(req)
    assert outcome.result_payload == {"echo": True}
    assert outcome.violation is None


@pytest.mark.asyncio
async def test_execute_mock_runner_error_status(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)

    class _Proc:
        returncode = 0

        async def communicate(self, input=None):
            return (b'{"status":"error","error":"runner failed"}', b"")

        async def wait(self):
            return 0

        def kill(self):
            pass

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=_Proc()))
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", AsyncMock())
    req = IsolatedExecutionRequest(
        action_id="act-err",
        organization_id="org-1",
        action_type="noop",
        arguments={},
    )
    outcome = await backend.execute(req)
    assert outcome.exit_code == 1
    assert outcome.violation == "runner failed"


@pytest.mark.asyncio
async def test_execute_mock_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)

    class _Proc:
        returncode = 127

        async def communicate(self, input=None):
            return (b"", b"command not found")

        async def wait(self):
            return 127

        def kill(self):
            pass

    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=_Proc()))
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", AsyncMock())
    req = IsolatedExecutionRequest(
        action_id="act-exit",
        organization_id="org-1",
        action_type="noop",
        arguments={},
    )
    outcome = await backend.execute(req)
    assert outcome.exit_code == 127
    assert "exited with code" in (outcome.violation or "")


@pytest.mark.asyncio
async def test_execute_mock_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)

    class _Proc:
        returncode = None

        async def communicate(self, input=None):
            raise TimeoutError

        async def wait(self):
            return None

        def kill(self):
            self.returncode = -9

    proc = _Proc()
    monkeypatch.setattr(asyncio, "create_subprocess_exec", AsyncMock(return_value=proc))
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", AsyncMock())
    profile = IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.01))
    req = IsolatedExecutionRequest(
        action_id="act-timeout",
        organization_id="org-1",
        action_type="noop",
        arguments={},
        profile=profile,
    )
    outcome = await backend.execute(req)
    assert outcome.timed_out is True
    assert outcome.exit_code == -9


@pytest.mark.asyncio
async def test_execute_rejects_egress_network_policy() -> None:
    backend = DockerContainerBackend()
    profile = IsolationProfile(network_policy=NetworkPolicy.ALLOWLISTED_EGRESS)
    req = IsolatedExecutionRequest(
        action_id="act-net",
        organization_id="org-1",
        action_type="noop",
        arguments={},
        profile=profile,
    )
    with patch.object(backend, "is_available", return_value=True):
        with pytest.raises(IsolationPolicyViolationError):
            await backend.execute(req)


@pytest.mark.asyncio
async def test_execute_unavailable_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend()
    monkeypatch.setattr(backend, "is_available", lambda: False)
    req = IsolatedExecutionRequest(
        action_id="act-unavail",
        organization_id="org-1",
        action_type="noop",
        arguments={},
    )
    with pytest.raises(IsolationBackendUnavailableError):
        await backend.execute(req)
