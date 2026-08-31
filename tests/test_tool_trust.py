# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for the Tool Trust Network (Authority Everywhere Phase 8) and
Execution Permit v2's target-fingerprint drift detection (Phase 9).

Covers: the deterministic scoring math in `governance/tool_trust.py`,
`ToolTrustRepository`'s persistence, the BLOCKED-tier gate in
`mcp/upstream_dispatch.py` (denied before governance is even consulted,
mirroring `UNAPPROVED_MCP_SERVER`'s own shape), the executor-level
fingerprint-drift invariant in `governance/upstream_executor.py`, and a
REST round trip that scans a real (in-process, ASGI-transported)
upstream server and persists the resulting score.
"""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import create_engine
from responsibleai.db.tool_trust_repository import ToolTrustRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorizationTargetDriftError,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.execution import authorize_execution
from responsibleai.governance.models import DecisionResult
from responsibleai.governance.risk import RiskTier
from responsibleai.governance.tool_trust import (
    ToolTrustTier,
    apply_admin_override,
    compute_trust_score,
    unscanned_score,
)
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    UpstreamMCPExecutor,
    build_upstream_target,
    compute_upstream_target_fingerprint,
)
from responsibleai.supplychain.models import Finding, SupplyChainReport, Verdict

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


def _fake_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_getaddrinfo(host, *args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)


def _clean_report() -> SupplyChainReport:
    return SupplyChainReport(
        server_name="s",
        findings=[
            Finding(check="confusable_characters", verdict=Verdict.VERIFIED_FACT, summary="none"),
            Finding(check="tool_description_scan", verdict=Verdict.INFERRED_SIGNAL, summary="none"),
        ],
    )


def _typosquat_report() -> SupplyChainReport:
    return SupplyChainReport(
        server_name="s",
        findings=[
            Finding(
                check="confusable_characters",
                verdict=Verdict.VERIFIED_FACT,
                summary="hit",
                detail={"matches": {"server_name": [{"char": "а"}]}},
            ),
            Finding(check="tool_description_scan", verdict=Verdict.INFERRED_SIGNAL, summary="none"),
        ],
    )


def _incident_report() -> SupplyChainReport:
    return SupplyChainReport(
        server_name="s",
        findings=[
            Finding(check="confusable_characters", verdict=Verdict.VERIFIED_FACT, summary="none"),
            Finding(check="tool_description_scan", verdict=Verdict.INFERRED_SIGNAL, summary="none"),
            Finding(
                check="known_incidents",
                verdict=Verdict.VERIFIED_FACT,
                summary="filed",
                detail={"incidents": [{"id": "inc-1"}]},
            ),
        ],
    )


class TestComputeTrustScore:
    def test_clean_scan_stays_at_baseline_provisional(self) -> None:
        score = compute_trust_score("srv-1", "org-1", _clean_report())
        assert score.score == 70
        assert score.tier is ToolTrustTier.PROVISIONAL
        assert score.has_been_scanned is True

    def test_confusable_characters_are_a_large_penalty(self) -> None:
        score = compute_trust_score("srv-1", "org-1", _typosquat_report())
        assert score.score == 30
        assert score.tier is ToolTrustTier.UNTRUSTED

    def test_known_incident_drops_below_untrusted_floor(self) -> None:
        score = compute_trust_score("srv-1", "org-1", _incident_report(), incident_count=1)
        assert score.score == 20
        assert score.tier is ToolTrustTier.UNTRUSTED
        assert score.incident_count == 1

    def test_confusable_plus_incident_reaches_blocked(self) -> None:
        combined = SupplyChainReport(
            server_name="s",
            findings=[
                *_typosquat_report().findings,
                Finding(
                    check="known_incidents",
                    verdict=Verdict.VERIFIED_FACT,
                    summary="filed",
                    detail={"incidents": [{"id": "inc-1"}]},
                ),
            ],
        )
        score = compute_trust_score("srv-1", "org-1", combined)
        assert score.score == 0
        assert score.tier is ToolTrustTier.BLOCKED

    def test_flagged_description_penalty_is_capped(self) -> None:
        many_flagged = SupplyChainReport(
            server_name="s",
            findings=[
                Finding(
                    check="confusable_characters", verdict=Verdict.VERIFIED_FACT, summary="none"
                ),
                Finding(
                    check="tool_description_scan",
                    verdict=Verdict.INFERRED_SIGNAL,
                    summary="flagged",
                    detail={"flagged_tools": {f"tool_{i}": ["x"] for i in range(10)}},
                ),
            ],
        )
        score = compute_trust_score("srv-1", "org-1", many_flagged)
        # 10 flagged tools * 15 would be 150, capped at 45 -> 70 - 45 = 25
        assert score.score == 25

    def test_score_never_goes_negative(self) -> None:
        worst = SupplyChainReport(
            server_name="s",
            findings=[
                *_typosquat_report().findings,
                Finding(
                    check="known_incidents",
                    verdict=Verdict.VERIFIED_FACT,
                    summary="filed",
                    detail={"incidents": [{"id": "inc-1"}, {"id": "inc-2"}]},
                ),
            ],
        )
        score = compute_trust_score("srv-1", "org-1", worst)
        assert score.score == 0


class TestUnscannedScore:
    def test_unscanned_is_provisional_and_capped_below_trusted(self) -> None:
        score = unscanned_score("srv-1", "org-1")
        assert score.has_been_scanned is False
        assert score.tier is ToolTrustTier.PROVISIONAL
        assert score.score < 80


class TestApplyAdminOverride:
    def test_override_to_blocked_zeroes_score_and_records_who_and_why(self) -> None:
        current = unscanned_score("srv-1", "org-1")
        overridden = apply_admin_override(
            current, ToolTrustTier.BLOCKED, admin_id="admin-1", reason="reported by partner"
        )
        assert overridden.score == 0
        assert overridden.tier is ToolTrustTier.BLOCKED
        assert overridden.admin_override_by == "admin-1"
        assert overridden.admin_override_reason == "reported by partner"
        assert overridden.admin_override_at is not None

    def test_override_to_trusted_ahead_of_a_scan(self) -> None:
        current = compute_trust_score("srv-1", "org-1", _clean_report())
        assert current.tier is ToolTrustTier.PROVISIONAL
        overridden = apply_admin_override(
            current, ToolTrustTier.TRUSTED, admin_id="admin-1", reason="manually vetted"
        )
        assert overridden.tier is ToolTrustTier.TRUSTED
        assert overridden.score == 100

    def test_override_preserves_scan_history(self) -> None:
        current = compute_trust_score("srv-1", "org-1", _clean_report())
        overridden = apply_admin_override(
            current, ToolTrustTier.BLOCKED, admin_id="admin-1", reason="x"
        )
        assert overridden.scan_report_id == current.scan_report_id
        assert overridden.has_been_scanned is True


class TestToolTrustRepository:
    @pytest.fixture()
    async def engine(self):
        e = create_engine(":memory:")
        await e.init()
        yield e
        await e.close()

    @pytest.fixture()
    def repo(self, engine):
        return ToolTrustRepository(engine)

    async def test_get_missing_returns_none(self, repo: ToolTrustRepository) -> None:
        assert await repo.get("does-not-exist") is None

    async def test_upsert_then_get_round_trips(self, repo: ToolTrustRepository) -> None:
        score = compute_trust_score("srv-1", "org-1", _clean_report())
        await repo.upsert(score)
        fetched = await repo.get("srv-1")
        assert fetched is not None
        assert fetched.score == score.score
        assert fetched.tier is score.tier

    async def test_upsert_replaces_existing_row(self, repo: ToolTrustRepository) -> None:
        first = compute_trust_score("srv-1", "org-1", _clean_report())
        await repo.upsert(first)
        second = compute_trust_score("srv-1", "org-1", _typosquat_report())
        await repo.upsert(second)
        fetched = await repo.get("srv-1")
        assert fetched is not None
        assert fetched.score == second.score

    async def test_list_scoped_to_org(self, repo: ToolTrustRepository) -> None:
        await repo.upsert(compute_trust_score("srv-a", "org-a", _clean_report()))
        await repo.upsert(compute_trust_score("srv-b", "org-b", _clean_report()))
        org_a_scores = await repo.list_for_org("org-a")
        assert len(org_a_scores) == 1
        assert org_a_scores[0].server_id == "srv-a"

    async def test_admin_override_round_trips(self, repo: ToolTrustRepository) -> None:
        current = unscanned_score("srv-1", "org-1")
        overridden = apply_admin_override(
            current, ToolTrustTier.BLOCKED, admin_id="admin-1", reason="manual block"
        )
        await repo.upsert(overridden)
        fetched = await repo.get("srv-1")
        assert fetched is not None
        assert fetched.tier is ToolTrustTier.BLOCKED
        assert fetched.admin_override_by == "admin-1"
        assert fetched.admin_override_reason == "manual block"


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(
        identity=_identity(org_id), organization_id=org_id, framework="upstream-gateway"
    )


def _upstream_action(
    server_id: str = "srv-1", tool_name: str = "remote_tool", org_id: str = "org-1"
) -> ActionRequest:
    return ActionRequest(
        agent=_agent(org_id),
        action_type=ACTION_TYPE,
        target=build_upstream_target(server_id, tool_name),
    )


def _allow_decision(action_id: str) -> DecisionResult:
    return DecisionResult(
        decision=GovernanceDecision.ALLOW, action_id=action_id, risk_tier=RiskTier.HIGH
    )


class _FakeRegistry:
    """Same shape as test_upstream_gateway.py's own fake -- returns
    whatever `_FakeServer` object is currently stored under a
    `server_id`, so a test can mutate it between authorize-time and
    execute-time to simulate config drift."""

    def __init__(self, servers: dict) -> None:
        self._servers = servers

    async def get(self, server_id: str):
        return self._servers.get(server_id)


class _FakeServer:
    def __init__(
        self, org_id: str, url: str, enabled: bool = True, auth_token: str | None = None
    ) -> None:
        self.org_id = org_id
        self.url = url
        self.enabled = enabled
        self.auth_token = auth_token


class TestExecutionPermitV2FingerprintDrift:
    """Execution Permit v2 (Phase 9): `ExecutionAuthorization` now binds
    to the resolved server config at decision time, not just the action
    digest -- a `server_id::tool_name` target string is unchanged, but
    what it resolves to can drift."""

    def test_internal_style_permit_with_no_fingerprint_is_unaffected(self) -> None:
        """`target_fingerprint=None` (the default) must never trigger a
        drift check -- InternalToolExecutor never sets one."""
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        assert authorization.target_fingerprint is None

    async def test_url_change_between_authorize_and_execute_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fake_public_dns(monkeypatch)
        server = _FakeServer("org-1", "https://partner.example.com/mcp")
        registry = _FakeRegistry({"srv-1": server})
        action = _upstream_action()

        fingerprint_at_decision = compute_upstream_target_fingerprint(server)
        authorization = authorize_execution(
            _allow_decision(action.action_id), action, target_fingerprint=fingerprint_at_decision
        )

        # The server's registration changes after the decision but
        # before execution -- same server_id, different resolved URL.
        server.url = "https://attacker-controlled.example.com/mcp"

        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(AuthorizationTargetDriftError):
            await executor.execute(authorization, action)

    async def test_auth_token_presence_change_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fake_public_dns(monkeypatch)
        server = _FakeServer("org-1", "https://partner.example.com/mcp", auth_token=None)
        registry = _FakeRegistry({"srv-1": server})
        action = _upstream_action()

        fingerprint_at_decision = compute_upstream_target_fingerprint(server)
        authorization = authorize_execution(
            _allow_decision(action.action_id), action, target_fingerprint=fingerprint_at_decision
        )

        server.auth_token = "some-new-credential"  # noqa: S105 -- test fixture value, not a real secret

        executor = UpstreamMCPExecutor(registry)
        with pytest.raises(AuthorizationTargetDriftError):
            await executor.execute(authorization, action)

    async def test_unchanged_config_is_not_flagged_as_drift(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The success path: same URL/enabled/auth_token at both
        points must not raise AuthorizationTargetDriftError. The actual
        proxied call is never reached in this test -- a fake HTTP
        client factory raises immediately, both to keep the test fast
        (no real socket/timeout) and to prove the drift check runs
        *before* any network attempt."""
        _fake_public_dns(monkeypatch)
        server = _FakeServer("org-1", "https://partner.example.com/mcp")
        registry = _FakeRegistry({"srv-1": server})
        action = _upstream_action()

        fingerprint_at_decision = compute_upstream_target_fingerprint(server)
        authorization = authorize_execution(
            _allow_decision(action.action_id), action, target_fingerprint=fingerprint_at_decision
        )

        class _BoomFactory:
            def __call__(self):
                raise RuntimeError("no real network call expected in this test")

        executor = UpstreamMCPExecutor(registry, http_client_factory=_BoomFactory())
        with pytest.raises(RuntimeError, match="no real network call expected"):
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
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as c:
            yield c


@pytest.fixture()
async def org_and_admin_key(client: AsyncClient):
    r = await client.post(
        "/api/orgs",
        json={"name": "Tool Trust Test Co", "slug": "tool-trust-test-co"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    org_id = r.json()["id"]
    r = await client.post(
        f"/api/orgs/{org_id}/keys",
        json={"name": "admin-key", "role": "ADMIN"},
        headers=BOOTSTRAP_AUTH,
    )
    assert r.status_code == 201, r.text
    return org_id, r.json()["key"]


class TestToolTrustRESTEndpoints:
    async def test_get_trust_for_never_scanned_server_is_provisional(
        self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}
        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "partner", "url": "https://partner.example.com/mcp"},
            headers=headers,
        )
        server_id = r.json()["server_id"]

        r = await client.get(f"/api/governance/upstream/servers/{server_id}/trust", headers=headers)
        assert r.status_code == 200
        body = r.json()
        assert body["tier"] == "PROVISIONAL"
        assert body["has_been_scanned"] is False

    async def test_get_trust_for_unknown_server_is_404(
        self, client: AsyncClient, org_and_admin_key
    ) -> None:
        _org_id, admin_key = org_and_admin_key
        headers = {"Authorization": f"Bearer {admin_key}"}
        r = await client.get(
            "/api/governance/upstream/servers/does-not-exist/trust", headers=headers
        )
        assert r.status_code == 404

    async def test_override_requires_admin(
        self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}
        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "partner", "url": "https://partner.example.com/mcp"},
            headers=headers,
        )
        server_id = r.json()["server_id"]

        r = await client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "analyst-key", "role": "ANALYST"},
            headers=BOOTSTRAP_AUTH,
        )
        analyst_key = r.json()["key"]
        r = await client.post(
            f"/api/governance/upstream/servers/{server_id}/trust/override",
            json={"tier": "BLOCKED", "reason": "test"},
            headers={"Authorization": f"Bearer {analyst_key}"},
        )
        assert r.status_code == 403

    async def test_override_to_blocked_then_call_is_denied(
        self, client: AsyncClient, org_and_admin_key, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The end-to-end proof this feature exists for: an admin
        override to BLOCKED must stop a subsequent governed call to
        that server before governance even evaluates it, with the
        UNTRUSTED_MCP_SERVER reason code."""
        _org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}
        r = await client.post(
            "/api/governance/upstream/servers",
            json={"name": "partner", "url": "https://partner.example.com/mcp"},
            headers=headers,
        )
        server_id = r.json()["server_id"]

        r = await client.post(
            f"/api/governance/upstream/servers/{server_id}/trust/override",
            json={"tier": "BLOCKED", "reason": "reported by a partner org"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["tier"] == "BLOCKED"

        r = await client.post(
            f"/api/governance/upstream/servers/{server_id}/call",
            json={"tool_name": "anything", "arguments": {}},
            headers=headers,
        )
        assert r.status_code == 200  # governance-blocked, not an HTTP error
        body = r.json()
        assert body["error"] == "governance_denied"
        assert any("UNTRUSTED_MCP_SERVER" in code for code in body["reason_codes"])

    async def test_scan_persists_a_real_score_from_a_real_upstream_server(
        self,
        client: AsyncClient,
        org_and_admin_key,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same real-second-server pattern as
        test_upstream_gateway.py's full round-trip test -- proves the
        scan endpoint actually discovers real tools and persists a real
        score, not a mocked one."""
        import responsibleai.db as db_module
        from responsibleai.db import OrgRepository
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.rbac.models import Plan, Role

        org_id, admin_key = org_and_admin_key
        _fake_public_dns(monkeypatch)
        headers = {"Authorization": f"Bearer {admin_key}"}

        upstream_engine = create_engine(":memory:")
        await upstream_engine.init()
        upstream_org_repo = OrgRepository(upstream_engine)
        upstream_org = await upstream_org_repo.create_org(
            "Upstream Provider Co", "tool-trust-upstream-co", plan=Plan.ENTERPRISE
        )
        _key_rec, upstream_raw_key = await upstream_org_repo.create_key(
            upstream_org.id, "upstream-key", role=Role.ANALYST
        )

        r = await client.post(
            "/api/governance/upstream/servers",
            json={
                "name": "real-upstream",
                "url": "http://tool-trust-upstream-test/mcp",
                "auth_token": upstream_raw_key,
            },
            headers=headers,
        )
        assert r.status_code == 201
        server_id = r.json()["server_id"]

        monkeypatch.setattr(db_module, "create_engine", lambda _url: upstream_engine)
        upstream_app = _build_http_app()

        def _fake_factory():
            from httpx import AsyncClient as _AsyncClient

            return _AsyncClient(
                transport=ASGITransport(app=upstream_app),
                base_url="http://tool-trust-upstream-test",
            )

        monkeypatch.setattr(
            "responsibleai.governance.upstream_discovery._default_http_client_factory",
            _fake_factory,
        )

        async with LifespanManager(upstream_app):
            r = await client.post(
                f"/api/governance/upstream/servers/{server_id}/trust/scan", headers=headers
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["has_been_scanned"] is True
        assert body["tier"] in {"PROVISIONAL", "TRUSTED", "UNTRUSTED", "BLOCKED"}

        r = await client.get(f"/api/governance/upstream/servers/{server_id}/trust", headers=headers)
        assert r.json()["has_been_scanned"] is True
