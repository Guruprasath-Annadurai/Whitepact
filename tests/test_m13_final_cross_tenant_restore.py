# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Malformed restored FK graphs must not mutate another tenant's approval.

Rows below are negative database fixtures, never customer authority receipts.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleState,
    LifecycleStateRecord,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
)
from responsibleai.db.engine import (
    governance_approvals,
    organizations,
    restore_reconciliation_records,
    runtime_execution_requests,
)
from responsibleai.isolation import in_flight as tracking
from tests.test_m13_final_admission import admission_engine as admission_engine


@pytest.mark.asyncio
async def test_foreign_approval_reference_blocks_restore_without_mutating_foreign_tenant(
    admission_engine, monkeypatch, tmp_path
):
    engine = admission_engine
    now = datetime.now(UTC)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking")
    monkeypatch.setattr(tracking.InFlightExecutionRegistry, "_instance", None)
    async with engine.raw.begin() as conn:
        for tenant in ("deleted-a", "active-b"):
            await conn.execute(
                insert(organizations).values(
                    id=tenant,
                    name=tenant,
                    slug=tenant,
                    created_at=now.isoformat(),
                    governance_status="ACTIVE",
                )
            )
        await conn.execute(
            insert(governance_approvals).values(
                id="foreign-pending",
                org_id="active-b",
                action_id="negative-only",
                action_type="test",
                target="harmless",
                reason_codes="[]",
                status="PENDING",
                requested_at=now.isoformat(),
            )
        )
        await conn.execute(
            insert(runtime_execution_requests).values(
                request_id="malformed",
                organization_id="deleted-a",
                principal_id="negative-only",
                agent_id="negative-only",
                identity_id="negative-only",
                intent="test",
                action_type="test",
                target="harmless",
                action_digest="0" * 64,
                canonical_action_payload="{}",
                approved_arguments={},
                observed_governance_epoch=0,
                idempotency_key="malformed",
                approval_id="foreign-pending",
                created_at=now,
            )
        )
    provider = InMemoryLifecycleStateProvider()
    for tenant, state in (
        ("deleted-a", LifecycleState.TOMBSTONED),
        ("active-b", LifecycleState.ACTIVE),
    ):
        provider.record_state(
            LifecycleStateRecord(
                tenant_id=tenant,
                generation_id="negative-test",
                state=state,
                effective_at=now.isoformat(),
                security_epoch=0,
                revocation_floor=0,
            )
        )
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciler = RestoreReconciliationEngine(engine, lifecycle_provider=provider, gate=gate)
    error = None
    try:
        await reconciler.reconcile_post_restore("independent-negative-test")
    except RestoreReconciliationError as exc:
        error = exc
    async with engine.raw.begin() as conn:
        assert (
            await conn.scalar(
                select(governance_approvals.c.status).where(
                    governance_approvals.c.id == "foreign-pending"
                )
            )
            == "PENDING"
        )
        assert (
            await conn.scalar(
                select(organizations.c.governance_status).where(organizations.c.id == "deleted-a")
            )
            == "ACTIVE"
        )
        assert await conn.scalar(select(restore_reconciliation_records.c.status)) == "FAILED"
    assert error is not None and "cross-tenant" in str(error).lower()
    assert gate.state == RestoreReadinessState.FAILED
