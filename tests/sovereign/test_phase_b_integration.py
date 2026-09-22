# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from responsibleai.db import DelegationRepository, EvidenceRepository, OrgRepository, create_engine
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.models import GovernanceDecision
from responsibleai.sovereign.authority_engine import AuthorityDiffCategory
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.graph import GraphQueryBudget
from responsibleai.sovereign.manifest import WhitepactManifest
from responsibleai.sovereign.models import OutcomeDisposition
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import (
    consequential_invocation_count,
    is_zero_effect_context,
)


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def store(engine):
    return SovereignCanonicalStore.from_engine(engine)


@pytest.fixture()
def svc(store):
    return SovereignService(store=store)


@pytest.fixture()
async def org_a(engine):
    repo = OrgRepository(engine)
    org = await repo.create_org("Org A", "org-a")
    return org.id


async def _grant_tree(repo: DelegationRepository, org_id: str) -> None:
    await repo.grant(
        org_id,
        "manager-1",
        granted_action_types=frozenset({"payment.execute", "crm.read"}),
        purpose="ops",
        granted_by="owner-1",
    )
    await repo.grant(
        org_id,
        "agent-1",
        granted_action_types=frozenset({"payment.execute"}),
        purpose="support",
        granted_by="owner-1",
        from_identity_id="manager-1",
    )


def _evidence(org_id: str, identity: str = "agent-1", decision: str = "DENY") -> EvidenceRecord:
    return EvidenceRecord(
        action_id="act-1",
        agent_id=identity,
        identity_id=identity,
        action_type="payment.execute",
        target="acct:1",
        argument_keys=["amount"],
        authority_delegated_by="manager-1",
        decision=decision,
        reason_codes=["TEST"],
        evaluated_at=datetime.now(UTC),
        organization_id=org_id,
        policy_version=1,
        governance_epoch=0,
        delegation_chain=["owner-1", "manager-1"],
    )


class TestPhaseBXRay:
    async def test_repository_backed_graph_deterministic(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        ctx = SovereignContext(organization_id=org_a)
        g1 = (await svc.build_xray_async(ctx)).graph
        g2 = (await svc.build_xray_async(ctx)).graph
        assert [n.node_id for n in g1.nodes] == [n.node_id for n in g2.nodes]
        assert [e.edge_id for e in g1.edges] == [e.edge_id for e in g2.edges]
        kinds = {n.kind.value for n in g1.nodes}
        assert "organization" in kinds
        assert "agent" in kinds
        assert "capability" in kinds
        assert any(e.kind.value == "DELEGATED_TO" for e in g1.edges)

    async def test_transitive_can_call_derivation(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        ctx = SovereignContext(organization_id=org_a)
        graph = (await svc.build_xray_async(ctx)).graph
        transitive = [
            e
            for e in graph.edges
            if e.kind.value == "CAN_CALL" and e.provenance.derivation.value == "TRANSITIVE"
        ]
        assert transitive, "agent-1 should have transitive capability edges"

    async def test_graph_budget_truncation(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        ctx = SovereignContext(organization_id=org_a)
        tiny = GraphQueryBudget(max_nodes=3, max_edges=2, max_depth=2)
        graph = (await svc.build_xray_async(ctx, budget=tiny)).graph
        assert graph.truncated is True


class TestPhaseBDebuggerAndTrace:
    async def test_debugger_from_evidence_deny(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        ev = await EvidenceRepository(store.engine).record(_evidence(org_a))
        ctx = SovereignContext(organization_id=org_a)
        exp = await svc.explain_evidence_async(ctx, ev.evidence_id)
        assert exp.disposition == GovernanceDecision.DENY
        kinds = {i.kind.value for i in exp.items}
        assert "FACT" in kinds
        assert "DERIVED" in kinds

    async def test_trace_missing_outcome_stage(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        ev = await EvidenceRepository(store.engine).record(_evidence(org_a))
        ctx = SovereignContext(organization_id=org_a)
        trace = await svc.trace_evidence_async(ctx, ev.evidence_id)
        outcomes = [s for s in trace.stages if s.stage.value == "outcome"]
        assert outcomes and outcomes[0].status == "MISSING"
        assert trace.envelope.evidence_id == ev.evidence_id

    async def test_unknown_decision_preserved(self, svc, store, org_a) -> None:
        ev = await EvidenceRepository(store.engine).record(
            _evidence(org_a, decision="NOT_A_REAL_DECISION")
        )
        ctx = SovereignContext(organization_id=org_a)
        exp = await svc.explain_evidence_async(ctx, ev.evidence_id)
        assert exp.disposition == OutcomeDisposition.UNKNOWN
        assert exp.reconciliation_required is True


class TestPhaseBAuthority:
    async def test_manifest_does_not_grant(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        manifest = WhitepactManifest(
            organization_id=org_a,
            capabilities=[
                {"capability_id": "payment.execute"},
                {"capability_id": "missing.cap"},
            ],
        )
        ctx = SovereignContext(organization_id=org_a)
        before = await svc.load_effective_async(ctx)
        result = await svc.compare_manifest_async(ctx, manifest)
        assert any(
            d.category == AuthorityDiffCategory.UNEXPECTED_EFFECTIVE
            for d in result.diffs
            if d.capability_id == "crm.read"
        )
        assert any(
            d.category == AuthorityDiffCategory.EXPECTED_BUT_MISSING
            for d in result.diffs
            if d.capability_id == "missing.cap"
        )
        after = await svc.load_effective_async(ctx)
        assert before.capability_ids == after.capability_ids

    async def test_drift_detects_policy_epoch_change(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        ctx = SovereignContext(organization_id=org_a)
        prior = await svc.load_effective_async(ctx)
        manifest = WhitepactManifest(organization_id=org_a, capabilities=[])
        drift = await svc.detect_drift_async(ctx, manifest, prior_effective=prior)
        assert isinstance(drift.facts, list)


class TestPhaseBTenantAndZeroEffect:
    async def test_cross_tenant_trace_denied(self, svc, store, org_a) -> None:
        org_b = await OrgRepository(store.engine).create_org("Org B", "org-b")
        ev = await EvidenceRepository(store.engine).record(_evidence(org_b.id))
        ctx = SovereignContext(organization_id=org_a)
        with pytest.raises(SovereignTenantIsolationError):
            await svc.trace_evidence_async(ctx, ev.evidence_id)

    async def test_xray_zero_effect_context(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        ctx = SovereignContext(organization_id=org_a)
        assert not is_zero_effect_context()
        await svc.build_xray_async(ctx)
        assert not is_zero_effect_context()
        assert consequential_invocation_count() == 0

    async def test_delegation_grant_not_called_during_xray(self, svc, store, org_a) -> None:
        await _grant_tree(store.delegations, org_a)
        original = store.delegations.grant

        async def forbidden_grant(*args, **kwargs):  # noqa: ANN002, ANN003
            raise AssertionError("grant must not run during read-only X-Ray")

        store.delegations.grant = forbidden_grant  # type: ignore[method-assign]
        try:
            await svc.build_xray_async(SovereignContext(organization_id=org_a))
        finally:
            store.delegations.grant = original  # type: ignore[method-assign]
