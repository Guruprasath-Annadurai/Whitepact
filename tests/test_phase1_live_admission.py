# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exercise real executors, not just the nonce repository's consume method."""

import asyncio
import copy
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
    StaleRevocationEpochError,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    AuthorizationExpiredError,
    ExecutionNotAuthorizedError,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    UpstreamMCPExecutor,
    compute_upstream_target_fingerprint,
)


def _executor(kind, nonce_repo, org, monkeypatch, sink):
    if kind == "internal":
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", sink)
        return InternalToolExecutor(nonce_repo=nonce_repo)
    server = SimpleNamespace(
        server_id="server",
        org_id=org,
        enabled=True,
        url="https://example.com/mcp",
        auth_token=None,
    )
    monkeypatch.setattr("responsibleai.governance.upstream_executor._call_upstream_tool", sink)
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor.validate_upstream_server_url", lambda _: None
    )
    return UpstreamMCPExecutor(
        SimpleNamespace(get=AsyncMock(return_value=server)), nonce_repo=nonce_repo
    )


def _action(kind, org):
    return ActionRequest(
        AgentContext(IdentityContext("worker", "api_key", org_id=org)),
        "rai_health" if kind == "internal" else ACTION_TYPE,
        "rai_health" if kind == "internal" else "server::read",
        arguments={"record": "invoice"},
        purpose="reconcile",
    )


def _permit(action, epoch=0):
    fingerprint = None
    if action.action_type == ACTION_TYPE:
        fingerprint = compute_upstream_target_fingerprint(
            SimpleNamespace(url="https://example.com/mcp", enabled=True, auth_token=None)
        )
    return authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, action.action_id),
        action,
        revocation_epoch=epoch,
        target_fingerprint=fingerprint,
    )


@pytest.mark.parametrize("kind", ["internal", "upstream"])
async def test_live_copied_permits_independent_consumers_and_reopen(kind, tmp_path, monkeypatch):
    url = str(tmp_path / "admission.db")
    engine = create_engine(url)
    await engine.init()
    org = str(uuid.uuid4())
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert().values(id=org, name=org, slug=org, created_at="now")
        )
    other = create_engine(url)
    sink = AsyncMock(return_value={"ok": True})
    action = _action(kind, org)
    permit = _permit(action)
    try:
        executors = [
            _executor(kind, ExecutionNonceRepository(e), org, monkeypatch, sink)
            for e in (engine, other)
        ]
        results = await asyncio.gather(
            *[
                executors[i % 2].execute(copy.deepcopy(permit), copy.deepcopy(action))
                for i in range(16)
            ],
            return_exceptions=True,
        )
        assert sum(isinstance(result, dict) for result in results) == 1
        assert sum(isinstance(result, NonceAlreadyConsumedError) for result in results) == 15
        assert sink.await_count == 1
        await other.close()
        await engine.close()
        reopened = create_engine(url)
        try:
            executor = _executor(kind, ExecutionNonceRepository(reopened), org, monkeypatch, sink)
            with pytest.raises(NonceAlreadyConsumedError):
                await executor.execute(copy.deepcopy(permit), action)
            await RevocationEpochRepository(reopened).bump(org)
            with pytest.raises(StaleRevocationEpochError):
                await executor.execute(_permit(action), action)
            assert sink.await_count == 1
            await executor.execute(_permit(action, epoch=1), action)
            assert sink.await_count == 2
        finally:
            await reopened.close()
    finally:
        await other.close()
        await engine.close()


@pytest.mark.parametrize("kind", ["internal", "upstream"])
@pytest.mark.parametrize("fault", ["database", "expiry", "mutation", "missing_epoch", "downgrade"])
async def test_admission_fails_closed(kind, fault, monkeypatch):
    action = _action(kind, "org")
    permit = _permit(action)
    sink = AsyncMock()

    async def consume(*args, **kwargs):
        if fault == "database":
            raise RuntimeError("database unavailable")
        if fault == "expiry":
            permit.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        if fault == "mutation":
            action.arguments["record"] = "different"

    repo = SimpleNamespace(consume=consume)
    expected = {
        "database": RuntimeError,
        "expiry": AuthorizationExpiredError,
        "mutation": AuthorizationActionMismatchError,
        "missing_epoch": ExecutionNotAuthorizedError,
        "downgrade": ExecutionNotAuthorizedError,
    }
    if fault == "missing_epoch":
        permit.revocation_epoch = None
    executor = _executor(kind, None if fault == "downgrade" else repo, "org", monkeypatch, sink)
    with pytest.raises(expected[fault]):
        await executor.execute(permit, action)
    sink.assert_not_awaited()


async def test_upstream_dispatch_uses_admitted_arguments(monkeypatch):
    action = _action("upstream", "org")
    permit = _permit(action)
    sink = AsyncMock(return_value={"ok": True})
    executor = _executor("upstream", SimpleNamespace(consume=AsyncMock()), "org", monkeypatch, sink)

    async def record_consumed(_credential_id):
        action.arguments["record"] = "changed-after-admission"

    executor._credential_issuance_repo = SimpleNamespace(
        record_issued=AsyncMock(),
        record_consumed=record_consumed,
    )
    await executor.execute(permit, action)
    assert sink.call_args.args[2] == {"record": "invoice"}
