# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""HTTP API for Sovereign — thin handlers over SovereignService."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from responsibleai.governance.policy import PolicyRule
from responsibleai.sovereign.api_deps import build_sovereign_service
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.effective import EffectiveAuthoritySnapshot
from responsibleai.sovereign.errors import SovereignCapabilityError, SovereignTenantIsolationError
from responsibleai.sovereign.policy_lab import PolicyTestCase
from responsibleai.sovereign.service import SovereignService

router = APIRouter(prefix="/api/sovereign", tags=["sovereign"])
web_router = APIRouter(prefix="/api/web/sovereign", tags=["web-sovereign"])


async def _svc() -> SovereignService:
    return await build_sovereign_service()


class OrgBody(BaseModel):
    organization_id: str
    environment: str | None = "development"
    principal_id: str | None = None


def _ctx(body: OrgBody) -> SovereignContext:
    return SovereignContext(
        organization_id=body.organization_id,
        environment=body.environment or "development",
        principal_id=body.principal_id,
    )


def _route(fn):
    async def wrapper(*args, **kwargs):
        try:
            return await fn(*args, **kwargs)
        except SovereignTenantIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except SovereignCapabilityError as exc:
            raise HTTPException(status_code=501, detail=str(exc)) from exc

    return wrapper


@router.get("/status")
async def sovereign_status(svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    return svc.get_status().model_dump()


@router.get("/capabilities")
async def sovereign_capabilities(svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    return svc.get_capabilities().model_dump()


class XRayBody(OrgBody):
    pass


@router.post("/xray")
async def post_xray(body: XRayBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    result = await svc.build_xray_async(_ctx(body))
    return result.model_dump()


class ExplainBody(OrgBody):
    evidence_id: str | None = None
    identity_id: str | None = None


@router.post("/explain")
async def post_explain(body: ExplainBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    ctx = _ctx(body)
    if body.evidence_id:
        return (await svc.explain_evidence_async(ctx, body.evidence_id)).model_dump()
    if body.identity_id:
        return (await svc.explain_identity_async(ctx, body.identity_id)).model_dump()
    raise HTTPException(status_code=400, detail="evidence_id or identity_id required")


class TraceBody(OrgBody):
    evidence_id: str


@router.post("/trace")
async def post_trace(body: TraceBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    return (await svc.trace_evidence_async(_ctx(body), body.evidence_id)).model_dump()


@router.post("/authority/effective")
async def post_effective(body: OrgBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    snap = await svc.load_effective_async(_ctx(body))
    return snap.model_dump()


class CompareBody(OrgBody):
    manifest: dict[str, Any]


@router.post("/authority/compare")
async def post_compare(body: CompareBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    from responsibleai.sovereign.manifest import WhitepactManifest

    manifest = WhitepactManifest.model_validate(body.manifest)
    result = await svc.compare_manifest_async(_ctx(body), manifest)
    return result.model_dump()


class DriftBody(OrgBody):
    manifest: dict[str, Any]


@router.post("/authority/drift")
async def post_drift(body: DriftBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    from responsibleai.sovereign.manifest import WhitepactManifest

    manifest = WhitepactManifest.model_validate(body.manifest)
    report = await svc.detect_drift_async(_ctx(body), manifest)
    return report.model_dump()


class BlastRadiusBody(OrgBody):
    actor_identity_id: str
    hypothetical_extra_capabilities: list[str] = Field(default_factory=list)


@router.post("/simulate/blast-radius")
async def post_blast_radius(
    body: BlastRadiusBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    result = await svc.simulate_blast_radius_async(
        _ctx(body),
        actor_identity_id=body.actor_identity_id,
        hypothetical_extra_capabilities=frozenset(body.hypothetical_extra_capabilities),
    )
    return result.model_dump()


class MissionBody(OrgBody):
    agent_id: str
    steps: list[str]


@router.post("/simulate/mission")
async def post_mission(body: MissionBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    return (
        await svc.simulate_mission_async(_ctx(body), agent_id=body.agent_id, steps=body.steps)
    ).model_dump()


class ShadowBody(OrgBody):
    agent_id: str
    action_type: str
    target: str = "shadow:target"
    persist: bool = False


@router.post("/shadow")
async def post_shadow(body: ShadowBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    ctx = _ctx(body)
    if body.persist:
        row = await svc.evaluate_shadow_persisted_async(
            ctx,
            agent_id=body.agent_id,
            action_type=body.action_type,
            target=body.target,
        )
        return row.model_dump()
    return svc.evaluate_shadow(
        ctx, agent_id=body.agent_id, action_type=body.action_type, target=body.target
    ).model_dump()


class PolicyTestBody(OrgBody):
    cases: list[dict[str, Any]]


@router.post("/policy/test")
async def post_policy_test(
    body: PolicyTestBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    cases = [PolicyTestCase(**c) for c in body.cases]
    return (await svc.run_policy_tests_async(_ctx(body), cases)).model_dump()


class PolicyRulesBody(OrgBody):
    rules: list[dict[str, Any]]


@router.post("/policy/lint")
async def post_policy_lint(
    body: PolicyRulesBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    rules = [PolicyRule(**r) for r in body.rules]
    return {"errors": svc.lint_policy_rules(rules)}


@router.post("/policy/diff")
async def post_policy_diff(
    body: PolicyRulesBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    rules = [PolicyRule(**r) for r in body.rules]
    return (await svc.diff_policy_async(_ctx(body), rules)).model_dump()


class PolicySimBody(PolicyRulesBody):
    action_types: list[str]


@router.post("/policy/simulate")
async def post_policy_simulate(
    body: PolicySimBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    rules = [PolicyRule(**r) for r in body.rules]
    return (
        await svc.simulate_policy_async(
            _ctx(body), candidate_rules=rules, action_types=body.action_types
        )
    ).model_dump()


class GauntletBody(OrgBody):
    probe_ids: list[str] | None = None


@router.post("/gauntlet")
async def post_gauntlet(
    body: GauntletBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    return (await svc.run_gauntlet_async(_ctx(body), probe_ids=body.probe_ids)).model_dump()


class FlightBody(OrgBody):
    evidence_id: str


@router.post("/flight-recorder")
async def post_flight(body: FlightBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    return (await svc.flight_recorder_async(_ctx(body), body.evidence_id)).model_dump()


class TimeMachineBody(OrgBody):
    then_snapshot: dict[str, Any] | None = None


@router.post("/time-machine")
async def post_time_machine(
    body: TimeMachineBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    then = (
        EffectiveAuthoritySnapshot.model_validate(body.then_snapshot)
        if body.then_snapshot
        else None
    )
    return (await svc.time_machine_async(_ctx(body), then_snapshot=then)).model_dump()


class EvidenceBody(OrgBody):
    evidence_id: str


@router.post("/evidence/correlate")
async def post_evidence(
    body: EvidenceBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    return (await svc.correlate_evidence_async(_ctx(body), body.evidence_id)).model_dump()


class CapsuleCreateBody(OrgBody):
    authority_subset: dict[str, Any] = Field(default_factory=dict)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/capsules")
async def post_capsule(
    body: CapsuleCreateBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    return svc.create_capsule(
        _ctx(body), authority_subset=body.authority_subset, timeline=body.timeline
    ).model_dump()


class CapsuleValidateBody(BaseModel):
    capsule: dict[str, Any]


@router.post("/capsules/validate")
async def post_capsule_validate(
    body: CapsuleValidateBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    from responsibleai.sovereign.capsule import SovereignCapsule

    cap = SovereignCapsule.model_validate(body.capsule)
    return {"valid": svc.validate_capsule(cap)}


@router.post("/capsules/reproduce")
async def post_capsule_reproduce(
    body: CapsuleValidateBody, svc: SovereignService = Depends(_svc)
) -> dict[str, Any]:
    from responsibleai.sovereign.capsule import SovereignCapsule

    cap = SovereignCapsule.model_validate(body.capsule)
    return svc.reproduce_capsule(cap)


@router.post("/authority-bom")
async def post_bom(body: OrgBody, svc: SovereignService = Depends(_svc)) -> dict[str, Any]:
    return (await svc.authority_bom_async(_ctx(body))).model_dump()


# Web session mirror (same service layer)
web_router.add_api_route("/status", sovereign_status, methods=["GET"])
web_router.add_api_route("/capabilities", sovereign_capabilities, methods=["GET"])
