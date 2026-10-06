# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2 isolation child dispatch boundary — parent admission vs direct backend."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.execution_nonce_repository import ExecutionNonceRepository
from responsibleai.governance.execution import InternalToolExecutor, authorize_execution
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.isolation.models import DEFAULT_STRICT_PROFILE, IsolatedExecutionRequest
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend


@pytest.mark.asyncio
async def test_parent_executor_admits_before_dispatch(monkeypatch: pytest.MonkeyPatch) -> None:
    org = str(uuid.uuid4())
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert().values(id=org, name=org, slug=org, created_at="now")
        )
    action = ActionRequest(
        AgentContext(IdentityContext("p", "api_key", org_id=org), organization_id=org),
        "rai_health",
        "rai_health",
        arguments={},
    )
    permit = authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, action.action_id), action, revocation_epoch=0
    )
    sink = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", sink)
    executor = InternalToolExecutor(nonce_repo=ExecutionNonceRepository(engine))
    executor._broker = None
    await executor.execute(permit, action)
    sink.assert_awaited_once()


@pytest.mark.asyncio
async def test_direct_subprocess_backend_invokes_dispatch_without_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Documents the LOCAL_DEV child trust model: stdin JSON is not a crypto
    admission proof. Enterprise production forbids same-process/subprocess
    shortcuts without IsolationBroker + production gate (see execution.py)."""
    sink = AsyncMock(return_value={"status": "ok"})
    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", sink)

    async def _fake_subprocess(*_args, **_kwargs):
        await sink("rai_health", {})
        proc = AsyncMock()
        proc.communicate = AsyncMock(
            return_value=(
                b'{"status": "success", "result": {"status": "ok"}}',
                b"",
            )
        )
        proc.returncode = 0
        return proc

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_subprocess)
    backend = LocalSubprocessBackend()
    request = IsolatedExecutionRequest(
        action_id="forged",
        organization_id="org-attacker",
        action_type="rai_health",
        arguments={},
        profile=DEFAULT_STRICT_PROFILE,
    )
    outcome = await backend.execute(request)
    assert outcome.is_success
    sink.assert_awaited()


@pytest.mark.asyncio
async def test_production_internal_executor_refuses_without_broker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("WHITEPACT_ISOLATION_BACKEND", raising=False)
    action = ActionRequest(
        AgentContext(IdentityContext("p", "api_key", org_id="o"), organization_id="o"),
        "rai_health",
        "rai_health",
        arguments={},
    )
    permit = authorize_execution(DecisionResult(GovernanceDecision.ALLOW, action.action_id), action)
    sink = AsyncMock()
    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", sink)
    from responsibleai.isolation.errors import IsolationBackendUnavailableError, IsolationError

    try:
        executor = InternalToolExecutor(nonce_repo=None)
    except IsolationBackendUnavailableError:
        sink.assert_not_awaited()
        return
    executor._broker = None
    with pytest.raises(IsolationError):
        await executor.execute(permit, action)
    sink.assert_not_awaited()
