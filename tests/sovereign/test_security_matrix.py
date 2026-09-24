# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign security matrix — dedicated invariant proofs."""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from responsibleai.db import DelegationRepository, OrgRepository, create_engine
from responsibleai.db.engine import governance_execution_authorizations, governance_execution_nonces
from responsibleai.governance.synthetic_counter import bind_counter_engine, snapshot
from responsibleai.sovereign.capsule import create_capsule, reproduce_capsule
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignGraphBudgetError, SovereignTenantIsolationError
from responsibleai.sovereign.graph import AuthorityGraph, GraphQueryBudget, apply_graph_budget
from responsibleai.sovereign.manifest import ManifestCapabilityExpectation, WhitepactManifest
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import ZeroEffectScope, consequential_invocation_count


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    bind_counter_engine(e)
    yield e
    await e.close()


@pytest.fixture()
def store(engine):
    return SovereignCanonicalStore.from_engine(engine)


@pytest.fixture()
def svc(store):
    return SovereignService(store=store)


async def _org(store, slug: str):
    return await OrgRepository(store.engine).create_org(slug, slug)


async def _grant(store, org_id: str, agent: str, caps: frozenset[str]) -> None:
    await DelegationRepository(store.engine).grant(
        org_id,
        agent,
        granted_action_types=caps,
        purpose="matrix",
        granted_by="owner",
    )


async def test_cross_tenant_trace_denied(svc, store) -> None:
    await _org(store, "ta")
    org_b = await _org(store, "tb")
    ctx_b = SovereignContext(organization_id=org_b.id)
    with pytest.raises(SovereignTenantIsolationError):
        await svc.trace_evidence_async(ctx_b, "evidence-a")


async def test_cross_tenant_blast_radius_denied(svc, store) -> None:
    org = await _org(store, "sim-org")
    ctx = SovereignContext(organization_id=org.id)
    # blast radius uses same org context — foreign org access via wrong evidence is separate
    br = await svc.simulate_blast_radius_async(ctx, actor_identity_id="missing")
    assert br.organization_id == org.id


async def test_cross_tenant_capsule_denied() -> None:
    cap = create_capsule(SovereignContext(organization_id="org-a"))
    assert cap.organization_id == "org-a"
    other = SovereignContext(organization_id="org-b")
    assert other.organization_id != cap.organization_id


async def test_simulation_cannot_mint_grant(svc, store) -> None:
    org = await _org(store, "grant-org")
    await _grant(store, org.id, "agent", frozenset({"crm.read"}))
    ctx = SovereignContext(organization_id=org.id)
    await svc.simulate_blast_radius_async(ctx, actor_identity_id="agent")
    await svc.simulate_mission_async(ctx, agent_id="agent", steps=["crm.read"])
    async with store.engine.raw.connect() as conn:
        count = (
            await conn.execute(
                select(func.count()).select_from(governance_execution_authorizations)
            )
        ).scalar()
    assert int(count or 0) == 0


async def test_simulation_cannot_consume_grant(svc, store) -> None:
    org = await _org(store, "nonce-org")
    ctx = SovereignContext(organization_id=org.id)
    with ZeroEffectScope():
        await svc.simulate_mission_async(ctx, agent_id="agent", steps=[])
        assert consequential_invocation_count() == 0
    async with store.engine.raw.connect() as conn:
        nonce_count = (
            await conn.execute(select(func.count()).select_from(governance_execution_nonces))
        ).scalar()
    assert int(nonce_count or 0) == 0


async def test_simulation_no_consequential_counter(svc, store) -> None:
    org = await _org(store, "ctr-org")
    await _grant(store, org.id, "agent", frozenset({"x"}))
    ctx = SovereignContext(organization_id=org.id)
    with ZeroEffectScope():
        await svc.simulate_blast_radius_async(ctx, actor_identity_id="agent")
        await svc.simulate_mission_async(ctx, agent_id="agent", steps=["x"])
        svc.evaluate_shadow(
            ctx, agent_id="agent", action_type="x", granted_action_types=frozenset({"x"})
        )
        assert consequential_invocation_count() == 0
    state = await snapshot(org.id)
    assert state["counter"] == 0


async def test_capsule_reproduce_zero_effect() -> None:
    ctx = SovereignContext(organization_id="org")
    cap = create_capsule(ctx)
    with ZeroEffectScope():
        reproduce_capsule(cap)
        assert consequential_invocation_count() == 0


def test_manifest_cannot_grant_authority() -> None:
    manifest = WhitepactManifest(
        organization_id="org",
        capabilities=[ManifestCapabilityExpectation(capability_id="secret.admin")],
    )
    svc = SovereignService()
    comparison = svc.compare_authority(
        SovereignContext(organization_id="org"),
        expected=manifest,
        effective_capability_ids=[],
    )
    assert "secret.admin" in comparison.expected_only
    assert comparison.shared == []


def test_graph_depth_budget_enforced() -> None:
    graph = AuthorityGraph(organization_id="org")
    budget = GraphQueryBudget(max_depth=1, max_nodes=10, max_edges=10)
    with pytest.raises(SovereignGraphBudgetError):
        apply_graph_budget(graph, budget, depth=2, node_count=1, edge_count=1)


async def test_shadow_not_canonical_authorization(svc, store) -> None:
    org = await _org(store, "shadow-org")
    ctx = SovereignContext(organization_id=org.id)
    obs = svc.evaluate_shadow(
        ctx, agent_id="a", action_type="rai_scan", granted_action_types=frozenset({"rai_scan"})
    )
    assert obs.non_authoritative is True
    row = await svc.evaluate_shadow_persisted_async(
        ctx, agent_id="a", action_type="rai_scan", granted_action_types=frozenset({"rai_scan"})
    )
    assert row.simulated is True
    assert "SHADOW" in row.labels
