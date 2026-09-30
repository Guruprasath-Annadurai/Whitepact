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
from unittest.mock import AsyncMock

import pytest

from responsibleai.dashboard.config import Settings
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
            cwd="/workspace",
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
            cwd="/workspace",
        )
        assert proc.returncode == 2


def os_environ_safe() -> dict[str, str]:
    import os

    return {k: v for k, v in os.environ.items() if isinstance(v, str)}


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
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from responsibleai.mcp.server import _call_tool, _current_hosted, _current_org
        from responsibleai.rbac.models import OrgContext, Plan, Role

        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.server.dispatch_tool", dispatch)
        token_org = _current_org.set(
            OrgContext(key_id="k1", org_id="o1", org_name="acme", plan=Plan.ENTERPRISE, role=Role.ANALYST)
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

        ctx = OrgContext(key_id="k1", org_id="o1", org_name="acme", plan=Plan.ENTERPRISE, role=Role.ANALYST)
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
