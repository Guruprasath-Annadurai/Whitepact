# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Empirical test suite for RestoreReadinessGate runtime admission across all consequential boundaries.

Guarantees:
- HTTP consequential boundary is strictly guarded (503 Service Unavailable with Retry-After).
- MCP consequential tool execution is strictly guarded.
- Upstream MCP consequential execution is strictly guarded.
- Background consequential workers (webhooks, retention pruning, erasure) are strictly guarded.
- Privileged tenant administration is strictly guarded.
- Startup in restore mode defaults to NOT_READY (STARTUP PRE-RECONCILIATION ACTIONS: 0).
- Multi-worker derives authoritative state from shared Store B (STALE WORKER EXECUTION: 0).
- Only narrowly authorized read-only and operator recovery endpoints remain admitted.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from responsibleai.dashboard.app import app
from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
    get_restore_readiness_gate,
    reset_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
from responsibleai.data_governance.erasure import DataErasureManager
from responsibleai.data_governance.retention import RetentionManager
from responsibleai.db.engine import create_engine
from responsibleai.governance.execution import ExecutionAuthorization, InternalToolExecutor
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.upstream_executor import UpstreamMCPExecutor
from responsibleai.iam.enums import PrivilegedAction
from responsibleai.iam.guard import PrivilegedSurfaceGuard
from responsibleai.iam.models import PrivilegedCallerContext
from responsibleai.mcp.server import _call_tool
from responsibleai.rbac.models import Role
from responsibleai.webhooks.manager import WebhookManager
from responsibleai.webhooks.models import WebhookConfig, WebhookEvent


def _now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture(autouse=True)
def clean_gate():
    """Ensure clean gate state before and after each test."""
    gate = reset_restore_readiness_gate(state=RestoreReadinessState.READY)
    yield gate
    reset_restore_readiness_gate(state=RestoreReadinessState.READY)


def test_http_consequential_boundary_blocked_at_restore_pending_and_failed():
    """Consequential HTTP operations are blocked (503) while health/recovery endpoints remain available."""
    gate = reset_restore_readiness_gate(state=RestoreReadinessState.RESTORE_PENDING)
    client = TestClient(app)

    # 1. Consequential/ordinary route is blocked at RESTORE_PENDING
    resp = client.get("/signup")
    assert resp.status_code == 503
    assert resp.headers.get("Retry-After") == "10"
    data = resp.json()
    assert data["error"] == "restore_quarantine"
    assert data["status"] == "RESTORE_PENDING"

    # API endpoints are blocked
    resp_api = client.get("/api/branding")
    assert resp_api.status_code == 503

    # 2. Permitted health and recovery endpoints are admitted
    resp_health = client.get("/health")
    assert resp_health.status_code == 200

    resp_healthz = client.get("/healthz")
    assert resp_healthz.status_code == 200

    resp_status = client.get("/api/v1/restore/status")
    assert resp_status.status_code == 200
    assert resp_status.json()["status"] == "RESTORE_PENDING"
    assert resp_status.json()["is_admitted"] is False

    # 3. Same blocks apply at FAILED state
    gate.set_state(RestoreReadinessState.FAILED)
    resp_failed = client.get("/signup")
    assert resp_failed.status_code == 503
    assert resp_failed.json()["status"] == "FAILED"

    resp_status_failed = client.get("/api/v1/restore/status")
    assert resp_status_failed.status_code == 200
    assert resp_status_failed.json()["status"] == "FAILED"

    # 4. Once READY, consequential traffic is admitted
    gate.set_state(RestoreReadinessState.READY)
    resp_ready = client.get("/signup")
    assert resp_ready.status_code == 200


@pytest.mark.asyncio
async def test_mcp_consequential_boundary_blocked_at_restore_pending():
    """MCP tool execution is blocked with structured quarantine response when not READY."""
    gate = reset_restore_readiness_gate(state=RestoreReadinessState.RESTORE_PENDING)

    # Invoke real MCP tool boundary
    blocks, payload = await _call_tool(
        "calculate_cost", {"model": "gpt-4o", "input_tokens": 100, "output_tokens": 50}
    )
    assert payload.get("error") == "restore_quarantine"
    assert payload.get("status") == "RESTORE_PENDING"
    assert "MCP tool execution blocked" in payload.get("message", "")

    # Transition to FAILED -> still blocked
    gate.set_state(RestoreReadinessState.FAILED)
    blocks, payload = await _call_tool(
        "calculate_cost", {"model": "gpt-4o", "input_tokens": 100, "output_tokens": 50}
    )
    assert payload.get("error") == "restore_quarantine"
    assert payload.get("status") == "FAILED"


@pytest.mark.asyncio
async def test_upstream_mcp_and_internal_executor_boundaries():
    """Upstream and internal tool execution boundaries raise RestoreQuarantineError when not READY."""
    reset_restore_readiness_gate(state=RestoreReadinessState.RESTORE_PENDING)

    auth = ExecutionAuthorization(
        action_digest="digest-test-1",
        organization_id="org-test-1",
        decision=GovernanceDecision.ALLOW,
        authorization_id="auth-test-1",
        nonce="nonce-test-1",
        revocation_epoch=1,
    )
    agent = AgentContext(
        identity=IdentityContext(identity_id="k1", kind="api_key", org_id="org-test-1"),
        agent_id="agent-1",
        organization_id="org-test-1",
    )
    action = ActionRequest(
        action_type="mcp_tool_call",
        target="srv-1::tool-1",
        arguments={},
        agent=agent,
    )

    # 1. UpstreamMCPExecutor
    upstream_exec = UpstreamMCPExecutor(registry=MagicMock())
    with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
        await upstream_exec.execute(auth, action)

    # 2. InternalToolExecutor
    internal_exec = InternalToolExecutor()
    with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
        await internal_exec.execute(auth, action)


@pytest.mark.asyncio
async def test_background_consequential_workers_blocked_at_restore_pending():
    """Background jobs (webhooks, retention cleanup, erasure) raise RestoreQuarantineError."""
    reset_restore_readiness_gate(state=RestoreReadinessState.RESTORE_PENDING)
    engine = create_engine(":memory:")
    await engine.init()
    try:
        # 1. Webhook delivery worker
        wm = WebhookManager()
        cfg = WebhookConfig(
            id="wh-1",
            org_id="org-1",
            url="https://example.com/webhook",
            events=[WebhookEvent.GUARDRAIL_TRIGGERED],
        )
        wm.register(cfg)
        with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
            await wm.fire(WebhookEvent.GUARDRAIL_TRIGGERED, {"rule_id": "rule-1"})

        # 2. Retention policy evaluation & cleanup worker
        retention = RetentionManager(engine)
        with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
            await retention.run_retention_cleanup("org-1")

        # 3. Data erasure execution worker
        erasure = DataErasureManager(engine)
        with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
            await erasure.execute_erasure("req-1")

    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_privileged_tenant_administration_blocked_at_restore_pending():
    """Privileged administration (guard and deletion orchestrator) is blocked while not READY."""
    reset_restore_readiness_gate(state=RestoreReadinessState.RESTORE_PENDING)
    engine = create_engine(":memory:")
    await engine.init()
    try:
        # 1. PrivilegedSurfaceGuard
        guard = PrivilegedSurfaceGuard(engine)
        caller = PrivilegedCallerContext(
            principal_id="user-admin-1",
            org_id="org-1",
            role=Role.ADMIN,
            is_platform_operator=False,
        )
        with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
            await guard.authorize_privileged_operation(
                caller=caller,
                target_org_id="org-1",
                action=PrivilegedAction.REVOKE_API_KEY,
            )

        # 2. TenantDeletionOrchestrator
        orchestrator = TenantDeletionOrchestrator(engine)
        with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
            await orchestrator.delete_tenant(
                org_id="org-1",
                deleted_by="user-admin-1",
                reason="GDPR deletion",
            )

    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_multi_worker_shared_restore_readiness(tmp_path: Path):
    """Multiple workers derive admission from authoritative shared Store B state without stale execution."""
    store_b_path = tmp_path / "shared_gate_store_b.db"

    # Worker A and Worker B with separate gate instances connected to shared Store B
    provider_a = SqliteDurableLifecycleStateProvider(store_b_path)
    provider_b = SqliteDurableLifecycleStateProvider(store_b_path)

    gate_worker_a = RestoreReadinessGate(
        initial_state=RestoreReadinessState.RESTORE_PENDING, provider=provider_a
    )
    gate_worker_b = RestoreReadinessGate(
        initial_state=RestoreReadinessState.RESTORE_PENDING, provider=provider_b
    )

    # Initial: both observe RESTORE_PENDING
    assert gate_worker_a.is_admitted() is False
    assert gate_worker_b.is_admitted() is False

    # Worker A sets state to READY upon successful reconciliation
    gate_worker_a.set_state(RestoreReadinessState.READY, updated_by="worker-a")

    # Worker B immediately observes authoritative state from shared Store B (STALE WORKER EXECUTION: 0)
    assert gate_worker_b.state == RestoreReadinessState.READY
    assert gate_worker_b.is_admitted() is True
    gate_worker_b.assert_traffic_admitted()  # Does not raise!

    # Failure in Store B causes worker B to fail closed
    gate_worker_a.set_state(RestoreReadinessState.FAILED, updated_by="worker-a")
    assert gate_worker_b.state == RestoreReadinessState.FAILED
    assert gate_worker_b.is_admitted() is False
    with pytest.raises(RestoreQuarantineError):
        gate_worker_b.assert_traffic_admitted()


@pytest.mark.asyncio
async def test_startup_safety_default_not_ready():
    """When WhitePact starts up in restore mode, default is RESTORE_PENDING; pre-reconciliation actions blocked."""
    old_mode = os.environ.get("WHITEPACT_RESTORE_MODE")
    os.environ["WHITEPACT_RESTORE_MODE"] = "1"
    try:
        set_restore_readiness_gate(None)  # Force fresh initialization
        startup_gate = get_restore_readiness_gate()

        # Must start in RESTORE_PENDING
        assert startup_gate.state == RestoreReadinessState.RESTORE_PENDING
        assert startup_gate.is_admitted() is False

        # Attempt pre-reconciliation action -> blocked (STARTUP PRE-RECONCILIATION ACTIONS: 0)
        with pytest.raises(RestoreQuarantineError):
            startup_gate.assert_traffic_admitted()

    finally:
        if old_mode is not None:
            os.environ["WHITEPACT_RESTORE_MODE"] = old_mode
        else:
            os.environ.pop("WHITEPACT_RESTORE_MODE", None)
        set_restore_readiness_gate(None)
