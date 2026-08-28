"""Tests for Enterprise Neural Phase 13 (Immutable Audit + Evidence).

Per `docs/enterprise-neural/13_PHASE13_DESIGN.md`: `ENTERPRISE_SECURITY.md`
and `THREAT_MODEL.md` already document that no hash chain, on its own,
can defend against an attacker with full database write access who
recomputes the entire chain from scratch — only external anchoring
(a copy held somewhere the attacker doesn't control) can catch that.
`governance/evidence_bundle.py`'s offline-verifiable bundle export,
built for a different purpose (portable evidence for an auditor), is
already exactly the artifact such an anchor would need.

This file makes both halves of that claim concrete and reproducible,
rather than leaving them as prose assertions:

1. The limitation is real: a full-chain-regeneration attack, simulated
   by writing directly to the `governance_evidence` table (bypassing
   `EvidenceRepository` entirely, matching the documented threat model),
   passes `EvidenceRepository.verify_chain()` — internal self-consistency
   alone cannot catch it.
2. The mitigation actually works: a bundle digest captured *before*
   the tampering differs from one captured *after*, for the identical
   record range — an externally-held anchor from before the attack
   detects exactly what `verify_chain()` alone, run only after, cannot.
"""

from __future__ import annotations

import pytest
from sqlalchemy import update

from responsibleai.db import EvidenceRepository, create_engine
from responsibleai.db.engine import governance_evidence
from responsibleai.db.evidence_repository import _compute_entry_hash
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
    WhitePactRuntimeGateway,
    build_evidence_bundle,
)
from responsibleai.governance.evidence import EvidenceRecord, build_evidence_record


def _agent(org_id: str = "org-1", agent_id: str = "agent-1") -> AgentContext:
    identity = IdentityContext(identity_id=agent_id, kind="api_key", org_id=org_id)
    return AgentContext(identity=identity, agent_id=agent_id, framework="mcp-client")


def _authority(**kwargs) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"mcp_tool_call"}))
    return AuthorityContext(**kwargs)


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def evidence_repo(engine):
    return EvidenceRepository(engine)


async def _seed_with_one_denial(
    evidence_repo: EvidenceRepository, org_id: str = "org-1"
) -> list[EvidenceRecord]:
    """Four chained records; the third is a real DENY (no granted
    action types) — the decision an attacker would want to hide."""
    gw = WhitePactRuntimeGateway()
    records = []
    for i in range(4):
        agent = _agent(org_id=org_id)
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target=f"tool-{i}")
        authority = _authority(
            granted_action_types=frozenset() if i == 2 else frozenset({"mcp_tool_call"})
        )
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, agent, authority, decision)
        recorded = await evidence_repo.record(evidence)
        records.append(recorded)
    assert records[2].decision == "DENY"
    return records


async def _regenerate_chain_from_tampered_row(
    engine, org_id: str, tampered_index: int, records: list[EvidenceRecord]
) -> None:
    """Simulates an attacker with full DB write access: changes one
    row's `decision` directly (bypassing EvidenceRepository, which has
    no update method by design), then recomputes every hash from that
    point forward using the same formula the repository itself uses —
    the "full chain regeneration" ENTERPRISE_SECURITY.md's own
    documented limitation describes.
    """
    async with engine.raw.begin() as conn:
        prev_hash = records[tampered_index - 1].hash if tampered_index > 0 else None
        for i in range(tampered_index, len(records)):
            record = records[i]
            decision = "ALLOW" if i == tampered_index else record.decision
            hashable = {
                "id": record.evidence_id,
                "org_id": record.organization_id,
                "action_id": record.action_id,
                "decision": decision,
                "evaluated_at": record.evaluated_at.isoformat(),
                "recorded_at": record.recorded_at,
            }
            new_hash = _compute_entry_hash(prev_hash, hashable)
            await conn.execute(
                update(governance_evidence)
                .where(governance_evidence.c.id == record.evidence_id)
                .values(decision=decision, prev_hash=prev_hash, entry_hash=new_hash)
            )
            prev_hash = new_hash


class TestFullChainRegenerationIsUndetectableByVerifyChainAlone:
    """The documented limitation, made concrete: verify_chain() only
    proves internal self-consistency, which a full-DB-write attacker
    can always preserve."""

    async def test_tampered_chain_still_passes_verify_chain(self, engine, evidence_repo) -> None:
        records = await _seed_with_one_denial(evidence_repo)
        await _regenerate_chain_from_tampered_row(engine, "org-1", 2, records)

        assert await evidence_repo.verify_chain("org-1") is True

        # Confirm the tampering actually landed -- not a no-op test.
        tampered = await evidence_repo.get(records[2].evidence_id)
        assert tampered is not None
        assert tampered.decision == "ALLOW"


class TestExternalAnchorDetectsWhatVerifyChainCannot:
    """The mitigation, proven to work: a bundle digest captured before
    the attack differs from one captured after, for the same range."""

    async def test_bundle_digest_before_and_after_tampering_differ(
        self, engine, evidence_repo
    ) -> None:
        records = await _seed_with_one_denial(evidence_repo)
        pre_tamper_records = await evidence_repo.list_for_bundle("org-1")
        anchor_bundle = build_evidence_bundle(pre_tamper_records, org_id="org-1")

        await _regenerate_chain_from_tampered_row(engine, "org-1", 2, records)

        post_tamper_records = await evidence_repo.list_for_bundle("org-1")
        fresh_bundle = build_evidence_bundle(post_tamper_records, org_id="org-1")

        assert anchor_bundle.bundle_digest != fresh_bundle.bundle_digest
        # verify_chain() alone, run only against the now-tampered live
        # system, would report clean -- the anchor is what catches it.
        assert await evidence_repo.verify_chain("org-1") is True


class TestBundleDigestIsStableForUnchangedContent:
    """Negative control: two exports of the same, untampered range
    must produce the identical digest -- otherwise the two tests above
    would prove nothing (the digest could differ for unrelated
    reasons, like export timing)."""

    async def test_two_exports_of_unchanged_chain_match(self, evidence_repo) -> None:
        await _seed_with_one_denial(evidence_repo)

        first_records = await evidence_repo.list_for_bundle("org-1")
        first_bundle = build_evidence_bundle(first_records, org_id="org-1")

        second_records = await evidence_repo.list_for_bundle("org-1")
        second_bundle = build_evidence_bundle(second_records, org_id="org-1")

        assert first_bundle.bundle_digest == second_bundle.bundle_digest
