"""Tests for the MCP Upstream Gateway (v3 authority-layer work, Task
#139) -- the largest gap flagged across this session's reports:
WhitePact governed its own 27 in-process tools but had no way to proxy
a governed call to a third-party MCP server.

Covers: the SSRF guard on registration/dispatch, the org-scoped
registry, the executor's authorization-binding invariants (same shape
as test_executor_bypass_invariant.py's InternalToolExecutor coverage),
risk-tier defaulting to HIGH, and a full REST round trip that actually
proxies a call to a real (in-process, ASGI-transported -- no real
sockets) second MCP server.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import httpx
import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import UpstreamServerNotFoundError, UpstreamServerRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    ExecutionAuthorization,
    authorize_execution,
)
from responsibleai.governance.models import DecisionResult
from responsibleai.governance.risk import RiskTier, classify_action_risk
from responsibleai.governance.upstream import (
    UnsafeUpstreamServerURLError,
    validate_upstream_server_url,
)
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    MalformedUpstreamTargetError,
    UpstreamMCPExecutor,
    UpstreamServerNotAvailableError,
    build_upstream_target,
    parse_upstream_target,
)

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


def _fake_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same pattern as test_webhooks.py's fixture of the same purpose --
    validate_upstream_server_url delegates to validate_webhook_url,
    which does a real socket.getaddrinfo() lookup; test hostnames
    aren't real DNS records."""
    def _fake_getaddrinfo(host, *args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)


class TestValidateUpstreamServerURL:
    def test_public_looking_host_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_public_dns(monkeypatch)
        validate_upstream_server_url("https://upstream.example.com/mcp")  # no raise

    def test_loopback_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("127.0.0.1", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)
        with pytest.raises(UnsafeUpstreamServerURLError):
            validate_upstream_server_url("http://internal-looking-host/mcp")

    def test_private_network_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("10.0.0.5", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)
        with pytest.raises(UnsafeUpstreamServerURLError):
            validate_upstream_server_url("http://vpc-internal/mcp")

    def test_cloud_metadata_address_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("169.254.169.254", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)
        with pytest.raises(UnsafeUpstreamServerURLError):
            validate_upstream_server_url("http://metadata-lookalike/mcp")

    def test_unresolvable_host_rejected(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import socket

        def _raise(*args, **kwargs):
            raise socket.gaierror("no such host")

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _raise)
        with pytest.raises(UnsafeUpstreamServerURLError):
            validate_upstream_server_url("http://does-not-resolve.invalid/mcp")


class TestBuildParseUpstreamTarget:
    def test_round_trip(self) -> None:
        target = build_upstream_target("srv-1", "remote_tool")
        assert parse_upstream_target(target) == ("srv-1", "remote_tool")

    def test_malformed_target_raises(self) -> None:
        with pytest.raises(MalformedUpstreamTargetError):
            parse_upstream_target("not-a-valid-target")


class TestUpstreamServerRepository:
    @pytest.fixture()
    async def engine(self):
        e = create_engine(":memory:")
        await e.init()
        yield e
        await e.close()

    @pytest.fixture()
    def repo(self, engine):
        return UpstreamServerRepository(engine)

    async def test_register_rejects_unsafe_url(self, repo: UpstreamServerRepository, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("127.0.0.1", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)
        with pytest.raises(UnsafeUpstreamServerURLError):
            await repo.register("org-1", "evil-server", "http://internal/mcp")

    async def test_register_and_get(self, repo: UpstreamServerRepository, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_public_dns(monkeypatch)
        server = await repo.register("org-1", "partner-tools", "https://partner.example.com/mcp")
        fetched = await repo.get(server.server_id)
        assert fetched is not None
        assert fetched.name == "partner-tools"
        assert fetched.org_id == "org-1"
        assert fetched.enabled is True

    async def test_list_scoped_to_org(self, repo: UpstreamServerRepository, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_public_dns(monkeypatch)
        await repo.register("org-a", "a-server", "https://a.example.com/mcp")
        await repo.register("org-b", "b-server", "https://b.example.com/mcp")
        org_a_servers = await repo.list_for_org("org-a")
        assert len(org_a_servers) == 1
        assert org_a_servers[0].name == "a-server"

    async def test_remove_unknown_raises(self, repo: UpstreamServerRepository) -> None:
        with pytest.raises(UpstreamServerNotFoundError):
            await repo.remove("org-1", "does-not-exist")

    async def test_set_enabled_toggles(self, repo: UpstreamServerRepository, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_public_dns(monkeypatch)
        server = await repo.register("org-1", "toggle-server", "https://toggle.example.com/mcp")
        disabled = await repo.set_enabled("org-1", server.server_id, False)
        assert disabled.enabled is False
        enabled = await repo.set_enabled("org-1", server.server_id, True)
        assert enabled.enabled is True


class TestRiskTierDefaultsHighForUpstreamCalls:
    def test_upstream_action_type_is_high_regardless_of_target(self) -> None:
        assert classify_action_risk(ACTION_TYPE, build_upstream_target("srv-1", "anything")) == RiskTier.HIGH

    def test_higher_than_an_unrecognized_internal_action_type(self) -> None:
        """The whole point of the HIGH default: an upstream call is
        treated MORE cautiously than a merely-unrecognized internal
        action_type (which defaults to MEDIUM)."""
        assert classify_action_risk("some_future_internal_action", "x") == RiskTier.MEDIUM
        assert classify_action_risk(ACTION_TYPE, "srv::tool") == RiskTier.HIGH


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), organization_id=org_id, framework="upstream-gateway")


def _upstream_action(server_id: str = "srv-1", tool_name: str = "remote_tool", org_id: str = "org-1") -> ActionRequest:
    return ActionRequest(
        agent=_agent(org_id), action_type=ACTION_TYPE, target=build_upstream_target(server_id, tool_name),
    )


def _allow_decision(action_id: str) -> DecisionResult:
    return DecisionResult(decision=GovernanceDecision.ALLOW, action_id=action_id, risk_tier=RiskTier.HIGH)


class _FakeRegistry:
    """Minimal stand-in for UpstreamServerRepository -- avoids a real DB
    for pure executor-invariant tests."""

    def __init__(self, servers: dict) -> None:
        self._servers = servers

    async def get(self, server_id: str):
        return self._servers.get(server_id)


class _FakeServer:
    def __init__(self, org_id: str, url: str, enabled: bool = True, auth_token: str | None = None) -> None:
        self.org_id = org_id
        self.url = url
        self.enabled = enabled
        self.auth_token = auth_token


class TestUpstreamExecutorInvariants:
    """Mirrors test_executor_bypass_invariant.py's coverage of
    InternalToolExecutor -- UpstreamMCPExecutor must refuse to execute
    without a valid, matching, unexpired, unconsumed authorization,
    exactly the same way."""

    async def test_mismatched_action_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_public_dns(monkeypatch)
        registry = _FakeRegistry({"srv-1": _FakeServer("org-1", "https://partner.example.com/mcp")})
        original = _upstream_action(tool_name="tool_a")
        authorization = authorize_execution(_allow_decision(original.action_id), original)
        tampered = _upstream_action(tool_name="tool_b")

        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(AuthorizationActionMismatchError):
            await executor.execute(authorization, tampered)

    async def test_expired_authorization_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_public_dns(monkeypatch)
        registry = _FakeRegistry({"srv-1": _FakeServer("org-1", "https://partner.example.com/mcp")})
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        authorization.expires_at = datetime.now(UTC) - timedelta(seconds=1)

        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(AuthorizationExpiredError):
            await executor.execute(authorization, action)

    async def test_wrong_organization_is_refused(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _fake_public_dns(monkeypatch)
        registry = _FakeRegistry({"srv-1": _FakeServer("org-1", "https://partner.example.com/mcp")})
        action = _upstream_action(org_id="org-1")
        authorization = authorize_execution(_allow_decision(action.action_id), action)

        cross_org_action = _upstream_action(org_id="org-2")
        cross_org_action.arguments = action.arguments

        executor = UpstreamMCPExecutor(registry)
        with pytest.raises((AuthorizationOrganizationMismatchError, AuthorizationActionMismatchError)):
            await executor.execute(authorization, cross_org_action)

    async def test_forged_authorization_with_correct_digest_still_bound_to_org(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from responsibleai.governance.approval import compute_action_digest

        _fake_public_dns(monkeypatch)
        registry = _FakeRegistry({"srv-1": _FakeServer("org-1", "https://partner.example.com/mcp")})
        action = _upstream_action(org_id="org-1")
        forged = ExecutionAuthorization(
            action_digest=compute_action_digest(action),
            organization_id="org-attacker",
            decision=GovernanceDecision.ALLOW,
        )
        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(AuthorizationOrganizationMismatchError):
            await executor.execute(forged, action)

    async def test_unregistered_server_refused(self) -> None:
        registry = _FakeRegistry({})
        action = _upstream_action(server_id="does-not-exist")
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(UpstreamServerNotAvailableError):
            await executor.execute(authorization, action)

    async def test_disabled_server_refused(self) -> None:
        registry = _FakeRegistry({"srv-1": _FakeServer("org-1", "https://partner.example.com/mcp", enabled=False)})
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(UpstreamServerNotAvailableError):
            await executor.execute(authorization, action)

    async def test_other_orgs_server_refused(self) -> None:
        registry = _FakeRegistry({"srv-1": _FakeServer("org-OTHER", "https://partner.example.com/mcp")})
        action = _upstream_action(org_id="org-1")
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(UpstreamServerNotAvailableError):
            await executor.execute(authorization, action)

    async def test_replay_is_refused_once_a_valid_call_actually_executes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The core invariant, proven against a REAL second in-process
        MCP server (ASGI-transported, no real socket) -- a second
        execute() call with the same authorization must fail even
        though the first one genuinely dispatched over the wire.

        _build_http_app() authenticates against its OWN OrgRepository
        (not the dashboard's flat settings.api_keys), so a real org+key
        must exist in the same DB engine it's built against -- same
        create_engine substitution trick test_mcp_governance_dispatch.py
        already uses."""
        _fake_public_dns(monkeypatch)
        import responsibleai.db as db_module
        from responsibleai.db import OrgRepository, create_engine
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.rbac.models import Plan, Role

        engine = create_engine(":memory:")
        await engine.init()
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
        org_repo = OrgRepository(engine)
        upstream_org = await org_repo.create_org("Upstream Provider Co", "upstream-provider-co", plan=Plan.ENTERPRISE)
        _key_rec, upstream_raw_key = await org_repo.create_key(upstream_org.id, "upstream-key", role=Role.ANALYST)

        upstream_app = _build_http_app()

        def _http_client_factory():
            return httpx.AsyncClient(transport=ASGITransport(app=upstream_app), base_url="http://upstream-test")

        registry = _FakeRegistry({
            "srv-1": _FakeServer("org-1", "http://upstream-test/mcp", auth_token=upstream_raw_key),
        })
        executor = UpstreamMCPExecutor(registry, http_client_factory=_http_client_factory)

        action = _upstream_action(tool_name="rai_health")
        authorization = authorize_execution(_allow_decision(action.action_id), action)

        async with LifespanManager(upstream_app):
            first = await executor.execute(authorization, action)
            assert first["is_error"] is False

            with pytest.raises(AuthorizationAlreadyConsumedError):
                await executor.execute(authorization, action)


@pytest.fixture(autouse=True)
def _auth_enabled_with_bootstrap_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["bootstrap-test-key"])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture(autouse=True)
def _reset_rate_limits():
    limiter.reset()
    yield


@pytest.fixture()
async def client():
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as c:
            yield c


@pytest.fixture()
async def org_and_admin_key(client: AsyncClient):
    r = await client.post(
        "/api/orgs", json={"name": "Upstream Test Co", "slug": "upstream-test-co"}, headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    r = await client.post(
        f"/api/orgs/{org_id}/keys", json={"name": "admin-key", "role": "ADMIN"}, headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


class TestUpstreamRegistryRESTEndpoints:
    async def test_register_requires_admin(self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch) -> None:
        org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        r = await client.post(
            f"/api/orgs/{org_id}/keys", json={"name": "analyst-key", "role": "ANALYST"}, headers=BOOTSTRAP_AUTH,
        )
        analyst_key = r.json()["key"]
        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "partner", "url": "https://partner.example.com/mcp"},
            headers={"Authorization": f"Bearer {analyst_key}"},
        )
        assert r.status_code == 403

    async def test_register_rejects_unsafe_url(self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch) -> None:
        _org_id, admin_key = org_and_admin_key

        def _fake_getaddrinfo(host, *args, **kwargs):
            return [(2, 1, 6, "", ("127.0.0.1", 0))]

        monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)
        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "evil", "url": "http://internal-service/mcp"},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 422

    async def test_register_list_remove_round_trip(
        self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}

        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "partner-tools", "url": "https://partner.example.com/mcp"},
            headers=headers,
        )
        assert r.status_code == 201
        server_id = r.json()["server_id"]

        r = await client.get("/api/governance/upstream/servers", headers=headers)
        assert r.status_code == 200
        assert any(s["server_id"] == server_id for s in r.json()["servers"])

        r = await client.delete(f"/api/governance/upstream/servers/{server_id}", headers=headers)
        assert r.status_code == 200

        r = await client.get("/api/governance/upstream/servers", headers=headers)
        assert r.json()["servers"] == []


class TestUpstreamCallEndToEnd:
    async def test_call_to_unregistered_server_is_denied(self, client: AsyncClient, org_and_admin_key) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.post(
            "/api/governance/upstream/servers/does-not-exist/call",
            json={"tool_name": "anything", "arguments": {}},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 200  # governance-blocked, not an HTTP error
        body = r.json()
        assert body["error"] == "governance_denied"
        assert any("UNAPPROVED_MCP_SERVER" in code for code in body["reason_codes"])

    async def test_call_to_disabled_server_is_denied(
        self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}
        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "disabled-server", "url": "https://disabled.example.com/mcp"},
            headers=headers,
        )
        server_id = r.json()["server_id"]

        from responsibleai.dashboard.app import _upstream_registry

        await _upstream_registry.set_enabled(org_id, server_id, False)

        r = await client.post(
            f"/api/governance/upstream/servers/{server_id}/call",
            json={"tool_name": "anything", "arguments": {}},
            headers=headers,
        )
        body = r.json()
        assert body["error"] == "governance_denied"

    async def test_full_round_trip_actually_proxies_the_call(
        self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Registers a server, monkeypatches UpstreamMCPExecutor's
        default HTTP client factory to point at a REAL second in-process
        MCP server (ASGI-transported) instead of a real socket, then
        proves the call actually executed there -- not just that
        governance said ALLOW. That second server is a real, separate
        _build_http_app() instance with its own OrgRepository (it
        authenticates callers against its own DB, not the dashboard
        app's settings.api_keys), so it needs a real seeded org+key too
        -- create_engine is patched only after the dashboard app's own
        engine already exists (from the `client` fixture's startup), so
        this doesn't disturb it."""
        org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}

        import responsibleai.db as db_module
        from responsibleai.db import OrgRepository, create_engine
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.rbac.models import Plan, Role

        upstream_engine = create_engine(":memory:")
        await upstream_engine.init()
        upstream_org_repo = OrgRepository(upstream_engine)
        upstream_org = await upstream_org_repo.create_org(
            "Upstream Provider Co", "upstream-provider-co-2", plan=Plan.ENTERPRISE,
        )
        _key_rec, upstream_raw_key = await upstream_org_repo.create_key(
            upstream_org.id, "upstream-key", role=Role.ANALYST,
        )

        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "real-upstream", "url": "http://upstream-test/mcp", "auth_token": upstream_raw_key},
            headers=headers,
        )
        assert r.status_code == 201
        server_id = r.json()["server_id"]

        monkeypatch.setattr(db_module, "create_engine", lambda _url: upstream_engine)
        upstream_app = _build_http_app()

        def _fake_factory():
            return httpx.AsyncClient(transport=ASGITransport(app=upstream_app), base_url="http://upstream-test")

        monkeypatch.setattr(
            "responsibleai.governance.upstream_executor._default_http_client_factory", _fake_factory,
        )

        async with LifespanManager(upstream_app):
            r = await client.post(
                f"/api/governance/upstream/servers/{server_id}/call",
                json={"tool_name": "rai_health", "arguments": {}},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["server_id"] == server_id
        assert body["result"]["is_error"] is False
        assert any("ok" in c or "status" in c for c in body["result"]["content"])

        from responsibleai.dashboard.app import _db_engine
        from responsibleai.db import EvidenceRepository

        records = await EvidenceRepository(_db_engine).list_for_org(org_id, decision="ALLOW")
        matching = [r for r in records if r.action_type == ACTION_TYPE]
        assert matching
        assert matching[0].risk_tier == "HIGH"

    async def test_cross_org_server_id_denied(self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch) -> None:
        _org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)

        r = await client.post(
            "/api/orgs", json={"name": "Other Upstream Co", "slug": "other-upstream-co"}, headers=BOOTSTRAP_AUTH,
        )
        other_org_id = r.json()["id"]
        r = await client.post(
            f"/api/orgs/{other_org_id}/keys", json={"name": "other-admin", "role": "ADMIN"}, headers=BOOTSTRAP_AUTH,
        )
        other_admin_key = r.json()["key"]
        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "other-org-server", "url": "https://other.example.com/mcp"},
            headers={"Authorization": f"Bearer {other_admin_key}"},
        )
        other_server_id = r.json()["server_id"]

        r = await client.post(
            f"/api/governance/upstream/servers/{other_server_id}/call",
            json={"tool_name": "anything", "arguments": {}},
            headers={"Authorization": f"Bearer {admin_key}"},
        )
        body = r.json()
        assert body["error"] == "governance_denied"
        assert any("UNAPPROVED_MCP_SERVER" in code for code in body["reason_codes"])


class TestResumeApprovalWorksForUpstreamOriginatedApprovals:
    """mcp/governance_integration.py's resume_approval() was made
    executor-agnostic specifically so a REQUIRE_APPROVAL queued by
    apply_upstream_governance() (e.g. a low-trust or policy-flagged
    proxied call) can also be resumed later, via UpstreamMCPExecutor
    rather than the hardcoded InternalToolExecutor -- this proves that
    wiring, not just that it compiles."""

    async def test_resume_without_upstream_registry_raises(self) -> None:
        from datetime import datetime as _dt

        from responsibleai.db import ApprovalRepository, EvidenceRepository, create_engine
        from responsibleai.governance.approval import ApprovalRequest, ApprovalStatus
        from responsibleai.mcp.governance_integration import resume_approval

        engine = create_engine(":memory:")
        await engine.init()
        approval_repo = ApprovalRepository(engine)
        approval = await approval_repo.create(ApprovalRequest(
            action_id="a1", action_type=ACTION_TYPE, target=build_upstream_target("srv-1", "remote_tool"),
            reason_codes=[], requested_at=_dt.now(UTC),
            action_digest="x" * 64, organization_id="org-1", requested_by="k1",
            arguments={"x": 1},
        ))
        await approval_repo.resolve(approval.approval_id, resolved_by="human-1", outcome=ApprovalStatus.APPROVED)

        with pytest.raises(ValueError, match="upstream_registry"):
            await resume_approval(
                approval.approval_id,
                approval_repo=approval_repo,
                evidence_repo=EvidenceRepository(engine),
                org_id="org-1",
            )
        await engine.close()


class TestUpstreamToolDiscovery:
    """governance/upstream_discovery.py (Task #144, bounded scope --
    discovery/aggregation only, deliberately not live MCP protocol
    tools/list injection, see that module's docstring)."""

    async def test_discover_returns_real_tools_from_a_real_second_server(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from responsibleai.db import OrgRepository, create_engine
        from responsibleai.governance.upstream_discovery import discover_upstream_tools
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.rbac.models import Plan, Role

        _fake_public_dns(monkeypatch)

        upstream_engine = create_engine(":memory:")
        await upstream_engine.init()
        upstream_org_repo = OrgRepository(upstream_engine)
        upstream_org = await upstream_org_repo.create_org(
            "Discovery Provider Co", "discovery-provider-co", plan=Plan.ENTERPRISE,
        )
        _key_rec, upstream_raw_key = await upstream_org_repo.create_key(
            upstream_org.id, "discovery-key", role=Role.ANALYST,
        )

        import responsibleai.db as db_module

        monkeypatch.setattr(db_module, "create_engine", lambda _url: upstream_engine)
        upstream_app = _build_http_app()

        def _http_client_factory():
            return httpx.AsyncClient(transport=ASGITransport(app=upstream_app), base_url="http://upstream-test")

        # _FakeRegistry (used elsewhere in this file) only implements
        # get(); discover_upstream_tools also needs list_for_org(), so
        # this uses the real repository against a throwaway engine.
        real_engine = create_engine(":memory:")
        await real_engine.init()
        real_registry = UpstreamServerRepository(real_engine)
        await real_registry.register(
            "org-1", "real-upstream", "http://upstream-test/mcp", auth_token=upstream_raw_key,
        )

        async with LifespanManager(upstream_app):
            tools, errors = await discover_upstream_tools(
                real_registry, "org-1", http_client_factory=_http_client_factory,
            )

        assert errors == {}
        assert len(tools) > 0
        assert any(t.tool_name == "rai_health" for t in tools)
        namespaced = next(t for t in tools if t.tool_name == "rai_health")
        assert namespaced.namespaced_name.startswith(namespaced.server_id)
        assert "::" in namespaced.namespaced_name

        await real_engine.close()
        await upstream_engine.close()

    async def test_unreachable_server_reports_error_not_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.db import create_engine
        from responsibleai.governance.upstream_discovery import discover_upstream_tools

        _fake_public_dns(monkeypatch)
        engine = create_engine(":memory:")
        await engine.init()
        registry = UpstreamServerRepository(engine)
        await registry.register("org-1", "dead-server", "https://dead.example.com/mcp")

        def _broken_factory():
            return httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))

        tools, errors = await discover_upstream_tools(registry, "org-1", http_client_factory=_broken_factory)
        assert tools == []
        assert len(errors) == 1
        await engine.close()

    async def test_rest_endpoint_returns_discovered_tools(
        self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}

        import responsibleai.db as db_module
        from responsibleai.db import OrgRepository, create_engine
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.rbac.models import Plan, Role

        upstream_engine = create_engine(":memory:")
        await upstream_engine.init()
        upstream_org_repo = OrgRepository(upstream_engine)
        upstream_org = await upstream_org_repo.create_org(
            "REST Discovery Co", "rest-discovery-co", plan=Plan.ENTERPRISE,
        )
        _key_rec, upstream_raw_key = await upstream_org_repo.create_key(
            upstream_org.id, "rest-discovery-key", role=Role.ANALYST,
        )

        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "rest-upstream", "url": "http://upstream-test/mcp", "auth_token": upstream_raw_key},
            headers=headers,
        )
        assert r.status_code == 201

        monkeypatch.setattr(db_module, "create_engine", lambda _url: upstream_engine)
        upstream_app = _build_http_app()

        def _fake_factory():
            return httpx.AsyncClient(transport=ASGITransport(app=upstream_app), base_url="http://upstream-test")

        monkeypatch.setattr(
            "responsibleai.governance.upstream_discovery._default_http_client_factory", _fake_factory,
        )

        async with LifespanManager(upstream_app):
            r = await client.get("/api/governance/upstream/tools", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["errors"] == {}
        assert any(t["tool_name"] == "rai_health" for t in body["tools"])

    async def test_rest_endpoint_no_servers_returns_empty(self, client: AsyncClient, org_and_admin_key) -> None:
        _org_id, admin_key = org_and_admin_key
        r = await client.get(
            "/api/governance/upstream/tools", headers={"Authorization": f"Bearer {admin_key}"},
        )
        assert r.status_code == 200
        assert r.json() == {"tools": [], "errors": {}}
