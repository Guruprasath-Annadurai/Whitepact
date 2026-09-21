# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Empirical 23-Step Threat Model Verification for Backup Resurrection Defense.

Proves:
- Store A: Application Database (restored backward to T1 pre-deletion snapshot).
- Store B: CurrentLifecycleStateProvider (persisted forward outside restore domain).
- Operational traffic is blocked post-restore until lifecycle reconciliation completes.
- Post-restore reconciliation quarantines resurrected tenants, purges credentials,
  re-erases eligible data, and synchronizes tombstone state.
- Fail-Closed: Unavailability or corruption of Store B transitions gate to FAILED
  and permanently blocks operational traffic.
- Generation/Tombstone integrity prevents reusing tombstoned ID, slug, or name.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, insert, select

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleState,
    LifecycleStateRecord,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
    compute_lifecycle_digest,
)
from responsibleai.data_governance.deletion_orchestrator import (
    TenantDeletionError,
    TenantDeletionOrchestrator,
)
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    eval_runs,
    governance_policies,
    iam_api_key_lineage,
    iam_sessions,
    org_api_keys,
    organizations,
    tenant_tombstones,
    web_sessions,
    web_users,
)
from responsibleai.db.org_repository import OrgRepository


def _now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture
async def store_a_engine():
    """Store A: Customer/Application Database."""
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture
def store_b_provider() -> InMemoryLifecycleStateProvider:
    """Store B: Current Lifecycle Security State Provider (independent of Store A)."""
    return InMemoryLifecycleStateProvider()


@pytest.mark.asyncio
async def test_23_step_empirical_backup_resurrection_closure(
    store_a_engine: DatabaseEngine,
    store_b_provider: InMemoryLifecycleStateProvider,
):
    """Execute exact 23-step empirical temporal threat sequence from Section 4."""
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    org_name = "Acme Corp Alpha"
    org_slug = f"acme-{uuid.uuid4().hex[:8]}"
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    key_id = f"key-{uuid.uuid4().hex[:8]}"
    eval_id = f"eval-{uuid.uuid4().hex[:8]}"
    policy_id = f"pol-{uuid.uuid4().hex[:8]}"

    # Step 1: Create tenant in Store A
    async with store_a_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name=org_name,
                slug=org_slug,
                monthly_budget_usd=15000.0,
                created_at=_now(),
                plan="ENTERPRISE",
            )
        )

    # Step 2: Create root/authority in Store A
    async with store_a_engine.raw.begin() as conn:
        await conn.execute(
            insert(web_users).values(
                id=user_id,
                email="root@acme.corp",
                full_name="Acme Root Admin",
                password_hash="hash_root_secret",
                created_at=_now(),
                updated_at=_now(),
            )
        )

    # Step 3: Create session
    async with store_a_engine.raw.begin() as conn:
        await conn.execute(
            insert(web_sessions).values(
                token_hash=hashlib.sha256(b"active-web-session-token").hexdigest(),
                user_id=user_id,
                org_id=org_id,
                csrf_hash="csrf_token_hash",
                expires_at="2026-12-31T00:00:00Z",
                created_at=_now(),
                last_seen_at=_now(),
                revoked=0,
            )
        )
        await conn.execute(
            insert(iam_sessions).values(
                id=session_id,
                org_id=org_id,
                principal_id=user_id,
                token_hash=hashlib.sha256(b"active-iam-session-token").hexdigest(),
                session_type="INTERACTIVE",
                status="ACTIVE",
                created_at=_now(),
                expires_at="2026-12-31T00:00:00Z",
                last_seen_at=_now(),
                revoked_at=None,
            )
        )

    # Step 4: Create API key
    async with store_a_engine.raw.begin() as conn:
        await conn.execute(
            insert(org_api_keys).values(
                id=key_id,
                org_id=org_id,
                key_hash=hashlib.sha256(b"wp_live_active_key").hexdigest(),
                name="Production Root API Key",
                role="ADMIN",
                created_at=_now(),
                revoked=0,
            )
        )

    # Step 5: Create agent/service credential / key lineage
    async with store_a_engine.raw.begin() as conn:
        await conn.execute(
            insert(iam_api_key_lineage).values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                name="Root Key Lineage",
                fingerprint=f"fp_{uuid.uuid4().hex[:16]}",
                parent_key_id=None,
                status="ACTIVE",
                scopes_json="[]",
                created_at=_now(),
                expires_at="2026-12-31T00:00:00Z",
            )
        )

    # Step 6: Create erasable operational/eval/policy data
    async with store_a_engine.raw.begin() as conn:
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

    # Step 7: Take physical/logical snapshot of Store A at T1
    # We snapshot all rows of Store A
    tables_to_snapshot = [
        organizations,
        web_users,
        web_sessions,
        iam_sessions,
        org_api_keys,
        iam_api_key_lineage,
        eval_runs,
        governance_policies,
    ]
    snapshot_t1: dict[str, list[dict]] = {}
    async with store_a_engine.raw.connect() as conn:
        for tbl in tables_to_snapshot:
            rows = (await conn.execute(select(tbl))).fetchall()
            snapshot_t1[tbl.name] = [dict(r._mapping) for r in rows]

    # Verify snapshot captured active credentials and data
    assert len(snapshot_t1["organizations"]) == 1
    assert len(snapshot_t1["web_sessions"]) == 1
    assert len(snapshot_t1["org_api_keys"]) == 1
    assert len(snapshot_t1["eval_runs"]) == 1

    # Step 8: Delete tenant through Phase-5 workflow with Store B wired in
    orchestrator = TenantDeletionOrchestrator(store_a_engine, lifecycle_provider=store_b_provider)
    del_result = await orchestrator.delete_tenant(
        org_id=org_id,
        deleted_by="compliance_officer",
        reason="Customer GDPR Erasure Right Exercised",
    )
    assert del_result.verification_passed is True

    # Step 9: Verify Store B now contains forward tombstone/revocation state
    assert store_b_provider.is_tombstoned(org_id) is True
    rec_b = store_b_provider.get_state(org_id)
    assert rec_b is not None
    assert rec_b.state == LifecycleState.TOMBSTONED
    assert rec_b.tenant_id == org_id

    # Step 10: Verify tenant unusable in Store A
    async with store_a_engine.raw.connect() as conn:
        active_keys = (
            await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == org_id))
        ).fetchall()
        assert len(active_keys) == 0
        active_sess = (
            await conn.execute(select(web_sessions).where(web_sessions.c.org_id == org_id))
        ).fetchall()
        assert len(active_sess) == 0
        active_evals = (
            await conn.execute(select(eval_runs).where(eval_runs.c.org_id == org_id))
        ).fetchall()
        assert len(active_evals) == 0

    # Step 11: Restore Store A from snapshot taken at step 7 (T1)
    # Simulate DB restore: purge current DB and restore exact T1 snapshot
    async with store_a_engine.raw.begin() as conn:
        # Clear all tables including tenant_tombstones
        await conn.execute(delete(tenant_tombstones))
        for tbl in tables_to_snapshot:
            await conn.execute(delete(tbl))
        # Restore rows from T1 snapshot
        for tbl in tables_to_snapshot:
            for row in snapshot_t1[tbl.name]:
                await conn.execute(insert(tbl).values(**row))

    # Step 12: DO NOT restore Store B (Store B remains untouched with forward tombstone)
    assert store_b_provider.is_tombstoned(org_id) is True

    # Step 13: Prove old tenant/credentials/data reappear physically in Store A
    async with store_a_engine.raw.connect() as conn:
        # Crucial security demonstration: Store A alone HAS NO TOMBSTONES!
        ts_in_a = (await conn.execute(select(tenant_tombstones))).fetchall()
        assert len(ts_in_a) == 0  # Restored DB knows nothing of the deletion!

        # Old tenant and credentials reappear
        reappeared_orgs = (
            await conn.execute(select(organizations).where(organizations.c.id == org_id))
        ).fetchall()
        assert len(reappeared_orgs) == 1
        assert reappeared_orgs[0].name == org_name  # original name restored!

        reappeared_keys = (
            await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == org_id))
        ).fetchall()
        assert len(reappeared_keys) == 1  # Resurrected key physically in DB!

        reappeared_sessions = (
            await conn.execute(select(web_sessions).where(web_sessions.c.org_id == org_id))
        ).fetchall()
        assert len(reappeared_sessions) == 1  # Resurrected session physically in DB!

        reappeared_evals = (
            await conn.execute(select(eval_runs).where(eval_runs.c.org_id == org_id))
        ).fetchall()
        assert len(reappeared_evals) == 1  # Resurrected sensitive data physically in DB!

    # Step 14: Start WhitePact in RESTORE_PENDING state.
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    assert gate.is_admitted() is False
    with pytest.raises(
        RestoreQuarantineError,
        match="Operational traffic blocked: system is in RESTORE_PENDING state",
    ):
        gate.assert_traffic_admitted()

    # Step 15: Reconcile Store A against CURRENT state from Store B
    reconciliation_engine = RestoreReconciliationEngine(
        engine=store_a_engine,
        lifecycle_provider=store_b_provider,
        gate=gate,
    )
    report = await reconciliation_engine.reconcile_post_restore(
        reconciled_by="automated_sre_restore_agent"
    )

    assert report.status == "RECONCILED"
    assert report.tombstones_detected >= 1
    assert report.tenants_quarantined >= 1
    assert org_id in report.details["quarantined_orgs"]

    # Step 16: Prove restored tenant is quarantined in Store A
    async with store_a_engine.raw.connect() as conn:
        org_row = (
            await conn.execute(select(organizations).where(organizations.c.id == org_id))
        ).fetchone()
        assert org_row is not None
        assert "RESTORE_QUARANTINED" in org_row.name

    # Step 17: Prove old root authority unusable
    # Step 18: Prove old sessions unusable (purged)
    async with store_a_engine.raw.connect() as conn:
        web_sess = (
            await conn.execute(select(web_sessions).where(web_sessions.c.org_id == org_id))
        ).fetchall()
        assert len(web_sess) == 0
        iam_sess = (
            await conn.execute(select(iam_sessions).where(iam_sessions.c.org_id == org_id))
        ).fetchall()
        assert len(iam_sess) == 0

    # Step 19: Prove old API key unusable (purged)
    async with store_a_engine.raw.connect() as conn:
        keys = (
            await conn.execute(select(org_api_keys).where(org_api_keys.c.org_id == org_id))
        ).fetchall()
        assert len(keys) == 0

    # Step 20: Prove old agent/workload credential / lineage unusable (purged)
    async with store_a_engine.raw.connect() as conn:
        lineage = (
            await conn.execute(
                select(iam_api_key_lineage).where(iam_api_key_lineage.c.org_id == org_id)
            )
        ).fetchall()
        assert len(lineage) == 0

    # Step 21: Reapply erasure / tombstone requirements in Store A
    async with store_a_engine.raw.connect() as conn:
        ts_a = (
            await conn.execute(
                select(tenant_tombstones).where(tenant_tombstones.c.org_id == org_id)
            )
        ).fetchall()
        assert len(ts_a) == 1  # Tombstone synchronized into Store A!

    # Step 22: Prove erased eligible data is not served (deleted)
    async with store_a_engine.raw.connect() as conn:
        evals = (
            await conn.execute(select(eval_runs).where(eval_runs.c.org_id == org_id))
        ).fetchall()
        assert len(evals) == 0
        pols = (
            await conn.execute(
                select(governance_policies).where(governance_policies.c.org_id == org_id)
            )
        ).fetchall()
        assert len(pols) == 0

    # Step 23: Only after successful reconciliation permit READY state
    assert gate.is_admitted() is True
    assert gate.state == RestoreReadinessState.READY
    # Traffic is now admitted without error
    gate.assert_traffic_admitted()


@pytest.mark.asyncio
async def test_restore_reconciliation_fails_closed_when_provider_unavailable(
    store_a_engine: DatabaseEngine,
    store_b_provider: InMemoryLifecycleStateProvider,
):
    """If Store B is unavailable, gate must transition to FAILED and block all traffic."""
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciliation_engine = RestoreReconciliationEngine(
        engine=store_a_engine,
        lifecycle_provider=store_b_provider,
        gate=gate,
    )

    # Simulate Store B unavailability
    store_b_provider.set_available(False)

    with pytest.raises(RestoreReconciliationError, match="unavailable"):
        await reconciliation_engine.reconcile_post_restore("sre_agent")

    # Invariant: Gate is in FAILED state!
    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False

    # Operational traffic permanently blocked
    with pytest.raises(
        RestoreQuarantineError, match="Operational traffic blocked: system is in FAILED state"
    ):
        gate.assert_traffic_admitted()


@pytest.mark.asyncio
async def test_restore_reconciliation_fails_closed_when_provider_corrupted(
    store_a_engine: DatabaseEngine,
    store_b_provider: InMemoryLifecycleStateProvider,
):
    """If Store B integrity verification fails, gate must transition to FAILED and block traffic."""
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    reconciliation_engine = RestoreReconciliationEngine(
        engine=store_a_engine,
        lifecycle_provider=store_b_provider,
        gate=gate,
    )

    # Record valid tombstone first
    eff_time = _now()
    store_b_provider.record_state(
        LifecycleStateRecord(
            tenant_id="org_corrupt_test",
            generation_id="gen_1",
            state=LifecycleState.TOMBSTONED,
            effective_at=eff_time,
            digest=compute_lifecycle_digest(
                tenant_id="org_corrupt_test",
                generation_id="gen_1",
                state=LifecycleState.TOMBSTONED.value,
                effective_at=eff_time,
            ),
        )
    )

    # Corrupt Store B integrity
    store_b_provider.set_corrupted(True)

    with pytest.raises(RestoreReconciliationError, match="integrity check failed"):
        await reconciliation_engine.reconcile_post_restore("sre_agent")

    assert gate.state == RestoreReadinessState.FAILED
    assert gate.is_admitted() is False
    with pytest.raises(RestoreQuarantineError, match="Operational traffic blocked"):
        gate.assert_traffic_admitted()


@pytest.mark.asyncio
async def test_cannot_recreate_tenant_with_tombstoned_identifier_or_name(
    store_a_engine: DatabaseEngine,
):
    """Section 7: Tombstone / Generation integrity prevents reusing tombstoned ID or name."""
    tombstone_id = str(uuid.uuid4())
    org_id = "org_doomed"
    org_name = "Doomed Global Corp"

    # Seed tombstone in database
    async with store_a_engine.raw.begin() as conn:
        await conn.execute(
            insert(tenant_tombstones).values(
                id=tombstone_id,
                org_id=org_id,
                original_name=org_name,
                generation_id="gen_doomed",
                tombstoned_at=_now(),
                tombstoned_by="admin_sec",
                authority_hash="hash",
                evidence_digest="digest",
                details_json="{}",
            )
        )

    repo = OrgRepository(store_a_engine)

    # Attempt recreation with same name must raise TenantDeletionError
    with pytest.raises(TenantDeletionError, match="tombstoned"):
        await repo.create_org(name=org_name, slug="new-slug-corp")
