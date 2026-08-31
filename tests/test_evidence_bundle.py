# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for the Evidence Bundle (governance/evidence_bundle.py):
`build_evidence_bundle()`, `verify_evidence_bundle()`, and
`EvidenceRepository.list_for_bundle()` -- the self-contained, offline-
verifiable export of an org's governance evidence chain.
"""

from __future__ import annotations

import copy

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.db import EvidenceRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
    WhitePactRuntimeGateway,
    build_evidence_bundle,
    verify_evidence_bundle,
)
from responsibleai.governance.evidence import build_evidence_record


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


async def _seed(evidence_repo: EvidenceRepository, n: int, *, org_id: str = "org-1"):
    gw = WhitePactRuntimeGateway()
    records = []
    for i in range(n):
        agent = _agent(org_id=org_id)
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target=f"tool-{i}")
        authority = _authority()
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, agent, authority, decision)
        recorded = await evidence_repo.record(evidence)
        records.append(recorded)
    return records


class TestListForBundle:
    async def test_empty_when_no_history(self, evidence_repo) -> None:
        assert await evidence_repo.list_for_bundle("org-1") == []

    async def test_returns_ascending_chronological_order(self, evidence_repo) -> None:
        await _seed(evidence_repo, 3)
        records = await evidence_repo.list_for_bundle("org-1")
        assert [r.target for r in records] == ["tool-0", "tool-1", "tool-2"]

    async def test_scoped_to_org(self, evidence_repo) -> None:
        await _seed(evidence_repo, 2, org_id="org-1")
        assert await evidence_repo.list_for_bundle("org-2") == []

    async def test_since_filters_out_old_entries(self, evidence_repo) -> None:
        await _seed(evidence_repo, 1)
        future = "2999-01-01T00:00:00+00:00"
        assert await evidence_repo.list_for_bundle("org-1", since=future) == []

    async def test_until_filters_out_new_entries(self, evidence_repo) -> None:
        await _seed(evidence_repo, 1)
        past = "2000-01-01T00:00:00+00:00"
        assert await evidence_repo.list_for_bundle("org-1", until=past) == []

    async def test_records_carry_recorded_at(self, evidence_repo) -> None:
        await _seed(evidence_repo, 1)
        records = await evidence_repo.list_for_bundle("org-1")
        assert records[0].recorded_at is not None


class TestBuildEvidenceBundle:
    async def test_empty_records_produce_valid_empty_bundle(self) -> None:
        bundle = build_evidence_bundle([], org_id="org-1")
        assert bundle.records == ()
        assert bundle.org_id == "org-1"
        assert bundle.bundle_digest  # deterministic hash of an empty join, still a real string

    async def test_bundle_id_defaults_to_a_generated_uuid(self) -> None:
        b1 = build_evidence_bundle([], org_id="org-1")
        b2 = build_evidence_bundle([], org_id="org-1")
        assert b1.bundle_id != b2.bundle_id

    async def test_explicit_bundle_id_used(self) -> None:
        bundle = build_evidence_bundle([], org_id="org-1", bundle_id="fixed-id")
        assert bundle.bundle_id == "fixed-id"

    async def test_to_dict_shape(self, evidence_repo) -> None:
        records = await _seed(evidence_repo, 2)
        bundle = build_evidence_bundle(records, org_id="org-1")
        d = bundle.to_dict()
        assert d["org_id"] == "org-1"
        assert d["record_count"] == 2
        assert len(d["records"]) == 2
        assert "bundle_digest" in d


class TestVerifyEvidenceBundleRoundTrip:
    async def test_freshly_built_full_chain_bundle_verifies(self, evidence_repo) -> None:
        records = await _seed(evidence_repo, 5)
        bundle = build_evidence_bundle(records, org_id="org-1")
        result = verify_evidence_bundle(bundle.to_dict())
        assert result.valid is True
        assert result.chain_intact is True
        assert result.digest_matches is True
        assert result.failure_reason is None

    async def test_single_record_bundle_verifies(self, evidence_repo) -> None:
        records = await _seed(evidence_repo, 1)
        bundle = build_evidence_bundle(records, org_id="org-1")
        result = verify_evidence_bundle(bundle.to_dict())
        assert result.valid is True

    async def test_empty_bundle_verifies(self) -> None:
        bundle = build_evidence_bundle([], org_id="org-1")
        result = verify_evidence_bundle(bundle.to_dict())
        assert result.valid is True

    async def test_scoped_bundle_with_external_anchor_still_verifies(self, evidence_repo) -> None:
        """A bundle covering only the tail of the chain -- its first
        record's prev_hash points outside the bundle, but internal
        consistency from that anchor forward should still verify."""
        await _seed(evidence_repo, 5)
        all_records = await evidence_repo.list_for_bundle("org-1")
        tail = all_records[2:]  # skip the first two -- tail[0].prev_hash is an external anchor
        bundle = build_evidence_bundle(tail, org_id="org-1")
        result = verify_evidence_bundle(bundle.to_dict())
        assert result.valid is True


class TestVerifyEvidenceBundleTamperDetection:
    async def test_editing_a_field_breaks_hash(self, evidence_repo) -> None:
        records = await _seed(evidence_repo, 3)
        bundle = build_evidence_bundle(records, org_id="org-1")
        tampered = copy.deepcopy(bundle.to_dict())
        tampered["records"][1]["decision"] = "DENY"  # was ALLOW
        result = verify_evidence_bundle(tampered)
        assert result.valid is False


_json_scalars = st.none() | st.booleans() | st.integers() | st.text(max_size=80)
_json_values = st.recursive(
    _json_scalars,
    lambda children: (
        st.lists(children, max_size=8) | st.dictionaries(st.text(max_size=30), children, max_size=8)
    ),
    max_leaves=30,
)


class TestEvidenceBundleMalformedInputProperties:
    @given(value=_json_values)
    def test_arbitrary_json_never_raises_or_verifies(self, value: object) -> None:
        """Untrusted serialized input must fail closed without parser exceptions."""
        result = verify_evidence_bundle(value)  # type: ignore[arg-type]
        assert result.valid is False

    @given(replacement=st.text(max_size=100).filter(lambda value: value != "ALLOW"))
    def test_arbitrary_decision_mutation_breaks_hash(self, replacement: str) -> None:
        from datetime import UTC, datetime

        from responsibleai.governance.evidence import EvidenceRecord
        from responsibleai.governance.evidence_bundle import _compute_entry_hash

        record = EvidenceRecord(
            evidence_id="evidence-1",
            organization_id="org-1",
            action_id="action-1",
            agent_id="agent-1",
            identity_id="identity-1",
            action_type="mcp_tool_call",
            target="tool-1",
            argument_keys=[],
            authority_delegated_by="org-1",
            decision="ALLOW",
            reason_codes=[],
            evaluated_at=datetime(2026, 8, 31, tzinfo=UTC),
            recorded_at="2026-08-31T00:00:00+00:00",
        )
        record.hash = _compute_entry_hash(record.prev_hash, record)
        bundle = build_evidence_bundle([record], org_id="org-1").to_dict()
        bundle["records"][0]["decision"] = replacement
        assert verify_evidence_bundle(bundle).valid is False

    async def test_reordering_records_breaks_chain(self, evidence_repo) -> None:
        records = await _seed(evidence_repo, 3)
        bundle = build_evidence_bundle(records, org_id="org-1")
        tampered = copy.deepcopy(bundle.to_dict())
        tampered["records"][0], tampered["records"][1] = (
            tampered["records"][1],
            tampered["records"][0],
        )
        result = verify_evidence_bundle(tampered)
        assert result.valid is False

    async def test_removing_a_middle_record_breaks_chain(self, evidence_repo) -> None:
        records = await _seed(evidence_repo, 3)
        bundle = build_evidence_bundle(records, org_id="org-1")
        tampered = copy.deepcopy(bundle.to_dict())
        del tampered["records"][1]
        result = verify_evidence_bundle(tampered)
        assert result.valid is False

    async def test_tampered_bundle_digest_alone_caught(self, evidence_repo) -> None:
        """Even if every record and its internal chain is untouched, a
        directly-edited bundle_digest field is caught."""
        records = await _seed(evidence_repo, 2)
        bundle = build_evidence_bundle(records, org_id="org-1")
        tampered = copy.deepcopy(bundle.to_dict())
        tampered["bundle_digest"] = "0" * 64
        result = verify_evidence_bundle(tampered)
        assert result.valid is False
        assert result.chain_intact is True
        assert result.digest_matches is False
        assert result.failure_reason == "bundle digest mismatch"

    async def test_appending_a_forged_record_caught(self, evidence_repo) -> None:
        records = await _seed(evidence_repo, 2)
        bundle = build_evidence_bundle(records, org_id="org-1")
        tampered = copy.deepcopy(bundle.to_dict())
        forged = copy.deepcopy(tampered["records"][-1])
        forged["evidence_id"] = "forged-id"
        forged["action_id"] = "forged-action"
        tampered["records"].append(forged)
        result = verify_evidence_bundle(tampered)
        assert result.valid is False
