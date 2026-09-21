# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Cursor V1 hardening: production preflight, governance_status, secrets, capacity."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from responsibleai.dashboard.config import is_production_environment
from responsibleai.db import OrgRepository, create_engine
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.mcp.server import HostedProductionSecurityError, hosted_production_preflight
from responsibleai.mcp.tools import dispatch_tool
from responsibleai.net.egress import PeerMismatchError, SafeNetworkBackend
from responsibleai.rbac.models import GovernanceStatus, Plan
from responsibleai.runtime.capacity_reservation import (
    AtomicCapacityReservation,
    InMemoryRedisEval,
)
from responsibleai.runtime.lock_order import CANONICAL_LOCK_ORDER


def test_production_environment_detection() -> None:
    assert is_production_environment("production") is True
    assert is_production_environment("PROD") is True
    assert is_production_environment("development") is False
    assert is_production_environment("staging") is False


def test_hosted_production_preflight_rejects_demo() -> None:
    settings = SimpleNamespace(
        is_production=True,
        mcp_http_allow_unauthenticated_demo=True,
        mcp_governance_enabled=True,
        multi_replica=False,
    )
    with pytest.raises(HostedProductionSecurityError, match="unauthenticated_demo"):
        hosted_production_preflight(settings, allowed_hosts=["mcp.example.com"])


def test_hosted_production_preflight_requires_governance() -> None:
    settings = SimpleNamespace(
        is_production=True,
        mcp_http_allow_unauthenticated_demo=False,
        mcp_governance_enabled=False,
        multi_replica=False,
    )
    with pytest.raises(HostedProductionSecurityError, match="mcp_governance_enabled"):
        hosted_production_preflight(settings, allowed_hosts=["mcp.example.com"])


def test_hosted_production_preflight_requires_allowlist() -> None:
    settings = SimpleNamespace(
        is_production=True,
        mcp_http_allow_unauthenticated_demo=False,
        mcp_governance_enabled=True,
        multi_replica=False,
    )
    with pytest.raises(HostedProductionSecurityError, match="ALLOWED_HOSTS"):
        hosted_production_preflight(settings, allowed_hosts=[])


def test_hosted_production_preflight_skips_non_production() -> None:
    settings = SimpleNamespace(
        is_production=False,
        mcp_http_allow_unauthenticated_demo=True,
        mcp_governance_enabled=False,
    )
    hosted_production_preflight(settings, allowed_hosts=[])


def test_hosted_production_preflight_rejects_multi_replica() -> None:
    settings = SimpleNamespace(
        is_production=True,
        mcp_http_allow_unauthenticated_demo=False,
        mcp_governance_enabled=True,
        multi_replica=True,
    )
    with pytest.raises(HostedProductionSecurityError, match="one authenticated"):
        hosted_production_preflight(settings, allowed_hosts=["mcp.example.com"])


def test_hosted_production_preflight_rejects_phase7a_dispatcher() -> None:
    settings = SimpleNamespace(
        is_production=True,
        mcp_http_allow_unauthenticated_demo=False,
        mcp_governance_enabled=True,
        multi_replica=False,
        phase7a_dispatcher_enabled=True,
    )
    with pytest.raises(HostedProductionSecurityError, match="Gate B"):
        hosted_production_preflight(settings, allowed_hosts=["mcp.example.com"])


@pytest.mark.asyncio
async def test_dispatch_tool_does_not_return_exception_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from responsibleai.mcp import tools as tools_mod

    original = tools_mod._TOOL_HANDLERS["rai_scan"]

    async def boom(_args: dict) -> dict:
        raise RuntimeError("password=supersecret-db-url")

    monkeypatch.setitem(tools_mod._TOOL_HANDLERS, "rai_scan", boom)
    result = await dispatch_tool("rai_scan", {"text": "x"})
    assert result["error"] == "tool_execution_failed"
    assert "supersecret" not in str(result)
    monkeypatch.setitem(tools_mod._TOOL_HANDLERS, "rai_scan", original)


@pytest.mark.asyncio
async def test_governance_status_bumps_epoch_billing_does_not() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    org_repo = OrgRepository(engine)
    epoch_repo = RevocationEpochRepository(engine)
    org = await org_repo.create_org("Gov Co", "gov-co", plan=Plan.ENTERPRISE)
    before = await epoch_repo.current(org.id)
    assert org.governance_status == GovernanceStatus.ACTIVE.value

    ok = await org_repo.set_governance_status(org.id, GovernanceStatus.SUSPENDED)
    assert ok is True
    after = await epoch_repo.current(org.id)
    assert after.epoch == before.epoch + 1
    loaded = await org_repo.get_org(org.id)
    assert loaded is not None
    assert loaded.governance_status == GovernanceStatus.SUSPENDED.value

    await org_repo.set_plan(org.id, Plan.FREE, subscription_status="canceled")
    after_billing = await epoch_repo.current(org.id)
    assert after_billing.epoch == after.epoch
    billed = await org_repo.get_org(org.id)
    assert billed is not None
    assert billed.plan is Plan.FREE
    assert billed.governance_status == GovernanceStatus.SUSPENDED.value
    await engine.close()


@pytest.mark.asyncio
async def test_set_plan_cannot_write_governance_status() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Bill Co", "bill-co", plan=Plan.PRO)
    await org_repo.set_plan(org.id, Plan.ENTERPRISE, subscription_status="active")
    loaded = await org_repo.get_org(org.id)
    assert loaded is not None
    assert loaded.plan is Plan.ENTERPRISE
    assert loaded.governance_status == GovernanceStatus.ACTIVE.value
    await engine.close()


def test_capacity_reserve_release_idempotent() -> None:
    store = InMemoryRedisEval()
    cap = AtomicCapacityReservation(store)
    first = cap.reserve(
        execution_id="ex-1", organization_id="org-1", ttl_seconds=30, tenant_limit=2
    )
    assert first.ok is True
    assert first.mutated is True
    assert first.tenant_count == 1
    again = cap.reserve(
        execution_id="ex-1", organization_id="org-1", ttl_seconds=30, tenant_limit=2
    )
    assert again.ok is True
    assert again.mutated is False
    assert again.tenant_count == 1
    second = cap.reserve(
        execution_id="ex-2", organization_id="org-1", ttl_seconds=30, tenant_limit=2
    )
    assert second.ok is True
    assert second.tenant_count == 2
    third = cap.reserve(
        execution_id="ex-3", organization_id="org-1", ttl_seconds=30, tenant_limit=2
    )
    assert third.ok is False
    released = cap.release(execution_id="ex-1", organization_id="org-1")
    assert released.mutated is True
    assert released.tenant_count == 1
    released_again = cap.release(execution_id="ex-1", organization_id="org-1")
    assert released_again.mutated is False
    assert released_again.tenant_count == 1


def test_canonical_lock_order_starts_with_organization() -> None:
    assert CANONICAL_LOCK_ORDER[0] == "organizations"
    assert CANONICAL_LOCK_ORDER[1] == "governance_revocation_epochs"
    assert CANONICAL_LOCK_ORDER.index("runtime_execution_requests") < CANONICAL_LOCK_ORDER.index(
        "governance_execution_authorizations"
    )
    assert CANONICAL_LOCK_ORDER.index("runtime_execution_attempts") > CANONICAL_LOCK_ORDER.index(
        "runtime_execution_requests"
    )


@pytest.mark.asyncio
async def test_post_connect_peer_unavailable_fails_closed() -> None:
    from unittest.mock import AsyncMock

    import httpcore

    class _Resolver:
        async def resolve(self, host, port, policy):
            return ["93.184.216.34"]

    mock_inner = AsyncMock(spec=httpcore.AsyncNetworkBackend)
    mock_stream = AsyncMock(spec=httpcore.AsyncNetworkStream)
    mock_stream.get_extra_info.side_effect = RuntimeError("no peer")
    mock_inner.connect_tcp.return_value = mock_stream
    backend = SafeNetworkBackend(
        resolver=_Resolver(),  # type: ignore[arg-type]
        inner_backend=mock_inner,
    )
    with pytest.raises(PeerMismatchError, match="Could not verify"):
        await backend.connect_tcp("api.example.com", 443)
    mock_stream.aclose.assert_awaited()
