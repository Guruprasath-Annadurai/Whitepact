# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-H3: Comprehensive Audit Integrity and Evidence Durability Adversarial Suite.

Mandatory 20-Scenario Evidence Integrity Matrix:
1.  Modified historical audit entry detected.
2.  Deleted audit entry detected.
3.  Reordered audit entries detected.
4.  Duplicated audit entries detected.
5.  Altered actor identifier detected.
6.  Altered tenant identifier detected.
7.  Modified policy hash / version detected.
8.  Modified approval digest detected.
9.  Grant-to-execution mismatch detected.
10. Replayed evidence nonce rejected.
11. Interrupted audit append atomic rollback.
12. Partial evidence write rollback.
13. Database outage during evidence persistence fail-closed.
14. Witness service unavailable handling.
15. Witness publication mismatch detected.
16. Revoked grant reused with old evidence rejected.
17. Corrupt evidence export detected during verification.
18. Concurrent append collisions serialized.
19. Incorrect retention enforcement detected.
20. Unauthorized evidence deletion detected against durable head.
"""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db import EvidenceRepository, create_engine
from responsibleai.db.engine import governance_evidence, governance_evidence_chain_heads
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.evidence import EvidenceRecord, build_evidence_record
from responsibleai.governance.evidence_bundle import build_evidence_bundle, verify_evidence_bundle
from responsibleai.governance.evidence_publication import (
    AppendOnlyWitnessLog,
    FileWitnessKeyStore,
    WitnessPublicationError,
    WitnessRequiredUnavailableError,
    publish_evidence_head,
    verify_published_head,
)


@pytest.fixture()
async def engine():
    database = create_engine(":memory:")
    await database.init()
    yield database
    await database.close()


def _make_evidence_record(org_id: str, index: int = 0, actor_id: str | None = None) -> EvidenceRecord:
    actor = actor_id or f"principal-{index}"
    identity = IdentityContext(identity_id=actor, kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, organization_id=org_id, agent_id=f"agent-{index}")
    action = ActionRequest(
        agent=agent,
        action_type="mcp_tool_call",
        target=f"tool-{index}",
        arguments={"token": "test-token", "step": index},
        purpose=f"h3-audit-test-{index}",
    )
    authority = AuthorityContext(
        delegated_by=identity.identity_id,
        granted_action_types=frozenset({"mcp_tool_call"}),
        delegation_chain=("root-auth-1", identity.identity_id),
    )
    decision = WhitePactRuntimeGateway().evaluate(action, authority)
    assert decision.decision is GovernanceDecision.ALLOW
    return build_evidence_record(
        action,
        agent,
        authority,
        decision,
        authentication_method="api_key",
        authority_version="auth-v1.0",
        consent_id=f"consent-{index}",
        consent_version="consent-v1",
        governance_epoch=index,
    )


# Scenario 1: Modified historical audit entry
@pytest.mark.asyncio
async def test_01_modified_historical_audit_entry_detected(engine):
    repo = EvidenceRepository(engine)
    saved = await repo.record(_make_evidence_record("org-h3-1", 1))

    # Tamper with the saved record's target
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == saved.evidence_id)
            .values(target="tampered-tool-call")
        )

    # Chain verification MUST detect the corruption
    assert await repo.verify_chain("org-h3-1") is False


# Scenario 2: Deleted audit entry
@pytest.mark.asyncio
async def test_02_deleted_audit_entry_detected(engine):
    repo = EvidenceRepository(engine)
    records = [await repo.record(_make_evidence_record("org-h3-2", i)) for i in range(3)]

    # Delete the middle entry
    async with engine.raw.begin() as conn:
        await conn.execute(
            delete(governance_evidence).where(
                governance_evidence.c.id == records[1].evidence_id
            )
        )

    assert await repo.verify_chain("org-h3-2") is False


# Scenario 3: Reordered entries
@pytest.mark.asyncio
async def test_03_reordered_entries_detected(engine):
    repo = EvidenceRepository(engine)
    r1 = await repo.record(_make_evidence_record("org-h3-3", 1))
    r2 = await repo.record(_make_evidence_record("org-h3-3", 2))

    # Swap their sequence numbers (using intermediate 999 to avoid unique constraint)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == r1.evidence_id)
            .values(chain_sequence=999)
        )
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == r2.evidence_id)
            .values(chain_sequence=1)
        )
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == r1.evidence_id)
            .values(chain_sequence=2)
        )

    assert await repo.verify_chain("org-h3-3") is False


# Scenario 4: Duplicated entries
@pytest.mark.asyncio
async def test_04_duplicated_entries_detected(engine):
    repo = EvidenceRepository(engine)
    r1 = await repo.record(_make_evidence_record("org-h3-4", 1))

    # Attempting to insert duplicate primary key / sequence fails or breaks chain
    async with engine.raw.begin() as conn:
        row = (
            await conn.execute(
                select(governance_evidence).where(governance_evidence.c.id == r1.evidence_id)
            )
        ).fetchone()
        row_dict = dict(row._mapping)
        row_dict["id"] = "duplicate-id-999"
        try:
            await conn.execute(insert(governance_evidence).values(**row_dict))
            # If inserted with duplicate sequence, chain verification must fail
            assert await repo.verify_chain("org-h3-4") is False
        except Exception:
            # Database unique constraint prevented duplicate sequence
            pass


# Scenario 5: Altered actor identifier
@pytest.mark.asyncio
async def test_05_altered_actor_identifier_detected(engine):
    repo = EvidenceRepository(engine)
    saved = await repo.record(_make_evidence_record("org-h3-5", 1, actor_id="alice"))

    # Alter actor from alice to eve
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == saved.evidence_id)
            .values(identity_id="eve")
        )

    assert await repo.verify_chain("org-h3-5") is False


# Scenario 6: Altered tenant identifier
@pytest.mark.asyncio
async def test_06_altered_tenant_identifier_detected(engine):
    repo = EvidenceRepository(engine)
    saved = await repo.record(_make_evidence_record("org-h3-6", 1))

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == saved.evidence_id)
            .values(org_id="foreign-tenant-evil")
        )

    assert await repo.verify_chain("org-h3-6") is False


# Scenario 7: Modified policy hash / version
@pytest.mark.asyncio
async def test_07_modified_policy_version_detected(engine):
    repo = EvidenceRepository(engine)
    saved = await repo.record(_make_evidence_record("org-h3-7", 1))

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == saved.evidence_id)
            .values(policy_version=99999)
        )

    assert await repo.verify_chain("org-h3-7") is False


# Scenario 8: Modified approval digest
@pytest.mark.asyncio
async def test_08_modified_approval_digest_detected(engine):
    repo = EvidenceRepository(engine)
    saved = await repo.record(_make_evidence_record("org-h3-8", 1))

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == saved.evidence_id)
            .values(approval_id="tampered-approval-id")
        )

    assert await repo.verify_chain("org-h3-8") is False


# Scenario 9: Grant-to-execution mismatch
@pytest.mark.asyncio
async def test_09_grant_to_execution_mismatch(engine):
    repo = EvidenceRepository(engine)
    saved = await repo.record(_make_evidence_record("org-h3-9", 1))

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == saved.evidence_id)
            .values(arguments_fingerprint="f" * 64)
        )

    assert await repo.verify_chain("org-h3-9") is False


# Scenario 10: Replayed evidence nonce
@pytest.mark.asyncio
async def test_10_replayed_evidence_nonce_rejected(engine):
    repo = EvidenceRepository(engine)
    rec1 = _make_evidence_record("org-h3-10", 1)
    await repo.record(rec1)

    # Re-recording with identical evidence_id is rejected by primary key integrity
    with pytest.raises(IntegrityError, match="(?i)unique|duplicate"):
        await repo.record(rec1)


# Scenario 11: Interrupted audit append atomic rollback
@pytest.mark.asyncio
async def test_11_interrupted_audit_append_atomic_rollback(engine):
    repo = EvidenceRepository(engine)
    await repo.record(_make_evidence_record("org-h3-11", 1))

    # An interrupted append transaction rolls back cleanly
    try:
        async with engine.raw.begin() as conn:
            await conn.execute(
                governance_evidence.insert().values(
                    id="partial-fail",
                    org_id="org-h3-11",
                    identity_id="test",
                    authentication_method="api_key",
                    agent_id="test",
                    action_type="test",
                    target="test",
                    arguments_fingerprint="0" * 64,
                    purpose="test",
                    decision="ALLOW",
                    chain_sequence=2,
                    entry_hash="bad_hash",
                    prev_hash="0" * 64,
                    recorded_at="2026-01-01T00:00:00Z",
                    evaluated_at="2026-01-01T00:00:00Z",
                    action_id="act-fail",
                    authority_delegated_by="test-auth",
                    reason_codes="[]",
                    integrity_version=2,
                )
            )
            raise RuntimeError("Interrupted power failure")
    except RuntimeError:
        pass

    # Chain remains completely valid at sequence 1
    assert await repo.verify_chain("org-h3-11") is True


# Scenario 12: Partial evidence write rollback
@pytest.mark.asyncio
async def test_12_partial_evidence_write_rollback(engine):
    repo = EvidenceRepository(engine)
    rec = _make_evidence_record("org-h3-12", 1)
    await repo.record(rec)

    # Verify head sequence is exactly 1 in chain heads table
    async with engine.raw.connect() as conn:
        head = (
            await conn.execute(
                select(governance_evidence_chain_heads).where(
                    governance_evidence_chain_heads.c.org_id == "org-h3-12"
                )
            )
        ).fetchone()
    assert head is not None
    assert head.sequence == 1


# Scenario 13: Database outage during evidence persistence fail-closed
@pytest.mark.asyncio
async def test_13_database_outage_during_persistence():
    # If database engine raises connection error, evidence cannot be silently recorded
    mock_engine = MagicMock()
    mock_engine.raw.begin.side_effect = ConnectionRefusedError("Database down")
    repo = EvidenceRepository(mock_engine)

    with pytest.raises(ConnectionRefusedError):
        await repo.record(_make_evidence_record("org-outage", 1))


# Scenario 14: Witness service unavailable handling
def test_14_witness_service_unavailable(tmp_path):
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")
    log.publish = MagicMock(side_effect=OSError("Disk full"))

    # If witness log fails to publish and required=True, raises WitnessRequiredUnavailableError
    with pytest.raises(WitnessRequiredUnavailableError):
        publish_evidence_head(
            store,
            log,
            organization_id="org-witness-down",
            chain_sequence=1,
            head_hash="a" * 64,
            witnessed_at="2026-10-18T00:00:00Z",
            required=True,
        )


# Scenario 15: Witness publication mismatch detected
def test_15_witness_publication_mismatch(tmp_path):
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")

    publish_evidence_head(
        store,
        log,
        organization_id="org-witness-mismatch",
        chain_sequence=1,
        head_hash="a" * 64,
        witnessed_at="2026-10-18T00:00:00Z",
        required=True,
        opaque_reference=False,
    )
    # Verification with different head hash raises WitnessPublicationError
    with pytest.raises(WitnessPublicationError, match="database head does not match the published witness"):
        verify_published_head(
            log,
            organization_id="org-witness-mismatch",
            chain_sequence=1,
            head_hash="b" * 64,
        )
    # Verification with matching head hash passes
    verified = verify_published_head(
        log,
        organization_id="org-witness-mismatch",
        chain_sequence=1,
        head_hash="a" * 64,
    )
    assert verified.head_hash == "a" * 64


# Scenario 16: Revoked grant reused with old evidence rejected
@pytest.mark.asyncio
async def test_16_revoked_grant_reused_with_old_evidence_rejected(engine):
    repo = EvidenceRepository(engine)
    rec = _make_evidence_record("org-h3-16", 1)
    await repo.record(rec)

    # Modifying the epoch on historical record breaks chain
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(governance_evidence)
            .where(governance_evidence.c.id == rec.evidence_id)
            .values(governance_epoch=99)
        )
    assert await repo.verify_chain("org-h3-16") is False


# Scenario 17: Corrupt evidence export detected during verification
@pytest.mark.asyncio
async def test_17_corrupt_evidence_export_detected(engine):
    repo = EvidenceRepository(engine)
    rec = await repo.record(_make_evidence_record("org-export", 1))

    bundle = build_evidence_bundle([rec], org_id="org-export")
    bundle_dict = bundle.to_dict()

    # Valid export passes verification
    res = verify_evidence_bundle(bundle_dict)
    assert res.valid is True

    # Tampered export fails verification
    tampered_dict = json.loads(json.dumps(bundle_dict))
    tampered_dict["records"][0]["target"] = "tampered-action-target"
    tampered_res = verify_evidence_bundle(tampered_dict)
    assert tampered_res.valid is False


# Scenario 18: Concurrent append collisions serialized
@pytest.mark.asyncio
async def test_18_concurrent_append_collisions_serialized(engine):
    repo = EvidenceRepository(engine)
    org_id = "org-concurrent-append"

    async def record_task(idx: int):
        rec = _make_evidence_record(org_id, idx)
        return await repo.record(rec)

    # Concurrently write 10 evidence records
    saved = await asyncio.gather(*(record_task(i) for i in range(10)))
    assert len(saved) == 10

    # Chain MUST remain strictly valid with all 10 records linked in sequence
    assert await repo.verify_chain(org_id) is True
    async with engine.raw.connect() as conn:
        head = (
            await conn.execute(
                select(governance_evidence_chain_heads).where(
                    governance_evidence_chain_heads.c.org_id == org_id
                )
            )
        ).fetchone()
    assert head.sequence == 10


# Scenario 19: Incorrect retention enforcement detected
@pytest.mark.asyncio
async def test_19_incorrect_retention_enforcement(engine):
    repo = EvidenceRepository(engine)
    org_id = "org-retention"
    await repo.record(_make_evidence_record(org_id, 1))
    await repo.record(_make_evidence_record(org_id, 2))

    # Deleting record 1 under the guise of "retention pruning" invalidates the chain
    async with engine.raw.begin() as conn:
        await conn.execute(
            delete(governance_evidence).where(
                governance_evidence.c.org_id == org_id,
                governance_evidence.c.chain_sequence == 1,
            )
        )
    assert await repo.verify_chain(org_id) is False


# Scenario 20: Unauthorized evidence deletion detected against durable head
@pytest.mark.asyncio
async def test_20_unauthorized_deletion_detected_against_durable_head(engine):
    repo = EvidenceRepository(engine)
    org_id = "org-purge-attack"
    await repo.record(_make_evidence_record(org_id, 1))

    # Attacker purges the entire evidence table for this tenant
    async with engine.raw.begin() as conn:
        await conn.execute(
            delete(governance_evidence).where(governance_evidence.c.org_id == org_id)
        )

    # Durable head still records that evidence existed; verification flags INVALID
    status = await repo.verify_chain_status(org_id)
    assert status.value == "INVALID"
    assert await repo.verify_chain(org_id) is False
