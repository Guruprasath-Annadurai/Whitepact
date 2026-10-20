# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Campaign B: Live Restore Authority & Stale Cached Readiness Adversarial Evaluation.

Tests:
1. Database initially clean and reconciled.
2. WhitePact successfully verifies authority (RECONCILED, READY).
3. New unresolved recovery marker is durably committed into PostgreSQL.
4. Application process remains running (stale cache risk).
5. Synchronous execution boundary attempts admission.
6. Asynchronous execution boundary attempts admission.
7. MCP tool attempts admission.
8. Background worker attempts admission.
9. Application cold restarts.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import os
import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    StartupAuthorityMode,
    assert_current_restore_readiness_admitted,
    assert_restore_readiness_admitted,
    evaluate_startup_authority,
    get_restore_readiness_gate,
    reset_restore_readiness_gate,
)
from responsibleai.db.engine import restore_reconciliation_records
from tests.test_m13_final_admission import admission_engine


@pytest.mark.asyncio
async def test_campaign_b_live_restore_authority_stale_cache_invalidation(admission_engine):
    engine = admission_engine
    now = datetime.now(UTC).isoformat()

    # 1. Database is initially clean and reconciled
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(restore_reconciliation_records).values(
                id=f"rec-{uuid.uuid4().hex[:8]}",
                restored_at=now,
                status="RECONCILED",
                reconciled_by="initial-dr",
            )
        )

    # 2. WhitePact successfully verifies authority
    provider = InMemoryLifecycleStateProvider()
    gate = RestoreReadinessGate(
        initial_state=RestoreReadinessState.READY,
        provider=provider,
        db_engine=engine,
    )
    # Check that initial authority check succeeds
    await gate.assert_current_traffic_admitted()
    assert gate.is_admitted() is True

    # 3. An out-of-band disaster recovery event durably commits an unresolved marker into DB
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(restore_reconciliation_records).values(
                id=f"rec-unres-{uuid.uuid4().hex[:8]}",
                restored_at=datetime.now(UTC).isoformat(),
                status="CONTAINMENT_PENDING",
                reconciled_by="out-of-band-dr-operator",
            )
        )

    # 4. Application process remains running (stale cache attack).

    # 5. Synchronous execution boundary attempts admission:
    # With a database authority configured, synchronous callers MUST NOT bypass
    # live database authority using stale cached readiness.
    with pytest.raises(RestoreQuarantineError, match="Current database authority requires asynchronous admission verification"):
        gate.assert_traffic_admitted()

    # 6. Asynchronous execution boundary attempts admission:
    # Must query database authority, detect the new marker, fail closed, and mutate gate state
    with pytest.raises(RestoreQuarantineError, match="FAILED"):
        await gate.assert_current_traffic_admitted()

    # Gate state is now strictly FAILED and records the database restore inconsistency
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False
    assert "CONTAINMENT_PENDING" in str(gate.provider_error)

    # 7. MCP tool attempts admission:
    from responsibleai.mcp.server import _call_tool
    import responsibleai.data_governance.backup_defense as bd_mod
    bd_mod._GLOBAL_RESTORE_GATE = gate

    _contents, payload = await _call_tool("policy_evaluate", {"policy_id": "test", "_whitepact_organization_id": "org-test"})
    assert payload.get("error") == "restore_quarantine"
    assert "pending restore reconciliation" in payload.get("message", "")

    # 8. Background worker / consequential execution boundary attempts admission
    with pytest.raises(RestoreQuarantineError):
        await assert_current_restore_readiness_admitted()

    # 9. Application cold restart: evaluate startup authority on fresh process
    eval_result = evaluate_startup_authority(gate=gate, engine=engine, db_status="CONTAINMENT_PENDING")
    assert eval_result.mode in (StartupAuthorityMode.RECOVERY, StartupAuthorityMode.UNCERTAIN)
    assert eval_result.readiness_state == RestoreReadinessState.FAILED
    assert eval_result.integrity_verified is False
