# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2 upstream UNKNOWN / reconciliation-required behavior."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from responsibleai.db.execution_nonce_repository import ExecutionNonceRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
    authorize_execution,
)
from responsibleai.governance.models import DecisionResult
from responsibleai.governance.outcome import OutcomeStatus
from responsibleai.governance.upstream_executor import (
    ACTION_TYPE,
    UpstreamMCPExecutor,
    compute_upstream_target_fingerprint,
)
from responsibleai.mcp.upstream_dispatch import apply_upstream_governance
from responsibleai.rbac.models import OrgContext, Plan, Role


@pytest.fixture
async def engine():
    from responsibleai.db.engine import create_engine

    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


@pytest.mark.asyncio
async def test_upstream_executor_transport_error_classified_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SimpleNamespace(
        server_id="srv",
        org_id="org-1",
        enabled=True,
        url="https://upstream.example/mcp",
        auth_token=None,
    )
    registry = SimpleNamespace(get=AsyncMock(return_value=server))
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor.validate_upstream_server_url",
        lambda _: None,
    )
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor._call_upstream_tool",
        AsyncMock(side_effect=httpx.ConnectTimeout("timeout")),
    )
    action = ActionRequest(
        AgentContext(IdentityContext("p", "api_key", org_id="org-1"), organization_id="org-1"),
        ACTION_TYPE,
        "srv::remote_tool",
        arguments={},
    )
    permit = authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, action.action_id),
        action,
        revocation_epoch=0,
        target_fingerprint=compute_upstream_target_fingerprint(server),
    )
    executor = UpstreamMCPExecutor(registry, nonce_repo=SimpleNamespace(consume=AsyncMock()))
    with pytest.raises(httpx.ConnectTimeout):
        await executor.execute(permit, action)


@pytest.mark.asyncio
async def test_upstream_dispatch_records_unknown_on_executor_failure(
    engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    from unittest.mock import MagicMock

    from responsibleai.db import (
        ApprovalRepository,
        EvidenceRepository,
        OrgRepository,
        OutcomeRepository,
        PolicyRepository,
    )
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
    from responsibleai.db.tool_trust_repository import ToolTrustRepository
    from responsibleai.governance.authority_resolver import AuthorityResolver

    repo = OrgRepository(engine)
    org = await repo.create_org("Up", f"up-{uuid.uuid4().hex[:8]}")
    principal = "up-principal"
    resolved = MagicMock()
    resolved.authority = AuthorityContext(
        delegated_by="fixture",
        granted_action_types=frozenset({ACTION_TYPE}),
    )
    resolved.authority_version = 1
    resolved.consent_id = "consent"
    resolved.consent_version = 1
    resolver = MagicMock(spec=AuthorityResolver)
    resolver.resolve = AsyncMock(return_value=resolved)
    server = SimpleNamespace(
        server_id="srv",
        org_id=org.id,
        enabled=True,
        url="https://upstream.example/mcp",
        auth_token=None,
    )
    registry = SimpleNamespace(get=AsyncMock(return_value=server))
    executor = UpstreamMCPExecutor(registry, nonce_repo=ExecutionNonceRepository(engine))
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor._call_upstream_tool",
        AsyncMock(side_effect=httpx.ReadError("reset")),
    )
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor.validate_upstream_server_url",
        lambda _: None,
    )
    outcome_repo = OutcomeRepository(engine)
    evidence_repo = EvidenceRepository(engine)
    with pytest.raises(httpx.ReadError):
        await apply_upstream_governance(
            "srv",
            "remote_tool",
            {},
            OrgContext(key_id=principal, role=Role.ANALYST, org_id=org.id, plan=Plan.ENTERPRISE),
            purpose="ws2-up",
            authority_resolver=resolver,
            gateway=WhitePactRuntimeGateway(),
            evidence_repo=evidence_repo,
            policy_repo=PolicyRepository(engine),
            approval_repo=ApprovalRepository(engine),
            upstream_registry=registry,
            executor=executor,
            tool_trust_repo=ToolTrustRepository(engine),
            epoch_repo=RevocationEpochRepository(engine),
            outcome_repo=outcome_repo,
        )
    records = await evidence_repo.list_for_org(org.id, decision="ALLOW")
    assert records
    outcome = await outcome_repo.get_for_org(records[0].evidence_id, org.id)
    assert outcome is not None
    assert outcome.status is OutcomeStatus.UNKNOWN


@pytest.mark.asyncio
async def test_upstream_is_error_response_is_failed_not_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server = SimpleNamespace(
        server_id="srv",
        org_id="org-1",
        enabled=True,
        url="https://upstream.example/mcp",
        auth_token=None,
    )
    registry = SimpleNamespace(get=AsyncMock(return_value=server))
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor.validate_upstream_server_url",
        lambda _: None,
    )
    monkeypatch.setattr(
        "responsibleai.governance.upstream_executor._call_upstream_tool",
        AsyncMock(return_value={"is_error": True, "content": ["upstream 500"]}),
    )
    action = ActionRequest(
        AgentContext(IdentityContext("p", "api_key", org_id="org-1"), organization_id="org-1"),
        ACTION_TYPE,
        "srv::remote_tool",
        arguments={},
    )
    permit = authorize_execution(
        DecisionResult(GovernanceDecision.ALLOW, action.action_id),
        action,
        revocation_epoch=0,
        target_fingerprint=compute_upstream_target_fingerprint(server),
    )
    executor = UpstreamMCPExecutor(registry, nonce_repo=SimpleNamespace(consume=AsyncMock()))
    result = await executor.execute(permit, action)
    assert result["is_error"] is True
