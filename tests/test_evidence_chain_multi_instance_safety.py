"""Tests for Security Remediation Gap 5 (multi-instance evidence-chain
sequencing safety). See migrations/versions/0033_add_evidence_chain_uniqueness.py's
own docstring for the full race being closed.

`EvidenceRepository`'s per-process `asyncio.Lock` + in-process
`_last_hash_by_org` cache is a real, deliberate gap this file
reproduces first, deterministically: two independent
`EvidenceRepository` instances (standing in for two application
replicas) sharing the same underlying DB engine, one of which has
stale cached chain state -- exactly what happens when a second
replica's write starts before the first replica's write has landed.
`db/engine.py`'s `idx_gev_chain_link`/`idx_gev_chain_genesis` unique
indexes turn the resulting race into a caught `IntegrityError`, and
`record()`'s retry loop recovers from it correctly rather than
forking the chain.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.evidence_repository import EvidenceChainConflictError, EvidenceRepository
from responsibleai.governance.evidence import EvidenceRecord


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


def _evidence(action_id: str, org_id: str = "org-1") -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"ev-{action_id}",
        organization_id=org_id,
        action_id=action_id,
        agent_id="agent-1",
        identity_id="identity-1",
        action_type="mcp_tool_call",
        target="rai_scan",
        argument_keys=[],
        authority_delegated_by="org-1",
        decision="ALLOW",
        reason_codes=[],
        evaluated_at=datetime.now(UTC),
    )


class TestGenesisRaceBetweenTwoReplicas:
    """Two 'replicas' both believe org-1 has no prior evidence (both
    cached prev_hash=None) -- simulating repo2 having read that state
    before repo1's write landed."""

    async def test_second_replica_recovers_and_chains_correctly(self, db):
        repo1 = EvidenceRepository(db)
        repo2 = EvidenceRepository(db)

        await repo1.record(_evidence("a1"))

        # Force repo2 into exactly the stale state a real second
        # replica would have: it "already checked" and cached "no
        # entries yet" for org-1, before repo1's write above happened.
        repo2._hydrated_orgs.add("org-1")
        repo2._last_hash_by_org["org-1"] = None

        result = await repo2.record(_evidence("a2"))

        records = await repo1.list_for_org("org-1")
        assert len(records) == 2
        # No fork: exactly one genesis entry (prev_hash=None), and the
        # second entry correctly chains onto the first's real hash,
        # not onto a second, independent None.
        genesis_entries = [r for r in records if r.prev_hash is None]
        assert len(genesis_entries) == 1
        assert result.prev_hash == genesis_entries[0].hash

        assert await repo1.verify_chain("org-1") is True


class TestNonGenesisRaceBetweenTwoReplicas:
    """Same scenario, one link further into an already-established
    chain -- repo2's cache is stale by one entry, not the whole
    chain."""

    async def test_second_replica_recovers_and_chains_correctly(self, db):
        repo1 = EvidenceRepository(db)
        repo2 = EvidenceRepository(db)

        first = await repo1.record(_evidence("b1"))
        second = await repo1.record(_evidence("b2"))

        # repo2 only ever saw the chain as of "first" -- it missed
        # "second" entirely, the realistic replica-lag scenario.
        repo2._hydrated_orgs.add("org-1")
        repo2._last_hash_by_org["org-1"] = first.hash

        result = await repo2.record(_evidence("b3"))

        records = await repo1.list_for_org("org-1")
        assert len(records) == 3
        assert result.prev_hash == second.hash
        assert await repo1.verify_chain("org-1") is True

    async def test_chains_for_different_orgs_never_interfere(self, db):
        """The unique indexes are scoped per org_id -- a race resolved
        for org-1 must not affect org-2's independent chain."""
        repo1 = EvidenceRepository(db)
        repo2 = EvidenceRepository(db)

        await repo1.record(_evidence("c1", org_id="org-1"))
        await repo2.record(_evidence("c2", org_id="org-2"))

        assert await repo1.verify_chain("org-1") is True
        assert await repo1.verify_chain("org-2") is True
        org1_records = await repo1.list_for_org("org-1")
        org2_records = await repo1.list_for_org("org-2")
        assert len(org1_records) == 1
        assert len(org2_records) == 1
        assert org1_records[0].prev_hash is None
        assert org2_records[0].prev_hash is None


class TestPersistentConflictFailsClosed:
    async def test_exhausted_retries_raise_a_named_error(self, db, monkeypatch: pytest.MonkeyPatch):
        from sqlalchemy.exc import IntegrityError

        repo = EvidenceRepository(db)

        attempts = 0
        original_begin = type(db.raw).begin

        class _AlwaysConflict:
            def __init__(self, engine):
                self._engine = engine

            async def __aenter__(self):
                nonlocal attempts
                attempts += 1
                raise IntegrityError("insert", {}, Exception("unique constraint failed"))

            async def __aexit__(self, *exc_info):
                return False

        monkeypatch.setattr(type(db.raw), "begin", lambda self: _AlwaysConflict(self))

        with pytest.raises(EvidenceChainConflictError):
            await repo.record(_evidence("d1"))

        monkeypatch.setattr(type(db.raw), "begin", original_begin)
        assert attempts == 5
