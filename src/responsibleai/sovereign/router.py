# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""HTTP API for Sovereign — thin handlers over SovereignService."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from responsibleai.db import create_engine
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.policy_lab import PolicyTestCase
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore

router = APIRouter(prefix="/api/sovereign", tags=["sovereign"])


class OrgBody(BaseModel):
    organization_id: str
    environment: str | None = None
    principal_id: str | None = None


class BlastRadiusBody(OrgBody):
    actor_identity_id: str
    hypothetical_extra_capabilities: list[str] = Field(default_factory=list)


class MissionBody(OrgBody):
    agent_id: str
    steps: list[str]


class ShadowBody(OrgBody):
    agent_id: str
    action_type: str
    target: str = "shadow:target"


@router.get("/status")
async def sovereign_status() -> dict[str, Any]:
    svc = SovereignService()
    return svc.get_status().model_dump()


@router.get("/capabilities")
async def sovereign_capabilities() -> dict[str, Any]:
    svc = SovereignService()
    return svc.get_capabilities().model_dump()


@router.post("/simulate/blast-radius")
async def post_blast_radius(body: BlastRadiusBody) -> dict[str, Any]:
    engine = create_engine(":memory:")
    await engine.init()
    svc = SovereignService(store=SovereignCanonicalStore.from_engine(engine))
    ctx = SovereignContext(
        organization_id=body.organization_id,
        environment=body.environment,
        principal_id=body.principal_id,
    )
    try:
        result = await svc.simulate_blast_radius_async(
            ctx,
            actor_identity_id=body.actor_identity_id,
            hypothetical_extra_capabilities=frozenset(body.hypothetical_extra_capabilities),
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result.model_dump()


@router.post("/simulate/mission")
async def post_mission(body: MissionBody) -> dict[str, Any]:
    engine = create_engine(":memory:")
    await engine.init()
    svc = SovereignService(store=SovereignCanonicalStore.from_engine(engine))
    ctx = SovereignContext(organization_id=body.organization_id, environment=body.environment)
    result = await svc.simulate_mission_async(ctx, agent_id=body.agent_id, steps=body.steps)
    return result.model_dump()


@router.post("/shadow")
async def post_shadow(body: ShadowBody) -> dict[str, Any]:
    svc = SovereignService()
    ctx = SovereignContext(organization_id=body.organization_id)
    obs = svc.evaluate_shadow(
        ctx,
        agent_id=body.agent_id,
        action_type=body.action_type,
        target=body.target,
    )
    return obs.model_dump()


@router.post("/policy/test")
async def post_policy_test(body: OrgBody, cases: list[dict[str, Any]]) -> dict[str, Any]:
    engine = create_engine(":memory:")
    await engine.init()
    svc = SovereignService(store=SovereignCanonicalStore.from_engine(engine))
    ctx = SovereignContext(organization_id=body.organization_id)
    parsed = [PolicyTestCase(**c) for c in cases]
    report = await svc.run_policy_tests_async(ctx, parsed)
    return report.model_dump()
