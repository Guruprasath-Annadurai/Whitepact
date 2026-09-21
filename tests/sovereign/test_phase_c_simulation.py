# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.db import DelegationRepository, OrgRepository, PolicyRepository, create_engine
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.risk import RiskTier
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.policy_lab import PolicyTestCase
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.simulation import MissionDisposition
from responsibleai.sovereign.zero_effect import consequential_invocation_count


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


class TestPhaseCSimulation:
    async def test_mission_simulation_zero_effect(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("O", "o")
        repo = DelegationRepository(store.engine)
        await repo.grant(
            org.id,
            "agent-1",
            granted_action_types=frozenset({"crm.read", "email.send"}),
            purpose="p",
            granted_by="owner",
        )
        ctx = SovereignContext(organization_id=org.id)
        result = await svc.simulate_mission_async(
            ctx, agent_id="agent-1", steps=["crm.read", "unknown.action"]
        )
        assert result.steps[1].disposition == MissionDisposition.UNREACHABLE
        assert consequential_invocation_count() == 0

    async def test_blast_radius_counterfactual(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("O2", "o2")
        repo = DelegationRepository(store.engine)
        await repo.grant(
            org.id,
            "agent-2",
            granted_action_types=frozenset({"a"}),
            purpose="p",
            granted_by="owner",
        )
        ctx = SovereignContext(organization_id=org.id)
        br = await svc.simulate_blast_radius_async(
            ctx, actor_identity_id="agent-2", hypothetical_extra_capabilities=frozenset({"b"})
        )
        assert "b" in br.reachable_capabilities

    async def test_shadow_non_authoritative(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("O3", "o3")
        ctx = SovereignContext(organization_id=org.id)
        obs = svc.evaluate_shadow(
            ctx, agent_id="agent", action_type="rai_scan", granted_action_types=frozenset({"rai_scan"})
        )
        assert obs.non_authoritative is True

    async def test_policy_lab_runs_engine(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("O4", "o4")
        policies = PolicyRepository(store.engine)
        await policies.add_rule(
            org.id,
            PolicyRule(
                rule_id="deny-all",
                reason_code="TEST",
                effect=GovernanceDecision.DENY,
                risk_tiers=frozenset({RiskTier.LOW}),
            ),
        )
        ctx = SovereignContext(organization_id=org.id)
        report = await svc.run_policy_tests_async(
            ctx,
            [PolicyTestCase(name="deny", action_type="x", expect_effect="DENY")],
        )
        assert report.results[0].passed is True
        assert report.results[0].matched_rule_id == "deny-all"
