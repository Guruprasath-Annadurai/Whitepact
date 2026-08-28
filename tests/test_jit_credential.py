# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for the JIT Credential Broker (Authority Everywhere Phase 10).

Covers: the pure issue/consume functions in
`governance/jit_credential.py` (single-use, expiry-capped-by-permit,
refuses to issue against a bad authorization), `CredentialIssuanceRepository`'s
fail-open audit persistence, `UpstreamMCPExecutor`'s wiring (the
executor no longer reads `server.auth_token` directly, an issuance is
recorded before the authorization is consumed, a consumption is
recorded after), and a real end-to-end REST round trip proving the
credential actually authenticates the proxied call and leaves a
complete audit row behind.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db import create_engine
from responsibleai.db.credential_issuance_repository import CredentialIssuanceRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.execution import authorize_execution
from responsibleai.governance.jit_credential import (
    AuthorizationNotYetValidatedError,
    CredentialAlreadyConsumedError,
    CredentialExpiredError,
    JITCredential,
    consume_jit_credential,
    issue_jit_credential,
)
from responsibleai.governance.models import DecisionResult
from responsibleai.governance.risk import RiskTier
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    UpstreamMCPExecutor,
    build_upstream_target,
)

BOOTSTRAP_AUTH = {"Authorization": "Bearer bootstrap-test-key"}


def _fake_public_dns(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_getaddrinfo(host, *args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr("responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo)


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


class _FakeServer:
    def __init__(
        self, org_id: str, url: str, enabled: bool = True, auth_token: str | None = None
    ) -> None:
        self.org_id = org_id
        self.url = url
        self.enabled = enabled
        self.auth_token = auth_token


class _FakeRegistry:
    def __init__(self, servers: dict) -> None:
        self._servers = servers

    async def get(self, server_id: str):
        return self._servers.get(server_id)


class TestIssueJitCredential:
    def test_issues_a_credential_bound_to_the_authorization(self) -> None:
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        server = _FakeServer("org-1", "https://partner.example.com/mcp", auth_token="secret-token")  # noqa: S106

        credential = issue_jit_credential(authorization, "srv-1", server)

        assert credential.authorization_id == authorization.authorization_id
        assert credential.server_id == "srv-1"
        assert credential.org_id == "org-1"
        assert credential.token == "secret-token"
        assert credential.consumed is False

    def test_token_is_none_for_unauthenticated_server(self) -> None:
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        server = _FakeServer("org-1", "https://partner.example.com/mcp", auth_token=None)

        credential = issue_jit_credential(authorization, "srv-1", server)
        assert credential.token is None

    def test_refuses_to_issue_against_a_consumed_authorization(self) -> None:
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        authorization.consumed = True
        server = _FakeServer("org-1", "https://partner.example.com/mcp")

        with pytest.raises(AuthorizationNotYetValidatedError):
            issue_jit_credential(authorization, "srv-1", server)

    def test_refuses_to_issue_against_an_expired_authorization(self) -> None:
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)
        authorization.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        server = _FakeServer("org-1", "https://partner.example.com/mcp")

        with pytest.raises(AuthorizationNotYetValidatedError):
            issue_jit_credential(authorization, "srv-1", server)

    def test_credential_cannot_outlive_the_authorization(self) -> None:
        action = _upstream_action()
        authorization = authorize_execution(
            _allow_decision(action.action_id), action, ttl_seconds=5
        )
        server = _FakeServer("org-1", "https://partner.example.com/mcp")

        credential = issue_jit_credential(authorization, "srv-1", server, ttl_seconds=3600)
        assert credential.expires_at <= authorization.expires_at

    def test_credential_ttl_can_be_shorter_than_the_authorization(self) -> None:
        action = _upstream_action()
        authorization = authorize_execution(
            _allow_decision(action.action_id), action, ttl_seconds=3600
        )
        server = _FakeServer("org-1", "https://partner.example.com/mcp")

        credential = issue_jit_credential(authorization, "srv-1", server, ttl_seconds=5)
        assert credential.expires_at < authorization.expires_at


class TestConsumeJitCredential:
    def _credential(
        self, *, expires_in_seconds: int = 60, token: str | None = "tok"
    ) -> JITCredential:
        now = datetime.now(UTC)
        return JITCredential(
            credential_id="cred-1",
            authorization_id="auth-1",
            server_id="srv-1",
            org_id="org-1",
            token=token,
            issued_at=now,
            expires_at=now + timedelta(seconds=expires_in_seconds),
        )

    def test_returns_the_token_and_marks_consumed(self) -> None:
        credential = self._credential(token="secret")  # noqa: S106
        result = consume_jit_credential(credential)
        assert result == "secret"
        assert credential.consumed is True

    def test_returns_none_for_unauthenticated_server(self) -> None:
        credential = self._credential(token=None)
        assert consume_jit_credential(credential) is None

    def test_double_consumption_is_refused(self) -> None:
        credential = self._credential()
        consume_jit_credential(credential)
        with pytest.raises(CredentialAlreadyConsumedError):
            consume_jit_credential(credential)

    def test_expired_credential_is_refused(self) -> None:
        credential = self._credential(expires_in_seconds=-1)
        with pytest.raises(CredentialExpiredError):
            consume_jit_credential(credential)


class TestCredentialIssuanceRepository:
    @pytest.fixture()
    async def engine(self):
        e = create_engine(":memory:")
        await e.init()
        yield e
        await e.close()

    @pytest.fixture()
    def repo(self, engine):
        return CredentialIssuanceRepository(engine)

    def _credential(self) -> JITCredential:
        now = datetime.now(UTC)
        return JITCredential(
            credential_id="cred-1",
            authorization_id="auth-1",
            server_id="srv-1",
            org_id="org-1",
            token="secret",  # noqa: S106
            issued_at=now,
            expires_at=now + timedelta(seconds=15),
        )

    async def test_record_issued_does_not_raise(self, repo: CredentialIssuanceRepository) -> None:
        await repo.record_issued(self._credential(), action_id="act-1", agent_id="agent-1")

    async def test_record_consumed_does_not_raise(self, repo: CredentialIssuanceRepository) -> None:
        credential = self._credential()
        await repo.record_issued(credential, action_id="act-1", agent_id="agent-1")
        await repo.record_consumed(credential.credential_id)

    async def test_record_issued_never_persists_the_token_value(
        self, repo: CredentialIssuanceRepository, engine
    ) -> None:
        """The audit table has no column for the secret at all -- this
        test proves that by reading the raw row back and confirming
        the token string appears nowhere in it."""
        from sqlalchemy import select

        from responsibleai.db.engine import credential_issuances

        credential = self._credential()
        await repo.record_issued(credential, action_id="act-1", agent_id="agent-1")

        async with engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(credential_issuances).where(
                        credential_issuances.c.credential_id == "cred-1"
                    )
                )
            ).fetchone()
        assert row is not None
        assert "secret" not in str(row)

    async def test_record_issued_is_fail_open_on_db_error(
        self, repo: CredentialIssuanceRepository, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        class _BoomEngine:
            @property
            def raw(self):
                raise RuntimeError("db is down")

        broken_repo = CredentialIssuanceRepository(_BoomEngine())
        # Must not raise -- fail-open, logged instead.
        await broken_repo.record_issued(self._credential(), action_id="act-1", agent_id="agent-1")


class TestUpstreamExecutorJitCredentialWiring:
    async def test_credential_issuance_is_recorded_before_authorization_consumed(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Regression test for a real ordering bug caught during
        development: issuing the credential requires the authorization
        to still be valid, so issuance must happen strictly before
        `authorization.consumed` is set."""
        _fake_public_dns(monkeypatch)
        server = _FakeServer("org-1", "https://partner.example.com/mcp", auth_token="tok")  # noqa: S106
        registry = _FakeRegistry({"srv-1": server})
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)

        recorded_issued = []
        recorded_consumed = []

        class _FakeAuditRepo:
            async def record_issued(self, credential, *, action_id, agent_id):
                recorded_issued.append((credential.credential_id, action_id, agent_id))

            async def record_consumed(self, credential_id):
                recorded_consumed.append(credential_id)

        class _BoomFactory:
            def __call__(self):
                raise RuntimeError("no real network call expected in this test")

        executor = UpstreamMCPExecutor(
            registry, http_client_factory=_BoomFactory(), credential_issuance_repo=_FakeAuditRepo()
        )
        with pytest.raises(RuntimeError, match="no real network call expected"):
            await executor.execute(authorization, action)

        assert len(recorded_issued) == 1
        assert recorded_issued[0][1] == action.action_id
        assert len(recorded_consumed) == 1
        assert recorded_consumed[0] == recorded_issued[0][0]

    async def test_none_audit_repo_is_a_valid_backward_compatible_configuration(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _fake_public_dns(monkeypatch)
        server = _FakeServer("org-1", "https://partner.example.com/mcp")
        registry = _FakeRegistry({"srv-1": server})
        action = _upstream_action()
        authorization = authorize_execution(_allow_decision(action.action_id), action)

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


class TestJitCredentialRestRoundTrip:
    async def test_real_proxied_call_leaves_a_complete_audit_trail(
        self,
        client: AsyncClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same real-second-server pattern as
        test_upstream_gateway.py's full round-trip test -- proves the
        JIT credential broker's token actually authenticates the real
        proxied call (not a mocked one), and that a complete
        credential_issuances audit row (issued + consumed) exists
        afterward, without ever persisting the token value itself."""
        import responsibleai.db as db_module
        from responsibleai.db import OrgRepository
        from responsibleai.mcp.server import _build_http_app
        from responsibleai.rbac.models import Plan, Role

        _fake_public_dns(monkeypatch)

        r = await client.post(
            "/api/orgs",
            json={"name": "JIT Credential Test Co", "slug": "jit-credential-test-co"},
            headers=BOOTSTRAP_AUTH,
        )
        assert r.status_code == 201, r.text
        org_id = r.json()["id"]
        r = await client.post(
            f"/api/orgs/{org_id}/keys",
            json={"name": "admin-key", "role": "ADMIN"},
            headers=BOOTSTRAP_AUTH,
        )
        admin_key = r.json()["key"]
        headers = {"Authorization": f"Bearer {admin_key}"}

        upstream_engine = create_engine(":memory:")
        await upstream_engine.init()
        upstream_org_repo = OrgRepository(upstream_engine)
        upstream_org = await upstream_org_repo.create_org(
            "Upstream Provider Co", "jit-upstream-provider-co", plan=Plan.ENTERPRISE
        )
        _key_rec, upstream_raw_key = await upstream_org_repo.create_key(
            upstream_org.id, "upstream-key", role=Role.ANALYST
        )

        r = await client.post(
            "/api/governance/upstream/servers",
            json={
                "name": "real-upstream",
                "url": "http://jit-upstream-test/mcp",
                "auth_token": upstream_raw_key,
            },
            headers=headers,
        )
        assert r.status_code == 201
        server_id = r.json()["server_id"]

        monkeypatch.setattr(db_module, "create_engine", lambda _url: upstream_engine)
        upstream_app = _build_http_app()

        def _fake_factory():
            return AsyncClient(
                transport=ASGITransport(app=upstream_app), base_url="http://jit-upstream-test"
            )

        monkeypatch.setattr(
            "responsibleai.governance.upstream_executor._default_http_client_factory",
            _fake_factory,
        )

        async with LifespanManager(upstream_app):
            r = await client.post(
                f"/api/governance/upstream/servers/{server_id}/call",
                json={"tool_name": "rai_health", "arguments": {}},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["result"]["is_error"] is False

        from sqlalchemy import select

        from responsibleai.dashboard.app import _db_engine
        from responsibleai.db.engine import credential_issuances

        async with _db_engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(credential_issuances).where(
                        credential_issuances.c.server_id == server_id
                    )
                )
            ).fetchall()
        assert len(rows) == 1
        row = rows[0]
        assert row.had_credential == 1
        assert row.consumed_at is not None
        assert upstream_raw_key not in str(row)
