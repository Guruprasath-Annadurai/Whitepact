# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.db import DelegationRepository, OrgRepository, create_engine
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.simulation import MissionDisposition
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import ZeroEffectScope, consequential_invocation_count


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


class TestPhaseCSecurity:
    async def test_cross_tenant_evidence_trace(self, svc, store) -> None:
        org_a = await OrgRepository(store.engine).create_org("A", "a")
        org_b = await OrgRepository(store.engine).create_org("B", "b")
        ctx_b = SovereignContext(organization_id=org_b.id)
        with pytest.raises(SovereignTenantIsolationError):
            await svc.trace_evidence_async(ctx_b, "evidence-from-org-a")

    async def test_unknown_capability_mission(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("O", "o")
        await DelegationRepository(store.engine).grant(
            org.id,
            "agent",
            granted_action_types=frozenset({"known"}),
            purpose="p",
            granted_by="owner",
        )
        ctx = SovereignContext(organization_id=org.id)
        mission = await svc.simulate_mission_async(ctx, agent_id="agent", steps=["unknown.cap"])
        assert mission.steps[0].disposition == MissionDisposition.UNREACHABLE

    async def test_zero_effect_simulators(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("Z", "z")
        ctx = SovereignContext(organization_id=org.id)
        with ZeroEffectScope():
            await svc.simulate_blast_radius_async(ctx, actor_identity_id="nope")
            await svc.simulate_mission_async(ctx, agent_id="agent", steps=[])
            assert consequential_invocation_count() == 0

    async def test_shadow_persisted_labels(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("S", "s")
        ctx = SovereignContext(organization_id=org.id)
        row = svc.evaluate_shadow_persisted(
            ctx, agent_id="a", action_type="rai_scan", granted_action_types=frozenset({"rai_scan"})
        )
        assert row.simulated is True
        assert "SHADOW" in row.labels
