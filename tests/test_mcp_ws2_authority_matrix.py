# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2 Lane A — authority boundary adversarial matrix (BLK-P0-02 / P0-03).

Complements test_executor_bypass_invariant.py, test_mcp_governance_dispatch.py,
and test_upstream_gateway.py with explicit WS-2 entrypoint and downgrade coverage.
M1 Antigravity qualification remains mandatory before findings are closed.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from responsibleai.dashboard.config import Settings
from responsibleai.db.engine import create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    ExecutionAuthorization,
    GovernanceDecision,
    IdentityContext,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.models import DecisionResult
from responsibleai.governance.risk import RiskTier
from responsibleai.mcp.server import (
    HostedProductionSecurityError,
    _run_stdio,
    _run_stdio_main_body,
    hosted_production_preflight,
    main,
)
from responsibleai.mcp.trust_domain import (
    ENTERPRISE_STDIO_REFUSAL,
    PRODUCTION_COMMUNITY_DOWNGRADE_REFUSAL,
    entrypoint_main_stdio,
    refuse_ungoverned_stdio_exit,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), organization_id=org_id, framework="mcp-client")


def _action(org_id: str = "org-1") -> ActionRequest:
    return ActionRequest(
        agent=_agent(org_id), action_type="rai_scan", target="rai_scan", arguments={"text": "x"}
    )


def _allow(action_id: str) -> DecisionResult:
    return DecisionResult(
        decision=GovernanceDecision.ALLOW,
        action_id=action_id,
        risk_tier=RiskTier.MINIMAL,
    )


class TestStdioInvocationRoutes:
    def test_main_exits_enterprise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.dashboard.config import get_settings

        monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 2

    def test_entrypoint_main_stdio_exits_enterprise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.dashboard.config import get_settings

        monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
        with pytest.raises(SystemExit) as exc:
            entrypoint_main_stdio()
        assert exc.value.code == 2

    def test_refuse_ungoverned_stdio_exit(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.dashboard.config import get_settings

        monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
        with pytest.raises(SystemExit) as exc:
            refuse_ungoverned_stdio_exit()
        assert exc.value.code == 2

    def test_run_stdio_main_body_reaches_asyncio(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.dashboard.config import get_settings

        monkeypatch.setattr(get_settings(), "mcp_trust_domain", "community")
        seen: list[str] = []

        def _fake_run(coro: object) -> None:
            seen.append("run")
            close = getattr(coro, "close", None)
            if callable(close):
                close()

        monkeypatch.setattr("responsibleai.mcp.server.asyncio.run", _fake_run)
        _run_stdio_main_body()
        assert seen == ["run"]

    def test_run_stdio_coroutine_guard_enterprise(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from responsibleai.dashboard.config import get_settings

        monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
        with pytest.raises(SystemExit):
            asyncio.run(_run_stdio())

    def test_python_module_main_enterprise_refused(self) -> None:
        env = {**os_environ_safe(), "WHITEPACT_MCP_TRUST_DOMAIN": "enterprise"}
        proc = subprocess.run(
            [sys.executable, "-m", "responsibleai.mcp.server"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_REPO_ROOT),
        )
        assert proc.returncode == 2
        assert "Enterprise MCP trust domain" in proc.stderr + proc.stdout

    def test_import_main_subprocess_enterprise_env(self) -> None:
        env = {**os_environ_safe(), "WHITEPACT_MCP_TRUST_DOMAIN": "enterprise"}
        proc = subprocess.run(
            [sys.executable, "-c", "from responsibleai.mcp.server import main; main()"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(_REPO_ROOT),
        )
        assert proc.returncode == 2


def os_environ_safe() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if isinstance(v, str)}


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


class TestEnterpriseTrustDowngradePrevention:
    def test_production_settings_reject_community_trust_domain(self) -> None:
        with pytest.raises(ValueError, match="enterprise"):
            Settings(environment="production", mcp_trust_domain="community")

    def test_hosted_production_preflight_requires_enterprise_trust(self) -> None:
        from types import SimpleNamespace

        settings = SimpleNamespace(
            environment="production",
            is_production=True,
            mcp_governance_enabled=True,
            mcp_trust_domain="community",
            mcp_http_allow_unauthenticated_demo=False,
            phase7a_dispatcher_enabled=False,
            multi_replica=False,
            api_keys=[],
        )
        with pytest.raises(HostedProductionSecurityError, match="mcp_trust_domain"):
            hosted_production_preflight(settings, allowed_hosts=["mcp.example.com"])

    def test_refusal_messages_document_paths(self) -> None:
        assert "hosted MCP" in ENTERPRISE_STDIO_REFUSAL
        assert "enterprise" in PRODUCTION_COMMUNITY_DOWNGRADE_REFUSAL.lower()


class TestGrantBindingAndReplayMatrix:
    async def test_expired_grant_refused(self) -> None:
        from dataclasses import replace

        action = _action()
        authorization = authorize_execution(_allow(action.action_id), action)
        expired = replace(
            authorization,
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        with pytest.raises(AuthorizationExpiredError):
            await InternalToolExecutor().execute(expired, action)

    async def test_cross_tenant_grant_refused(self) -> None:
        action = _action("org-a")
        authorization = authorize_execution(_allow(action.action_id), action)
        other = _action("org-b")
        with pytest.raises(AuthorizationOrganizationMismatchError):
            await InternalToolExecutor().execute(authorization, other)

    async def test_replayed_authorization_refused(self) -> None:
        action = _action()
        authorization = authorize_execution(_allow(action.action_id), action)
        executor = InternalToolExecutor()
        await executor.execute(authorization, action)
        with pytest.raises(AuthorizationAlreadyConsumedError):
            await executor.execute(authorization, action)

    async def test_forged_grant_wrong_digest_refused(self) -> None:
        from responsibleai.governance import AuthorizationActionMismatchError

        action = _action()
        authorization = authorize_execution(_allow(action.action_id), action)
        forged = ExecutionAuthorization(
            action_digest="f" * 64,
            organization_id=authorization.organization_id,
            decision=authorization.decision,
            principal_id=authorization.principal_id,
            nonce=authorization.nonce,
        )
        with pytest.raises(AuthorizationActionMismatchError):
            await InternalToolExecutor().execute(forged, action)


class TestHostedAndUpstreamBypassGuards:
    async def test_call_tool_hosted_without_governance_never_dispatches(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from responsibleai.mcp.server import _call_tool, _current_hosted, _current_org
        from responsibleai.rbac.models import OrgContext, Plan, Role

        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.server.dispatch_tool", dispatch)
        token_org = _current_org.set(
            OrgContext(
                key_id="k1", org_id="o1", org_name="acme", plan=Plan.ENTERPRISE, role=Role.ANALYST
            )
        )
        token_hosted = _current_hosted.set(True)
        try:
            _text, payload = await _call_tool("rai_health", {"_whitepact_purpose": "test"})
        finally:
            _current_hosted.reset(token_hosted)
            _current_org.reset(token_org)
        assert payload.get("error") == "governance_unavailable"
        dispatch.assert_not_awaited()

    async def test_upstream_unregistered_server_denied(self) -> None:
        from unittest.mock import AsyncMock, MagicMock

        from responsibleai.mcp.upstream_dispatch import apply_upstream_governance
        from responsibleai.rbac.models import OrgContext, Plan, Role

        ctx = OrgContext(
            key_id="k1", org_id="o1", org_name="acme", plan=Plan.ENTERPRISE, role=Role.ANALYST
        )
        registry = MagicMock()
        registry.get = AsyncMock(return_value=None)
        outcome = await apply_upstream_governance(
            "missing-server",
            "tool",
            {},
            ctx,
            purpose="probe",
            authority_resolver=MagicMock(),
            gateway=MagicMock(),
            evidence_repo=MagicMock(),
            policy_repo=MagicMock(),
            approval_repo=MagicMock(),
            upstream_registry=registry,
            executor=MagicMock(),
            tool_trust_repo=MagicMock(),
        )
        assert outcome.proceed is False
        assert outcome.blocked_response is not None
        assert outcome.blocked_response.get("error") == "governance_denied"


class TestTrustDomainEnvPrecedenceAndProductionAliases:
    def test_whitepact_env_wins_over_legacy_rai(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WHITEPACT_MCP_TRUST_DOMAIN", "enterprise")
        monkeypatch.setenv("RAI_MCP_TRUST_DOMAIN", "community")
        settings = Settings()
        assert settings.mcp_trust_domain == "enterprise"

    def test_production_alias_prod_rejects_community(self) -> None:
        with pytest.raises(ValueError, match="enterprise"):
            Settings(environment="prod", mcp_trust_domain="community")

    def test_init_production_community_refused_without_dotenv(self) -> None:
        with pytest.raises(ValueError, match="enterprise"):
            Settings(_env_file=None, environment="production", mcp_trust_domain="community")


class TestStaleRevocationEpochOnLiveExecutor:
    async def test_stale_epoch_denied_before_dispatch(self, tmp_path, monkeypatch) -> None:
        import uuid

        from responsibleai.db.engine import create_engine, organizations
        from responsibleai.db.execution_nonce_repository import (
            ExecutionNonceRepository,
            StaleRevocationEpochError,
        )
        from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository

        sink = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", sink)

        url = str(tmp_path / "epoch.db")
        engine = create_engine(url)
        await engine.init()
        org = str(uuid.uuid4())
        async with engine.raw.begin() as conn:
            await conn.execute(
                organizations.insert().values(id=org, name=org, slug=org, created_at="now")
            )
        nonce_repo = ExecutionNonceRepository(engine)
        epochs = RevocationEpochRepository(engine)
        action = _action(org)
        permit = authorize_execution(_allow(action.action_id), action, revocation_epoch=0)
        await epochs.bump(org)
        assert (await epochs.current(org)).epoch == 1
        executor = InternalToolExecutor(nonce_repo=nonce_repo)
        executor._broker = None
        with pytest.raises(StaleRevocationEpochError):
            await executor.execute(permit, action)
        sink.assert_not_awaited()


class TestApplyGovernanceInfrastructureFailClosed:
    async def test_resolver_raises_never_dispatches(self, engine, monkeypatch) -> None:
        import uuid
        from unittest.mock import AsyncMock, MagicMock

        from responsibleai.db import OrgRepository
        from responsibleai.governance import WhitePactRuntimeGateway
        from responsibleai.governance.authority_resolver import AuthorityDenied, AuthorityResolver
        from responsibleai.mcp.governance_integration import GovernanceServices, apply_governance
        from responsibleai.rbac.models import OrgContext, Plan, Role

        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)

        repo = OrgRepository(engine)
        org = await repo.create_org("Fail", f"fail-{uuid.uuid4().hex[:8]}")
        resolver = MagicMock(spec=AuthorityResolver)
        resolver.resolve = AsyncMock(side_effect=AuthorityDenied("denied"))
        services = GovernanceServices(
            gateway=WhitePactRuntimeGateway(),
            evidence_repo=MagicMock(record=AsyncMock()),
            approval_repo=MagicMock(),
            policy_repo=MagicMock(),
            trust_client=MagicMock(),
            authority_resolver=resolver,
            org_repo=repo,
        )
        ctx = OrgContext(key_id="k1", role=Role.ANALYST, org_id=org.id, plan=Plan.ENTERPRISE)
        outcome = await apply_governance("rai_health", {}, ctx, services, purpose="ws2-matrix")
        assert outcome.proceed is False
        assert outcome.blocked_response is not None
        assert outcome.blocked_response.get("error") in {
            "governance_denied",
            "governance_evidence_unavailable",
        }
        dispatch.assert_not_awaited()

    async def test_evidence_write_failure_fail_closed(
        self, engine, monkeypatch, seed_runtime_authority
    ) -> None:
        import uuid
        from unittest.mock import AsyncMock, MagicMock

        from responsibleai.db import OrgRepository
        from responsibleai.db.consent_proof_repository import ConsentProofRepository
        from responsibleai.db.delegation_repository import DelegationRepository
        from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
        from responsibleai.db.root_authority_repository import RootAuthorityRepository
        from responsibleai.governance import WhitePactRuntimeGateway
        from responsibleai.governance.authority_resolver import AuthorityResolver
        from responsibleai.mcp.governance_integration import GovernanceServices, apply_governance
        from responsibleai.rbac.models import OrgContext, Plan, Role

        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)

        repo = OrgRepository(engine)
        org = await repo.create_org("Ev", f"ev-{uuid.uuid4().hex[:8]}")
        principal = "k1"
        await seed_runtime_authority(
            engine,
            organization_id=org.id,
            principal_id=principal,
            action_types=("rai_health",),
            targets=("rai_health",),
        )
        resolver = AuthorityResolver(
            RootAuthorityRepository(engine),
            ConsentProofRepository(engine),
            DelegationRepository(engine),
        )
        evidence = MagicMock()
        evidence.record = AsyncMock(side_effect=RuntimeError("db down"))
        services = GovernanceServices(
            gateway=WhitePactRuntimeGateway(),
            evidence_repo=evidence,
            approval_repo=MagicMock(),
            policy_repo=MagicMock(get_policy=AsyncMock(return_value=MagicMock(version=1))),
            trust_client=MagicMock(),
            authority_resolver=resolver,
            org_repo=repo,
            epoch_repo=RevocationEpochRepository(engine),
            nonce_repo=MagicMock(),
        )
        ctx = OrgContext(key_id=principal, role=Role.ANALYST, org_id=org.id, plan=Plan.ENTERPRISE)
        outcome = await apply_governance("rai_health", {}, ctx, services, purpose="ws2-matrix")
        assert outcome.proceed is False
        assert outcome.blocked_response.get("error") == "governance_evidence_unavailable"
        dispatch.assert_not_awaited()

    async def test_nonce_repo_failure_on_execute_fail_closed(self, tmp_path, monkeypatch) -> None:
        import uuid
        from unittest.mock import AsyncMock

        from responsibleai.db.engine import create_engine, organizations
        from responsibleai.governance.execution import ExecutionNotAuthorizedError

        sink = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", sink)

        url = str(tmp_path / "nonce-fail.db")
        engine = create_engine(url)
        await engine.init()
        org = str(uuid.uuid4())
        async with engine.raw.begin() as conn:
            await conn.execute(
                organizations.insert().values(id=org, name=org, slug=org, created_at="now")
            )
        action = _action(org)
        permit = authorize_execution(_allow(action.action_id), action, revocation_epoch=0)
        executor = InternalToolExecutor(nonce_repo=None)
        with pytest.raises(ExecutionNotAuthorizedError):
            await executor.execute(permit, action)
        sink.assert_not_awaited()


class TestUpstreamGrantBindingMatrix:
    async def test_expired_upstream_grant_never_calls_upstream(self, monkeypatch) -> None:
        from dataclasses import replace
        from types import SimpleNamespace
        from unittest.mock import AsyncMock

        from responsibleai.governance.upstream_executor import (
            ACTION_TYPE,
            UpstreamMCPExecutor,
        )

        upstream = AsyncMock(return_value={"ok": True})
        monkeypatch.setattr(
            "responsibleai.governance.upstream_executor._call_upstream_tool", upstream
        )
        monkeypatch.setattr(
            "responsibleai.governance.upstream_executor.validate_upstream_server_url",
            lambda _: None,
        )
        server = SimpleNamespace(
            server_id="s1",
            org_id="org-1",
            enabled=True,
            url="https://example.com/mcp",
            auth_token=None,
        )
        action = ActionRequest(
            _agent("org-1"),
            ACTION_TYPE,
            "s1::tool",
            arguments={},
        )
        permit = authorize_execution(_allow(action.action_id), action, revocation_epoch=0)
        expired = replace(
            permit,
            expires_at=datetime.now(UTC) - timedelta(seconds=5),
        )
        executor = UpstreamMCPExecutor(SimpleNamespace(get=AsyncMock(return_value=server)))
        with pytest.raises(AuthorizationExpiredError):
            await executor.execute(expired, action)
        upstream.assert_not_awaited()


class TestConcurrentDurableConsumptionWs2Evidence:
    """Mandatory WS-2 evidence hook: production nonce repository under concurrency."""

    async def test_exactly_one_dispatch_under_race(self, tmp_path, monkeypatch) -> None:
        import copy
        import uuid

        from responsibleai.db.engine import create_engine, organizations
        from responsibleai.db.execution_nonce_repository import (
            ExecutionNonceRepository,
            NonceAlreadyConsumedError,
        )
        from tests.test_phase1_live_admission import _action as live_action
        from tests.test_phase1_live_admission import _executor as live_executor_factory
        from tests.test_phase1_live_admission import _permit as live_permit

        url = str(tmp_path / "ws2-race.db")
        engine = create_engine(url)
        await engine.init()
        org = str(uuid.uuid4())
        async with engine.raw.begin() as conn:
            await conn.execute(
                organizations.insert().values(id=org, name=org, slug=org, created_at="now")
            )
        other = create_engine(url)
        sink = AsyncMock(return_value={"ok": True})
        action = live_action("internal", org)
        permit = live_permit(action)
        executors = [
            live_executor_factory("internal", ExecutionNonceRepository(e), org, monkeypatch, sink)
            for e in (engine, other)
        ]
        results = await asyncio.gather(
            *[
                executors[i % 2].execute(copy.deepcopy(permit), copy.deepcopy(action))
                for i in range(8)
            ],
            return_exceptions=True,
        )
        assert sum(isinstance(r, dict) for r in results) == 1
        assert sum(isinstance(r, NonceAlreadyConsumedError) for r in results) == 7
        assert sink.await_count == 1
        await other.close()
        await engine.close()


class TestAuthorizationPathLatencyEvidence:
    """Engineering-only timing smoke (not a performance SLA)."""

    async def test_authorize_and_admit_monotonic_budget(self, tmp_path, monkeypatch) -> None:
        import time
        import uuid

        from responsibleai.db.engine import create_engine, organizations
        from responsibleai.db.execution_nonce_repository import ExecutionNonceRepository

        monkeypatch.setattr(
            "responsibleai.mcp.tools.dispatch_tool",
            AsyncMock(return_value={"status": "ok"}),
        )
        url = str(tmp_path / "perf.db")
        engine = create_engine(url)
        await engine.init()
        org = str(uuid.uuid4())
        async with engine.raw.begin() as conn:
            await conn.execute(
                organizations.insert().values(id=org, name=org, slug=org, created_at="now")
            )
        action = _action(org)
        started = time.monotonic()
        permit = authorize_execution(_allow(action.action_id), action, revocation_epoch=0)
        authorize_ms = (time.monotonic() - started) * 1000
        executor = InternalToolExecutor(nonce_repo=ExecutionNonceRepository(engine))
        admit_started = time.monotonic()
        await executor.execute(permit, action)
        admit_ms = (time.monotonic() - admit_started) * 1000
        await engine.close()
        assert authorize_ms < 5000
        assert admit_ms < 5000
