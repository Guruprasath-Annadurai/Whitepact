# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Denied upstream dispatch with genuine organization state, not journey receipts."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

from responsibleai.db.engine import organizations
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    OrganizationNotGovernableError,
    StaleRevocationEpochError,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.db.upstream_repository import UpstreamServerRepository
from responsibleai.governance.execution import authorize_execution
from responsibleai.governance.upstream_executor import (
    UpstreamMCPExecutor,
    compute_upstream_target_fingerprint,
)
from tests.test_sovereign_authority import owner as owner
from tests.test_upstream_gateway import _allow_decision, _fake_public_dns, _upstream_action


@pytest.mark.asyncio
@pytest.mark.parametrize("state", ["ACTIVE", "SUSPENDED", "DISABLED"])
async def test_committed_disable_never_dispatches_for_real_workspace(owner, state, monkeypatch):
    engine, _, actor, *_ = owner
    _fake_public_dns(monkeypatch)
    repo = UpstreamServerRepository(engine)
    server = await repo.register(actor.org_id, "partner", "https://partner.example.com/mcp")
    epoch = (await RevocationEpochRepository(engine).current(actor.org_id)).epoch
    action = _upstream_action(server_id=server.server_id, org_id=actor.org_id)
    # A constructed candidate permit is only a negative input. No ALLOW decision,
    # credential, remote dispatch or customer execution success is certified here.
    authorization = authorize_execution(
        _allow_decision(action.action_id),
        action,
        revocation_epoch=epoch,
        target_fingerprint=compute_upstream_target_fingerprint(server),
    )
    entered, release = asyncio.Event(), asyncio.Event()

    class PausingAudit:
        async def record_issued(self, *args, **kwargs):
            entered.set()
            await release.wait()

        async def record_consumed(self, *args, **kwargs):
            raise AssertionError("Denied permit must not be consumed")

    sink = AsyncMock()
    monkeypatch.setattr("responsibleai.governance.upstream_executor._call_upstream_tool", sink)
    executor = UpstreamMCPExecutor(
        repo, credential_issuance_repo=PausingAudit(), nonce_repo=ExecutionNonceRepository(engine)
    )
    pending = asyncio.create_task(executor.execute(authorization, action))
    try:
        await asyncio.wait_for(entered.wait(), 5)
        await repo.set_enabled(actor.org_id, server.server_id, False)
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == actor.org_id)
                .values(governance_status=state)
            )
        release.set()
        expected = (
            StaleRevocationEpochError if state == "ACTIVE" else OrganizationNotGovernableError
        )
        with pytest.raises(expected):
            await asyncio.wait_for(pending, 5)
        sink.assert_not_awaited()
    finally:
        release.set()
        await asyncio.gather(pending, return_exceptions=True)
