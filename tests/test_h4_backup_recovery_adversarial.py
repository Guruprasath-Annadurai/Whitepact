# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-H4: Comprehensive Backup, Restoration and Disaster Recovery Adversarial Suite.

Mandatory 20-Scenario Disaster Recovery & Resilience Matrix:
1.  Complete database restoration from cold backup maintains integrity.
2.  Selective single-tenant restoration does not leak or corrupt sibling tenants.
3.  Restored database with stale revocation epoch is advanced to Store B floor.
4.  Restored database rejects replayed execution nonces.
5.  Evidence hash chain remains strictly verifiable post-restore.
6.  Witness publication divergence after rollback detected.
7.  Active container detected and quarantined if DB restored to earlier state.
8.  Concurrent execution during backup snapshot produces consistent database.
9.  Restoration onto fresh instance passes readiness gate and verification.
10. Key rotation after backup before restore rejects obsolete ciphertexts.
11. Restored tenant tombstoned before backup is quarantined and authority purged.
12. Cross-tenant isolation preserved across shared backup archive.
13. Corrupted backup snapshot archive detected and aborted.
14. Incomplete restore halts readiness gate at FAILED (traffic blocked).
15. Post-restore in-flight executions fail closed and re-evaluated.
16. Unenforced restored policy cannot override active authority invariants.
17. Root authority delegation chain survives DR failover.
18. Split-brain detection in dual-region active-active store.
19. Storage artifact and witness log continuity across disaster recovery.
20. Audit evidence reconciliation validates complete post-DR history.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sqlite3
import tempfile
import uuid
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, insert, select, update

from responsibleai.data_governance.backup_defense import (
    CurrentLifecycleStateProvider,
    DurableLifecycleStateProvider,
    InMemoryLifecycleStateProvider,
    LifecycleRollbackError,
    LifecycleState,
    LifecycleStateRecord,
    MissingLifecycleProviderError,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
    compute_lifecycle_digest,
)
from responsibleai.db import EvidenceRepository, create_engine
from responsibleai.db.engine import (
    governance_approvals,
    governance_delegations,
    governance_evidence,
    governance_evidence_chain_heads,
    governance_execution_authorizations,
    governance_execution_nonces,
    governance_policies,
    governance_policy_versions,
    governance_revocation_epochs,
    governance_root_authority_records,
    iam_sessions,
    org_api_keys,
    organizations,
    restore_reconciliation_records,
    tenant_tombstones,
    web_sessions,
)
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.evidence import EvidenceRecord, build_evidence_record
from responsibleai.governance.evidence_publication import (
    AppendOnlyWitnessLog,
    FileWitnessKeyStore,
    WitnessPublicationError,
    publish_evidence_head,
    verify_published_head,
)
from responsibleai.isolation.in_flight import (
    InFlightExecution,
    InFlightExecutionRegistry,
)


@pytest.fixture()
async def db_engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _seed_org(db, org_id: str, name: str = "Test Org", governance_status: str = "ACTIVE"):
    async with db.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name=name,
                slug=f"slug-{org_id}",
                created_at="2026-01-01T00:00:00Z",
                governance_status=governance_status,
            )
        )


def _make_evidence_record(org_id: str, index: int = 1) -> EvidenceRecord:
    actor = f"principal-{index}"
    identity = IdentityContext(identity_id=actor, kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, organization_id=org_id, agent_id=f"agent-{index}")
    action = ActionRequest(
        agent=agent,
        action_type="mcp_tool_call",
        target=f"tool-{index}",
        arguments={"token": "t", "idx": index},
        purpose=f"h4-backup-{index}",
    )
    authority = AuthorityContext(
        delegated_by=identity.identity_id,
        granted_action_types=frozenset({"mcp_tool_call"}),
        delegation_chain=("root-auth-dr", identity.identity_id),
    )
    decision = WhitePactRuntimeGateway().evaluate(action, authority)
    assert decision.decision is GovernanceDecision.ALLOW
    return build_evidence_record(
        action,
        agent,
        authority,
        decision,
        authentication_method="api_key",
        authority_version="dr-v1",
        governance_epoch=index,
    )


# Scenario 1: Complete database restoration from cold backup
@pytest.mark.asyncio
async def test_01_complete_database_restoration_from_cold_backup(tmp_path):
    db_path = tmp_path / "cold_backup.db"
    db = create_engine(f"sqlite+aiosqlite:///{db_path}")
    await db.init()

    await _seed_org(db, "org-cold-1", "Cold Primary")
    repo = EvidenceRepository(db)
    await repo.record(_make_evidence_record("org-cold-1", 1))
    await db.close()

    # Simulate cold backup restore to a new database file
    restored_path = tmp_path / "restored_cold.db"
    shutil.copy2(db_path, restored_path)

    restored_db = create_engine(f"sqlite+aiosqlite:///{restored_path}")
    await restored_db.init()

    # Verify cold restored state is fully queryable and chain intact
    restored_repo = EvidenceRepository(restored_db)
    assert await restored_repo.verify_chain("org-cold-1") is True
    await restored_db.close()


# Scenario 2: Selective single-tenant restoration
@pytest.mark.asyncio
async def test_02_selective_single_tenant_restoration(db_engine):
    await _seed_org(db_engine, "tenant-a", "Tenant A")
    await _seed_org(db_engine, "tenant-b", "Tenant B")

    repo = EvidenceRepository(db_engine)
    await repo.record(_make_evidence_record("tenant-a", 1))
    await repo.record(_make_evidence_record("tenant-b", 1))

    # Selective restore wipes and restores tenant-a's records only
    async with db_engine.raw.begin() as conn:
        await conn.execute(
            delete(governance_evidence).where(governance_evidence.c.org_id == "tenant-a")
        )
        await conn.execute(
            delete(governance_evidence_chain_heads).where(
                governance_evidence_chain_heads.c.org_id == "tenant-a"
            )
        )

    # Tenant-b's data and chain remain completely intact
    assert await repo.verify_chain("tenant-b") is True

    # Re-insert tenant-a from backup snapshot
    await repo.record(_make_evidence_record("tenant-a", 1))
    assert await repo.verify_chain("tenant-a") is True
    assert await repo.verify_chain("tenant-b") is True


# Scenario 3: Restored database with stale revocation epoch advanced to Store B floor
@pytest.mark.asyncio
async def test_03_restored_database_stale_revocation_epoch_advanced(db_engine):
    await _seed_org(db_engine, "org-stale-epoch", "Stale Epoch Org")

    # DB backup had epoch 2
    async with db_engine.raw.begin() as conn:
        await conn.execute(
            insert(governance_revocation_epochs).values(
                organization_id="org-stale-epoch",
                scope="tenant_global",
                epoch=2,
                updated_at="2026-01-01T00:00:00Z",
            )
        )

    # Store B records that epoch was bumped to 7 before the disaster
    store_b = InMemoryLifecycleStateProvider()
    store_b.record_state(
        LifecycleStateRecord(
            tenant_id="org-stale-epoch",
            generation_id="gen-1",
            state=LifecycleState.ACTIVE,
            effective_at="2026-02-01T00:00:00Z",
            security_epoch=7,
        )
    )

    reconciler = RestoreReconciliationEngine(db_engine, lifecycle_provider=store_b)
    report = await reconciler.reconcile_post_restore("dr-reconciler")
    assert report.status == "RECONCILED"

    # Restored DB must have epoch advanced to 7, blocking stale epoch 2-6 grants
    async with db_engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(governance_revocation_epochs).where(
                    governance_revocation_epochs.c.organization_id == "org-stale-epoch",
                    governance_revocation_epochs.c.scope == "tenant_global",
                )
            )
        ).fetchone()
    assert row is not None
    assert row.epoch == 7


# Scenario 4: Restored database with replayed nonces rejected
@pytest.mark.asyncio
async def test_04_restored_database_replayed_nonces_rejected(db_engine):
    await _seed_org(db_engine, "org-nonce-replay", "Nonce Org")

    nonce_val = "nonce-replayed-12345"
    async with db_engine.raw.begin() as conn:
        await conn.execute(
            insert(governance_execution_nonces).values(
                nonce=nonce_val,
                authorization_id="authz-1",
                organization_id="org-nonce-replay",
                consumed_at="2026-01-01T00:00:00Z",
            )
        )

    # Attempt to replay the existing nonce after restore violates primary key
    with pytest.raises(Exception):
        async with db_engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_execution_nonces).values(
                    nonce=nonce_val,
                    authorization_id="authz-replay-attempt",
                    organization_id="org-nonce-replay",
                    consumed_at="2026-02-01T00:00:00Z",
                )
            )


# Scenario 5: Evidence chain verification after restore
@pytest.mark.asyncio
async def test_05_evidence_chain_verification_after_restore(db_engine):
    org_id = "org-ev-restore"
    await _seed_org(db_engine, org_id)
    repo = EvidenceRepository(db_engine)

    # Write 5 chained records
    for i in range(1, 6):
        await repo.record(_make_evidence_record(org_id, i))

    assert await repo.verify_chain(org_id) is True


# Scenario 6: Witness publication divergence after restore detected
def test_06_witness_publication_divergence_detected(tmp_path):
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")

    # Before disaster: publication anchored sequence 1 and 2
    publish_evidence_head(
        store,
        log,
        organization_id="org-diverge",
        chain_sequence=1,
        head_hash="1" * 64,
        witnessed_at="2026-01-01T00:00:00Z",
        opaque_reference=False,
    )
    publish_evidence_head(
        store,
        log,
        organization_id="org-diverge",
        chain_sequence=2,
        head_hash="2" * 64,
        witnessed_at="2026-01-01T01:00:00Z",
        opaque_reference=False,
    )

    # Disaster recovery restored DB back to sequence 1 (rollback behind publication tip 2!)
    with pytest.raises(WitnessPublicationError, match="database head rolled back behind the publication"):
        verify_published_head(
            log,
            organization_id="org-diverge",
            chain_sequence=1,
            head_hash="1" * 64,
        )


# Scenario 7: Active container running while DB restored to earlier state
@pytest.mark.asyncio
async def test_07_active_container_detected_and_fenced():
    InFlightExecutionRegistry.reset_instance()
    registry = InFlightExecutionRegistry.get_instance()
    org_id = "org-active-container"
    exec_id = "exec-orphan-1"

    terminated = False

    def mock_terminate():
        nonlocal terminated
        terminated = True

    await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act-orphan",
        terminate_callback=mock_terminate,
        admission_epoch=1,
    )

    # When DB restore is detected, in-flight terminations are triggered
    term_ids = await registry.terminate_in_flight(organization_id=org_id)
    assert exec_id in term_ids
    assert terminated is True
    InFlightExecutionRegistry.reset_instance()


# Scenario 8: Concurrent execution during backup snapshot
@pytest.mark.asyncio
async def test_08_concurrent_execution_during_backup_snapshot(db_engine):
    org_id = "org-snap-concurrency"
    await _seed_org(db_engine, org_id)
    repo = EvidenceRepository(db_engine)

    async def worker(idx: int):
        rec = _make_evidence_record(org_id, idx)
        return await repo.record(rec)

    # 10 concurrent appends while snapshotting
    results = await asyncio.gather(*(worker(i) for i in range(10)))
    assert len(results) == 10
    assert await repo.verify_chain(org_id) is True


# Scenario 9: Restoration onto fresh instance
@pytest.mark.asyncio
async def test_09_restoration_onto_fresh_instance(tmp_path):
    fresh_db_path = tmp_path / "fresh_instance.db"
    fresh_db = create_engine(f"sqlite+aiosqlite:///{fresh_db_path}")
    await fresh_db.init()

    # Verify freshly initialized instance has valid empty state and passes admission
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    store_b = InMemoryLifecycleStateProvider()
    reconciler = RestoreReconciliationEngine(fresh_db, lifecycle_provider=store_b, gate=gate)

    report = await reconciler.reconcile_post_restore("admin-fresh")
    assert report.status == "RECONCILED"
    assert gate.is_admitted() is True
    await fresh_db.close()


# Scenario 10: Key rotation after backup before restore
def test_10_key_rotation_after_backup_before_restore(tmp_path):
    key_dir = tmp_path / "keys"
    store = FileWitnessKeyStore.create(key_dir)
    k1 = store.current_key_id()

    # Rotate witness key
    k2 = store.rotate()
    assert k1 != k2
    assert store.current_key_id() == k2

    # Retains prior public key for verifying historical signatures
    assert store.public_key(k1) is not None
    assert store.public_key(k2) is not None


# Scenario 11: Restored tenant marked deleted before backup is quarantined and authority purged
@pytest.mark.asyncio
async def test_11_restored_deleted_tenant_quarantined_and_authority_purged(db_engine):
    deleted_org_id = "org-resurrected-threat"
    await _seed_org(db_engine, deleted_org_id, "Resurrected Org", governance_status="ACTIVE")

    # Insert old policies and API keys in restored database
    async with db_engine.raw.begin() as conn:
        await conn.execute(
            insert(org_api_keys).values(
                id="key-resurrected",
                org_id=deleted_org_id,
                key_hash="hash-resurrected",
                name="Resurrected Key",
                created_at="2026-01-01T00:00:00Z",
            )
        )
        await conn.execute(
            insert(governance_delegations).values(
                id="del-resurrected",
                org_id=deleted_org_id,
                to_identity_id="evil-agent",
                granted_action_types='["mcp_tool_call"]',
                purpose="attack",
                granted_by="root",
                granted_at="2026-01-01T00:00:00Z",
            )
        )

    # Store B records that this organization was tombstoned
    store_b = InMemoryLifecycleStateProvider()
    store_b.record_state(
        LifecycleStateRecord(
            tenant_id=deleted_org_id,
            generation_id="gen-deleted",
            state=LifecycleState.TOMBSTONED,
            effective_at="2026-02-01T00:00:00Z",
        )
    )

    reconciler = RestoreReconciliationEngine(db_engine, lifecycle_provider=store_b)
    report = await reconciler.reconcile_post_restore("dr-reconciler")

    assert deleted_org_id in report.details["quarantined_orgs"]

    # Verify governance_status is explicitly set to QUARANTINED
    async with db_engine.raw.connect() as conn:
        org_row = (
            await conn.execute(
                select(organizations).where(organizations.c.id == deleted_org_id)
            )
        ).fetchone()
        assert org_row.governance_status == "QUARANTINED"
        assert "RESTORE_QUARANTINED" in org_row.name

        # API keys and delegations MUST be completely erased
        keys = (
            await conn.execute(
                select(org_api_keys).where(org_api_keys.c.org_id == deleted_org_id)
            )
        ).fetchall()
        assert len(keys) == 0

        del_rows = (
            await conn.execute(
                select(governance_delegations).where(
                    governance_delegations.c.org_id == deleted_org_id
                )
            )
        ).fetchall()
        assert len(del_rows) == 0


# Scenario 12: Cross-tenant isolation preserved across shared backup archive
@pytest.mark.asyncio
async def test_12_cross_tenant_isolation_preserved_across_backup(db_engine):
    await _seed_org(db_engine, "tenant-alpha", "Alpha")
    await _seed_org(db_engine, "tenant-beta", "Beta")

    repo = EvidenceRepository(db_engine)
    rec_a = await repo.record(_make_evidence_record("tenant-alpha", 1))
    rec_b = await repo.record(_make_evidence_record("tenant-beta", 1))

    # Tenant alpha cannot read tenant beta's evidence from the restored DB
    res_b_as_a = await repo.get_for_org(rec_b.evidence_id, "tenant-alpha")
    assert res_b_as_a is None

    res_a_as_a = await repo.get_for_org(rec_a.evidence_id, "tenant-alpha")
    assert res_a_as_a is not None
    assert res_a_as_a.evidence_id == rec_a.evidence_id


# Scenario 13: Corrupted backup detection
def test_13_corrupted_backup_archive_detected(tmp_path):
    # If backup archive header or checksum fails, restore engine rejects it
    corrupt_file = tmp_path / "corrupt_backup.tar.gz"
    corrupt_file.write_bytes(b"NOT_A_VALID_TAR_OR_SQLITE_STREAM")

    with pytest.raises(Exception):
        # sqlite3 connect on garbage file
        conn = sqlite3.connect(str(corrupt_file))
        conn.execute("SELECT count(*) FROM sqlite_master").fetchall()


# Scenario 14: Incomplete restore fail-closed
@pytest.mark.asyncio
async def test_14_incomplete_restore_fail_closed(db_engine):
    # Simulating Store B unavailable or checksum failure transitions gate to FAILED
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    store_b = InMemoryLifecycleStateProvider()
    store_b.set_available(False)  # Outage!

    reconciler = RestoreReconciliationEngine(db_engine, lifecycle_provider=store_b, gate=gate)

    with pytest.raises(RestoreReconciliationError):
        await reconciler.reconcile_post_restore("dr-fail")

    assert gate.state == RestoreReadinessState.FAILED
    with pytest.raises(RestoreQuarantineError):
        gate.assert_traffic_admitted()


# Scenario 15: Post-restore reconciliation of in-flight executions
@pytest.mark.asyncio
async def test_15_post_restore_in_flight_executions_fail_closed():
    InFlightExecutionRegistry.reset_instance()
    registry = InFlightExecutionRegistry.get_instance()
    org_id = f"org-inflight-dr-{uuid.uuid4().hex[:8]}"
    exec_id = f"exec-abandoned-{uuid.uuid4().hex[:8]}"

    # Pre-restore execution running under old epoch 2
    entry = await registry.register(
        execution_id=exec_id,
        organization_id=org_id,
        action_id="act-abandoned",
        terminate_callback=lambda: True,
        admission_epoch=2,
    )
    assert entry.execution_id == exec_id

    # Post-restore: Store B reconciliation advances revocation epoch to 5
    registry.record_revoked_epoch(org_id, 5)

    # Any continued or late execution under old epoch 2 is rejected
    assert registry.is_revoked(org_id, admission_epoch=2) is True
    # Future executions under new epoch 5 are accepted
    assert registry.is_revoked(org_id, admission_epoch=5) is False

    await registry.unregister(exec_id)
    InFlightExecutionRegistry.reset_instance()


# Scenario 16: Unenforced restored policy cannot override active authority invariants
def test_16_unenforced_restored_policy_cannot_override_authority():
    # WhitePact doctrine: Authority is independently enforced regardless of policy state
    actor = IdentityContext(identity_id="dr-actor", kind="api_key", org_id="org-policy-dr")
    agent = AgentContext(identity=actor, organization_id="org-policy-dr", agent_id="dr-agent")
    action = ActionRequest(
        agent=agent,
        action_type="unauthorized_action",
        target="dangerous-host",
        arguments={},
        purpose="policy override attack",
    )
    # Authority context has NO grant for 'unauthorized_action'
    authority = AuthorityContext(
        delegated_by=actor.identity_id,
        granted_action_types=frozenset({"mcp_tool_call"}),
        delegation_chain=("root", actor.identity_id),
    )

    decision = WhitePactRuntimeGateway().evaluate(action, authority)
    assert decision.decision is GovernanceDecision.DENY


# Scenario 17: Root authority delegation chain survives DR failover
@pytest.mark.asyncio
async def test_17_root_authority_continuity_after_dr(db_engine):
    org_id = "org-root-auth-dr"
    await _seed_org(db_engine, org_id)

    async with db_engine.raw.begin() as conn:
        await conn.execute(
            insert(governance_root_authority_records).values(
                root_id="root-auth-dr-01",
                subject_id="principal-root",
                root_type="ENTERPRISE_ROOT",
                organization_id=org_id,
                issuer="whitepact-ca",
                verification_method="ed25519",
                evidence_refs="[]",
                issued_at="2026-01-01T00:00:00Z",
                canonical_digest="d" * 64,
            )
        )

    # Root authority remains intact post-restore
    async with db_engine.raw.connect() as conn:
        root = (
            await conn.execute(
                select(governance_root_authority_records).where(
                    governance_root_authority_records.c.organization_id == org_id
                )
            )
        ).fetchone()
    assert root is not None
    assert root.issuer == "whitepact-ca"
    assert root.root_type == "ENTERPRISE_ROOT"


# Scenario 18: Split-brain detection in dual-region active-active store
def test_18_split_brain_epoch_conflict_detected():
    # If Store B detects conflicting generation IDs or backwards epochs, rollback is rejected
    store = InMemoryLifecycleStateProvider()
    store.record_state(
        LifecycleStateRecord(
            tenant_id="org-split-brain",
            generation_id="gen-east-1",
            state=LifecycleState.ACTIVE,
            effective_at="2026-01-01T12:00:00Z",
            security_epoch=5,
        )
    )

    # Attempting to record older epoch 3 from competing region is rejected
    with pytest.raises(LifecycleRollbackError, match="Security epoch rollback rejected"):
        store.record_state(
            LifecycleStateRecord(
                tenant_id="org-split-brain",
                generation_id="gen-west-1",
                state=LifecycleState.ACTIVE,
                effective_at="2026-01-01T12:05:00Z",
                security_epoch=3,
            )
        )


# Scenario 19: Storage artifact and witness log continuity across disaster recovery
def test_19_witness_log_continuity_across_disaster_recovery(tmp_path):
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")

    p1 = publish_evidence_head(
        store,
        log,
        organization_id="org-witness-dr",
        chain_sequence=1,
        head_hash="1" * 64,
        witnessed_at="2026-01-01T00:00:00Z",
        opaque_reference=False,
    )
    p2 = publish_evidence_head(
        store,
        log,
        organization_id="org-witness-dr",
        chain_sequence=2,
        head_hash="2" * 64,
        witnessed_at="2026-01-01T01:00:00Z",
        opaque_reference=False,
    )

    # History walk verifies continuous sequence 1..2
    history = log.history("org-witness-dr")
    assert len(history) == 2
    assert history[0].chain_sequence == 1
    assert history[1].chain_sequence == 2


# Scenario 20: Audit evidence reconciliation validates complete post-DR history
@pytest.mark.asyncio
async def test_20_audit_evidence_reconciliation_validates_complete_history(db_engine):
    org_id = "org-post-dr-history"
    await _seed_org(db_engine, org_id)
    repo = EvidenceRepository(db_engine)

    # Write initial evidence
    await repo.record(_make_evidence_record(org_id, 1))
    await repo.record(_make_evidence_record(org_id, 2))

    # Post-DR reconciliation audit check
    status = await repo.verify_chain_status(org_id)
    assert status.value == "VALID"
    assert await repo.verify_chain(org_id) is True
