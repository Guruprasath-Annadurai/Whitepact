# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.db import OrgRepository, create_engine
from responsibleai.db.shadow_observation_repository import ShadowObservationRepository
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.shadow import ShadowObservation
from responsibleai.sovereign.sources import SovereignCanonicalStore


@pytest.mark.asyncio
async def test_shadow_observation_persisted_tenant_scoped() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    org = await OrgRepository(engine).create_org("S", "s")
    repo = ShadowObservationRepository(engine)
    ctx = SovereignContext(organization_id=org.id)
    obs = ShadowObservation(organization_id=org.id, decision="ALLOW", reason_codes=[])
    row = await repo.save(ctx, obs, agent_id="a", action_type="x")
    fetched = await repo.get_for_org(org.id, row.shadow_observation_id)
    assert fetched is not None
    assert fetched.org_id == org.id
    assert await repo.get_for_org("other-org", row.shadow_observation_id) is None
