# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authenticated browser-safe Sovereign HTTP adapters."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from responsibleai.db.web_identity_repository import WebPrincipal
from responsibleai.governance.policy import PolicyRule
from responsibleai.sovereign.api_deps import build_sovereign_service
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.effective import EffectiveAuthoritySnapshot
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.policy_lab import PolicyTestCase
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.web_auth import (
    guard_browser_tenant_override,
    require_web_csrf,
    web_organization_id,
)

web_router = APIRouter(prefix="/api/web/sovereign", tags=["web-sovereign"])


async def _svc() -> SovereignService:
    return await build_sovereign_service()


class WebTenantBody(BaseModel):
    environment: str | None = "development"

    @model_validator(mode="before")
    @classmethod
    def reject_client_organization_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "organization_id" in data:
            raise HTTPException(400, "organization_id must not be supplied by browser clients.")
        return data


def _web_ctx(principal: WebPrincipal, body: WebTenantBody) -> SovereignContext:
    return SovereignContext(
        organization_id=web_organization_id(principal),
        environment=body.environment or "development",
        principal_id=f"web:{principal.user_id}",
    )


def _tenant_http(exc: SovereignTenantIsolationError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


class WebXRayBody(WebTenantBody):
    pass


@web_router.post("/xray")
async def web_post_xray(
    body: WebXRayBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    try:
        result = await svc.build_xray_async(_web_ctx(principal, body))
    except SovereignTenantIsolationError as exc:
        raise _tenant_http(exc) from exc
    return result.model_dump()


class WebExplainBody(WebTenantBody):
    evidence_id: str | None = None
    identity_id: str | None = None


@web_router.post("/explain")
async def web_post_explain(
    body: WebExplainBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    ctx = _web_ctx(principal, body)
    try:
        if body.evidence_id:
            return (await svc.explain_evidence_async(ctx, body.evidence_id)).model_dump()
        if body.identity_id:
            return (await svc.explain_identity_async(ctx, body.identity_id)).model_dump()
    except SovereignTenantIsolationError as exc:
        raise _tenant_http(exc) from exc
    raise HTTPException(status_code=400, detail="evidence_id or identity_id required")


class WebTraceBody(WebTenantBody):
    evidence_id: str


@web_router.post("/trace")
async def web_post_trace(
    body: WebTraceBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    try:
        return (
            await svc.trace_evidence_async(_web_ctx(principal, body), body.evidence_id)
        ).model_dump()
    except SovereignTenantIsolationError as exc:
        raise _tenant_http(exc) from exc


@web_router.post("/authority/effective")
async def web_post_effective(
    body: WebTenantBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    snap = await svc.load_effective_async(_web_ctx(principal, body))
    return snap.model_dump()


class WebCompareBody(WebTenantBody):
    manifest: dict[str, Any]


@web_router.post("/authority/compare")
async def web_post_compare(
    body: WebCompareBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    from responsibleai.sovereign.manifest import WhitepactManifest

    manifest = WhitepactManifest.model_validate(body.manifest)
    try:
        result = await svc.compare_manifest_async(_web_ctx(principal, body), manifest)
    except SovereignTenantIsolationError as exc:
        raise _tenant_http(exc) from exc
    return result.model_dump()


class WebDriftBody(WebTenantBody):
    manifest: dict[str, Any]


@web_router.post("/authority/drift")
async def web_post_drift(
    body: WebDriftBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    from responsibleai.sovereign.manifest import WhitepactManifest

    manifest = WhitepactManifest.model_validate(body.manifest)
    try:
        report = await svc.detect_drift_async(_web_ctx(principal, body), manifest)
    except SovereignTenantIsolationError as exc:
        raise _tenant_http(exc) from exc
    return report.model_dump()


class WebBlastRadiusBody(WebTenantBody):
    actor_identity_id: str
    hypothetical_extra_capabilities: list[str] = Field(default_factory=list)


@web_router.post("/simulate/blast-radius")
async def web_post_blast_radius(
    body: WebBlastRadiusBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    result = await svc.simulate_blast_radius_async(
        _web_ctx(principal, body),
        actor_identity_id=body.actor_identity_id,
        hypothetical_extra_capabilities=frozenset(body.hypothetical_extra_capabilities),
    )
    return result.model_dump()


class WebMissionBody(WebTenantBody):
    agent_id: str
    steps: list[str]


@web_router.post("/simulate/mission")
async def web_post_mission(
    body: WebMissionBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    return (
        await svc.simulate_mission_async(
            _web_ctx(principal, body), agent_id=body.agent_id, steps=body.steps
        )
    ).model_dump()


class WebShadowBody(WebTenantBody):
    agent_id: str
    action_type: str
    target: str = "shadow:target"
    persist: bool = False


@web_router.post("/shadow")
async def web_post_shadow(
    body: WebShadowBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    ctx = _web_ctx(principal, body)
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


class WebPolicyTestBody(WebTenantBody):
    cases: list[dict[str, Any]]


@web_router.post("/policy/test")
async def web_post_policy_test(
    body: WebPolicyTestBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    cases = [PolicyTestCase(**c) for c in body.cases]
    return (await svc.run_policy_tests_async(_web_ctx(principal, body), cases)).model_dump()


class WebPolicyRulesBody(WebTenantBody):
    rules: list[dict[str, Any]]


@web_router.post("/policy/lint")
async def web_post_policy_lint(
    body: WebPolicyRulesBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    rules = [PolicyRule(**r) for r in body.rules]
    return {"errors": svc.lint_policy_rules(rules)}


@web_router.post("/policy/diff")
async def web_post_policy_diff(
    body: WebPolicyRulesBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    rules = [PolicyRule(**r) for r in body.rules]
    return (await svc.diff_policy_async(_web_ctx(principal, body), rules)).model_dump()


class WebPolicySimBody(WebPolicyRulesBody):
    action_types: list[str]


@web_router.post("/policy/simulate")
async def web_post_policy_simulate(
    body: WebPolicySimBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    rules = [PolicyRule(**r) for r in body.rules]
    return (
        await svc.simulate_policy_async(
            _web_ctx(principal, body), candidate_rules=rules, action_types=body.action_types
        )
    ).model_dump()


class WebGauntletBody(WebTenantBody):
    probe_ids: list[str] | None = None


@web_router.post("/gauntlet")
async def web_post_gauntlet(
    body: WebGauntletBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    return (
        await svc.run_gauntlet_async(_web_ctx(principal, body), probe_ids=body.probe_ids)
    ).model_dump()


class WebFlightBody(WebTenantBody):
    evidence_id: str


@web_router.post("/flight-recorder")
async def web_post_flight(
    body: WebFlightBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    try:
        return (
            await svc.flight_recorder_async(_web_ctx(principal, body), body.evidence_id)
        ).model_dump()
    except SovereignTenantIsolationError as exc:
        raise _tenant_http(exc) from exc


class WebTimeMachineBody(WebTenantBody):
    then_snapshot: dict[str, Any] | None = None


@web_router.post("/time-machine")
async def web_post_time_machine(
    body: WebTimeMachineBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    then = (
        EffectiveAuthoritySnapshot.model_validate(body.then_snapshot)
        if body.then_snapshot
        else None
    )
    return (
        await svc.time_machine_async(_web_ctx(principal, body), then_snapshot=then)
    ).model_dump()


class WebEvidenceBody(WebTenantBody):
    evidence_id: str


@web_router.post("/evidence/correlate")
async def web_post_evidence(
    body: WebEvidenceBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    try:
        return (
            await svc.correlate_evidence_async(_web_ctx(principal, body), body.evidence_id)
        ).model_dump()
    except SovereignTenantIsolationError as exc:
        raise _tenant_http(exc) from exc


class WebCapsuleCreateBody(WebTenantBody):
    authority_subset: dict[str, Any] = Field(default_factory=dict)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


@web_router.post("/capsules")
async def web_post_capsule(
    body: WebCapsuleCreateBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    return svc.create_capsule(
        _web_ctx(principal, body), authority_subset=body.authority_subset, timeline=body.timeline
    ).model_dump()


class WebCapsuleValidateBody(BaseModel):
    capsule: dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def reject_client_organization_id(cls, data: Any) -> Any:
        if isinstance(data, dict) and "organization_id" in data:
            raise HTTPException(400, "organization_id must not be supplied by browser clients.")
        return data


def _assert_capsule_tenant(principal: WebPrincipal, capsule_org: str) -> None:
    org_id = web_organization_id(principal)
    if capsule_org != org_id:
        raise HTTPException(status_code=404, detail="Capsule not found for organization")


@web_router.post("/capsules/validate")
async def web_post_capsule_validate(
    body: WebCapsuleValidateBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    from responsibleai.sovereign.capsule import SovereignCapsule

    cap = SovereignCapsule.model_validate(body.capsule)
    _assert_capsule_tenant(principal, cap.organization_id)
    return {"valid": svc.validate_capsule(cap)}


@web_router.post("/capsules/reproduce")
async def web_post_capsule_reproduce(
    body: WebCapsuleValidateBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    from responsibleai.sovereign.capsule import SovereignCapsule

    cap = SovereignCapsule.model_validate(body.capsule)
    _assert_capsule_tenant(principal, cap.organization_id)
    return svc.reproduce_capsule(cap)


@web_router.post("/authority-bom")
async def web_post_bom(
    body: WebTenantBody,
    _: None = Depends(guard_browser_tenant_override),
    principal: WebPrincipal = Depends(require_web_csrf),
    svc: SovereignService = Depends(_svc),
) -> dict[str, Any]:
    return (await svc.authority_bom_async(_web_ctx(principal, body))).model_dump()
