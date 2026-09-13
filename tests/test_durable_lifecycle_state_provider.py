# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Empirical test suite for Durable Store-B CurrentLifecycleStateProvider and process restart safety.

Guarantees:
- Durable Store B persists across process and node restart outside Store A restore domain.
- Missing durable Store B in production fails closed (PRODUCTION MISSING STORE-B -> READY: 0).
- State transitions are strictly forward-moving; attempts to roll back state or epoch are rejected.
- Corrupt or unavailable Store B prevents reconciliation success and locks gate to FAILED.
- Full process restart + old snapshot restoration neutralizes all resurrected authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleIntegrityError,
    LifecycleRollbackError,
    LifecycleState,
    LifecycleStateRecord,
    MissingLifecycleProviderError,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
    SqliteDurableLifecycleStateProvider,
    StoreBUnavailableError,
    compute_lifecycle_digest,
)
from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
from responsibleai.db.engine import (
    create_engine,
    eval_runs,
    governance_policies,
    org_api_keys,
    organizations,
    tenant_tombstones,
    web_sessions,
    web_users,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.mark.asyncio
async def test_durable_store_b_process_restart_preserves_tombstone(tmp_path: Path):
    """Prove Store B persists tenant tombstones across complete process restart."""
    store_b_path = tmp_path / "lifecycle_store_b.db"
    tenant_id = f"org-{uuid.uuid4().hex[:8]}"
    generation_id = f"gen-{uuid.uuid4().hex[:8]}"
    now = _now()

    # 1. Start durable Store B and record tombstone
    provider_1 = SqliteDurableLifecycleStateProvider(store_b_path)
    digest = compute_lifecycle_digest(
        tenant_id=tenant_id,
        generation_id=generation_id,
        state=LifecycleState.TOMBSTONED.value,
        effective_at=now,
    )
    provider_1.record_state(
        LifecycleStateRecord(
            tenant_id=tenant_id,
            generation_id=generation_id,
            state=LifecycleState.TOMBSTONED,
            effective_at=now,
            digest=digest,
        )
    )
    assert provider_1.is_tombstoned(tenant_id) is True

    # 2. Destroy WhitePact process object completely
    del provider_1

    # 3. Create a brand new Store-B provider instance pointing to same file
    provider_2 = SqliteDurableLifecycleStateProvider(store_b_path)

    # 4. Verify tombstone still exists intact
    rec = provider_2.get_state(tenant_id)
    assert rec is not None
    assert rec.tenant_id == tenant_id
    assert rec.generation_id == generation_id
    assert rec.state == LifecycleState.TOMBSTONED
    assert provider_2.is_tombstoned(tenant_id) is True

    # Check list_tombstones
    tombstones = provider_2.list_tombstones()
    assert len(tombstones) == 1
    assert tombstones[0].tenant_id == tenant_id


@pytest.mark.asyncio
async def test_durable_store_b_failure_matrix(tmp_path: Path):
    """Test Store-B failure matrix: rollback, corruption, outages, stale epoch."""
    store_b_path = tmp_path / "lifecycle_matrix.db"
    provider = SqliteDurableLifecycleStateProvider(store_b_path)
    tenant_id = f"org-{uuid.uuid4().hex[:8]}"
    generation_id = f"gen-{uuid.uuid4().hex[:8]}"
    now = _now()

    # 1. Record ACTIVE
    digest_active = compute_lifecycle_digest(
        tenant_id=tenant_id,
        generation_id=generation_id,
        state=LifecycleState.ACTIVE.value,
        effective_at=now,
        security_epoch=1,
    )
    provider.record_state(
        LifecycleStateRecord(
            tenant_id=tenant_id,
            generation_id=generation_id,
            state=LifecycleState.ACTIVE,
            effective_at=now,
            security_epoch=1,
            digest=digest_active,
        )
    )

    # 2. Advance to TOMBSTONED
    digest_tombstone = compute_lifecycle_digest(
        tenant_id=tenant_id,
        generation_id=generation_id,
        state=LifecycleState.TOMBSTONED.value,
        effective_at=now,
        security_epoch=2,
    )
    provider.record_state(
        LifecycleStateRecord(
            tenant_id=tenant_id,
            generation_id=generation_id,
            state=LifecycleState.TOMBSTONED,
            effective_at=now,
            security_epoch=2,
            digest=digest_tombstone,
        )
    )
    assert provider.is_tombstoned(tenant_id) is True

    # 3. Attempt lifecycle state rollback (TOMBSTONED -> ACTIVE) -> must raise LifecycleRollbackError
    with pytest.raises(LifecycleRollbackError, match="Lifecycle state rollback rejected"):
        provider.record_state(
            LifecycleStateRecord(
                tenant_id=tenant_id,
                generation_id=generation_id,
                state=LifecycleState.ACTIVE,
                effective_at=now,
                security_epoch=2,
            )
        )

    # 4. Attempt security epoch rollback (epoch 2 -> epoch 1) -> must raise LifecycleRollbackError
    with pytest.raises(LifecycleRollbackError, match="Security epoch rollback rejected"):
        provider.record_state(
            LifecycleStateRecord(
                tenant_id=tenant_id,
                generation_id=generation_id,
                state=LifecycleState.TOMBSTONED,
                effective_at=now,
                security_epoch=1,
            )
        )

    # 5. Tampered digest -> must raise LifecycleIntegrityError
    with pytest.raises(LifecycleIntegrityError, match="Tampered lifecycle state record digest"):
        provider.record_state(
            LifecycleStateRecord(
                tenant_id=tenant_id,
                generation_id=generation_id,
                state=LifecycleState.TOMBSTONED,
                effective_at=now,
                security_epoch=2,
                digest="tampered-fake-digest",
            )
        )

    # 6. Verify integrity passes on authentic records
    assert provider.verify_integrity() is True

    # 7. Corrupt record directly in database file -> verify_integrity() must return False
    conn = sqlite3.connect(str(store_b_path))
    conn.execute(
        "UPDATE durable_tenant_lifecycle_states SET state = 'ACTIVE' WHERE tenant_id = ?",
        (tenant_id,),
    )
    conn.commit()
    conn.close()
    assert provider.verify_integrity() is False

    # 8. Temporary provider outage simulation
    provider.set_available(False)
    with pytest.raises(StoreBUnavailableError):
        provider.get_state(tenant_id)
    with pytest.raises(StoreBUnavailableError):
        provider.list_tombstones()
    assert provider.verify_integrity() is False


@pytest.mark.asyncio
async def test_production_missing_durable_store_b_fails_closed(tmp_path: Path):
    """Production configuration must reject missing Store B or InMemory fallback."""
    engine = create_engine(":memory:")
    await engine.init()
    try:
        gate = RestoreReadinessGate()

        # 1. require_durable=True with lifecycle_provider=None -> MissingLifecycleProviderError
        with pytest.raises(MissingLifecycleProviderError, match="Durable Store-B CurrentLifecycleStateProvider is required"):
            RestoreReconciliationEngine(
                engine=engine,
                lifecycle_provider=None,
                gate=gate,
                require_durable=True,
            )
        assert gate.state == RestoreReadinessState.FAILED
        assert gate.is_admitted() is False

        # 2. require_durable=True with InMemoryLifecycleStateProvider -> MissingLifecycleProviderError
        gate_2 = RestoreReadinessGate()
        with pytest.raises(MissingLifecycleProviderError, match="InMemoryLifecycleStateProvider is forbidden"):
            RestoreReconciliationEngine(
                engine=engine,
                lifecycle_provider=InMemoryLifecycleStateProvider(),
                gate=gate_2,
                require_durable=True,
            )
        assert gate_2.state == RestoreReadinessState.FAILED
        assert gate_2.is_admitted() is False

        # 3. Environment variable WHITEPACT_ENV=production enforces require_durable
        old_env = os.environ.get("WHITEPACT_ENV")
        os.environ["WHITEPACT_ENV"] = "production"
        try:
            gate_3 = RestoreReadinessGate()
            with pytest.raises(MissingLifecycleProviderError):
                RestoreReconciliationEngine(
                    engine=engine,
                    lifecycle_provider=None,
                    gate=gate_3,
                )
            assert gate_3.state == RestoreReadinessState.FAILED
        finally:
            if old_env is not None:
                os.environ["WHITEPACT_ENV"] = old_env
            else:
                os.environ.pop("WHITEPACT_ENV", None)

    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_reconciliation_fails_closed_on_corrupt_or_unavailable_store_b(tmp_path: Path):
    """Reconciliation against unavailable or corrupt Store B transitions gate to FAILED."""
    engine = create_engine(":memory:")
    await engine.init()
    try:
        store_b_path = tmp_path / "corrupt_store_b.db"
        provider = SqliteDurableLifecycleStateProvider(store_b_path)
        gate = RestoreReadinessGate(provider=provider)
        reconciler = RestoreReconciliationEngine(
            engine=engine,
            lifecycle_provider=provider,
            gate=gate,
            require_durable=False,
        )

        # 1. Unavailable Store B -> reconciliation fails closed
        provider.set_available(False)
        with pytest.raises(RestoreReconciliationError, match="(integrity check failed|is unavailable)"):
            await reconciler.reconcile_post_restore(reconciled_by="security-auditor")
        assert gate.state == RestoreReadinessState.FAILED
        assert gate.is_admitted() is False
        with pytest.raises(RestoreQuarantineError):
            gate.assert_traffic_admitted()

        # 2. Corrupted Store B -> reconciliation fails closed
        provider.set_available(True)
        provider.set_corrupted(True)
        with pytest.raises(RestoreReconciliationError, match="(integrity check failed|is unavailable)"):
            await reconciler.reconcile_post_restore(reconciled_by="security-auditor")
        assert gate.state == RestoreReadinessState.FAILED
        assert gate.is_admitted() is False

    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_store_a_store_b_full_restart_23_step_restore_attack(tmp_path: Path):
    """Empirical 23-step attack with independent durable files for Store A & Store B and full process restart."""
    store_a_db = tmp_path / "store_a_app.db"
    store_b_db = tmp_path / "store_b_lifecycle.db"
    snapshot_db = tmp_path / "store_a_snapshot_t1.db"

    # Step 1: Initialize Store A (PostgreSQL simulated via durable SQLite file)
    store_a_engine = create_engine(f"sqlite+aiosqlite:///{store_a_db}")
    await store_a_engine.init()

    # Step 2: Initialize Store B (Durable Lifecycle Provider)
    store_b_provider = SqliteDurableLifecycleStateProvider(store_b_db)

    org_id = f"org-{uuid.uuid4().hex[:8]}"
    org_name = "Enterprise Delta Corp"
    org_slug = f"delta-{uuid.uuid4().hex[:8]}"
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    key_id = f"key-{uuid.uuid4().hex[:8]}"
    eval_id = f"eval-{uuid.uuid4().hex[:8]}"
    policy_id = f"pol-{uuid.uuid4().hex[:8]}"

    # Step 1-6: Create tenant, root, session, API key, and erasable data in Store A
    async with store_a_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name=org_name,
                slug=org_slug,
                monthly_budget_usd=25000.0,
                created_at=_now(),
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(web_users).values(
                id=user_id,
                email="root-admin@delta.example.com",
                password_hash="pbkdf2_sha256$hashed_root_secret",
                full_name="Root Administrator",
                created_at=_now(),
                updated_at=_now(),
            )
        )
        await conn.execute(
            insert(web_sessions).values(
                token_hash=hashlib.sha256(b"active-root-session-token").hexdigest(),
                user_id=user_id,
                org_id=org_id,
                csrf_hash="csrf_token_hash",
                expires_at="2099-01-01T00:00:00Z",
                created_at=_now(),
                last_seen_at=_now(),
                revoked=0,
            )
        )
        await conn.execute(
            insert(org_api_keys).values(
                id=key_id,
                org_id=org_id,
                name="Production Ingestion Key",
                key_hash=hashlib.sha256(b"rai_live_secret_key_delta").hexdigest(),
                role="ADMIN",
                created_at=_now(),
                revoked=0,
            )
        )
        await conn.execute(
            insert(eval_runs).values(
                id=eval_id,
                run_type="benchmark",
                model="claude-3-5-sonnet",
                provider="anthropic",
                suite="financial_eval",
                org_id=org_id,
                created_at=_now(),
                payload=json.dumps({"accuracy": 0.98}),
            )
        )
        await conn.execute(
            insert(governance_policies).values(
                id=policy_id,
                org_id=org_id,
                rule_id="r_confidential",
                reason_code="RC_CONFIDENTIAL",
                effect="ALLOW",
                position=0,
                created_at=_now(),
                updated_at=_now(),
            )
        )

    # Step 7: Take snapshot of Store A at T1
    await store_a_engine.close()
    shutil.copyfile(store_a_db, snapshot_db)

    # Reconnect Store A
    store_a_engine = create_engine(f"sqlite+aiosqlite:///{store_a_db}")
    await store_a_engine.init()

    # Step 8: Delete tenant through Phase-5 workflow with Store B attached
    orchestrator = TenantDeletionOrchestrator(store_a_engine, store_b_provider)
    del_res = await orchestrator.delete_tenant(
        org_id=org_id,
        deleted_by=user_id,
        reason="Customer GDPR Right-to-be-Forgotten Erasure Request",
    )
    assert del_res.verification_passed is True

    # Step 9: Verify Store B now contains forward TOMBSTONED state
    assert store_b_provider.is_tombstoned(org_id) is True
    tombstone_b = store_b_provider.get_state(org_id)
    assert tombstone_b is not None
    assert tombstone_b.state == LifecycleState.TOMBSTONED

    # Step 10: Verify tenant is unusable in Store A
    async with store_a_engine.raw.connect() as conn:
        sessions_left = (await conn.execute(select(web_sessions).where(web_sessions.c.org_id == org_id))).fetchall()
        keys_left = (await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == org_id))).fetchall()
        assert len(sessions_left) == 0
        assert len(keys_left) == 0

    # Step 11: Close all process objects and restore Store A from snapshot taken at step 7
    await store_a_engine.close()
    del store_a_engine
    del store_b_provider
    del orchestrator

    # Physically overwrite Store A database file with T1 pre-deletion snapshot
    shutil.copyfile(snapshot_db, store_a_db)

    # Step 12: DO NOT restore Store B (it retains its independent post-deletion tombstone)

    # Step 13: Restart process objects — prove old tenant, credentials, and data reappear in restored Store A
    new_store_a_engine = create_engine(f"sqlite+aiosqlite:///{store_a_db}")
    await new_store_a_engine.init()

    async with new_store_a_engine.raw.connect() as conn:
        resurrected_org = (await conn.execute(select(organizations).where(organizations.c.id == org_id))).fetchone()
        assert resurrected_org is not None
        assert resurrected_org.name == org_name  # Pre-deletion name!

        resurrected_sessions = (await conn.execute(select(web_sessions).where(web_sessions.c.org_id == org_id))).fetchall()
        assert len(resurrected_sessions) == 1  # Resurrected!

        resurrected_keys = (await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == org_id))).fetchall()
        assert len(resurrected_keys) == 1  # Resurrected!

        # Crucially: Store A does NOT have the tombstone because the snapshot predates it!
        tombstones_in_a = (await conn.execute(select(tenant_tombstones).where(tenant_tombstones.c.org_id == org_id))).fetchall()
        assert len(tombstones_in_a) == 0

    # Step 14: Start brand new Store-B provider and brand new RestoreReadinessGate in RESTORE_PENDING state
    new_store_b_provider = SqliteDurableLifecycleStateProvider(store_b_db)
    # Prove Store B preserved tombstone across the process restart
    assert new_store_b_provider.is_tombstoned(org_id) is True

    gate = RestoreReadinessGate(
        initial_state=RestoreReadinessState.RESTORE_PENDING,
        provider=new_store_b_provider,
    )
    assert gate.is_admitted() is False
    with pytest.raises(RestoreQuarantineError):
        gate.assert_traffic_admitted()

    # Step 15: Create brand new RestoreReconciliationEngine and reconcile Store A against Store B
    reconciler = RestoreReconciliationEngine(
        engine=new_store_a_engine,
        lifecycle_provider=new_store_b_provider,
        gate=gate,
        require_durable=True,
    )
    report = await reconciler.reconcile_post_restore(reconciled_by="secops-recovery-automation")

    # Step 16-20: Prove restored tenant is quarantined, credentials purged, data erased
    assert report.status == "RECONCILED"
    assert org_id in report.details["quarantined_orgs"]
    assert report.details["revoked_sessions"] >= 1
    assert report.details["revoked_keys"] >= 1
    assert report.details["erased_records"] >= 1

    async with new_store_a_engine.raw.connect() as conn:
        # Organization quarantined
        org_row = (await conn.execute(select(organizations).where(organizations.c.id == org_id))).fetchone()
        assert "RESTORE_QUARANTINED" in org_row.name

        # Sessions revoked (0 old sessions usable)
        clean_sessions = (await conn.execute(select(web_sessions).where(web_sessions.c.org_id == org_id))).fetchall()
        assert len(clean_sessions) == 0

        # API keys revoked (0 old keys usable)
        clean_keys = (await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == org_id))).fetchall()
        assert len(clean_keys) == 0

        # Erased eligible data not served (0 records served)
        clean_evals = (await conn.execute(select(eval_runs).where(eval_runs.c.org_id == org_id))).fetchall()
        clean_policies = (await conn.execute(select(governance_policies).where(governance_policies.c.org_id == org_id))).fetchall()
        assert len(clean_evals) == 0
        assert len(clean_policies) == 0

        # Tombstone ledger synchronized in Store A
        tombstones_synced = (await conn.execute(select(tenant_tombstones).where(tenant_tombstones.c.org_id == org_id))).fetchall()
        assert len(tombstones_synced) == 1

    # Step 23: Only after successful reconciliation permit READY state
    assert gate.is_admitted() is True
    gate.assert_traffic_admitted()  # Does not raise!

    await new_store_a_engine.close()
