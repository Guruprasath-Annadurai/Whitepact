# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.db import OrgRepository, create_engine
from responsibleai.sovereign.capsule import create_capsule
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.gauntlet import GauntletVerdict
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore
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


class TestPhaseD:
    async def test_gauntlet_pass_from_observation(self, svc, store) -> None:
        org = await OrgRepository(store.engine).create_org("G", "g")
        ctx = SovereignContext(organization_id=org.id)
        report = await svc.run_gauntlet_async(ctx)
        assert report.cases
        assert any(c.verdict == GauntletVerdict.PASS for c in report.cases)

    def test_capsule_tamper_detected(self) -> None:
        ctx = SovereignContext(organization_id="org")
        cap = create_capsule(ctx, authority_subset={"api_key": "secret-value"})
        cap.authority_subset["api_key"] = "tampered"
        assert SovereignService().validate_capsule(cap) is False

    def test_capsule_reproduce_zero_effect(self) -> None:
        ctx = SovereignContext(organization_id="org")
        svc = SovereignService()
        cap = svc.create_capsule(ctx)
        before = consequential_invocation_count()
        svc.reproduce_capsule(cap)
        assert consequential_invocation_count() == before
