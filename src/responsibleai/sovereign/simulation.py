# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Zero-effect counterfactual simulators (blast radius, mission)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.risk import RiskTier
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.effective import load_effective_authority
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation


class SimulationMarker(StrEnum):
    COUNTERFACTUAL = "COUNTERFACTUAL"
    ZERO_EFFECT = "ZERO_EFFECT"


class BlastRadiusResult(BaseModel):
    marker: SimulationMarker = SimulationMarker.COUNTERFACTUAL
    organization_id: str
    hypothesis: str
    reachable_capabilities: list[str] = Field(default_factory=list)
    reachable_identity_ids: list[str] = Field(default_factory=list)
    blocked_paths: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MissionStepResult(BaseModel):
    step_index: int
    action_type: str
    disposition: str  # allowed | denied | approval_required | unknown | unreachable
    explanation: str


class MissionSimulationResult(BaseModel):
    marker: SimulationMarker = SimulationMarker.COUNTERFACTUAL
    organization_id: str
    steps: list[MissionStepResult] = Field(default_factory=list)


@zero_effect_operation
async def simulate_blast_radius(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    actor_identity_id: str,
    hypothetical_extra_capabilities: frozenset[str] = frozenset(),
) -> BlastRadiusResult:
    """Counterfactual reachability — never executes consequential actions."""
    effective = await load_effective_authority(store, ctx.organization_id, environment=ctx.environment)
    graph = await store.delegations.get_org_graph(ctx.organization_id)
    reachable_ids: set[str] = set()
    reachable_caps: set[str] = set(effective.capability_ids)
    reachable_caps.update(hypothetical_extra_capabilities)

    def walk(node) -> None:
        reachable_ids.add(node.identity_id)
        if node.delegation and node.delegation.is_active():
            reachable_caps.update(node.delegation.granted_action_types)
        for child in node.children:
            walk(child)

    found = False

    def find_and_walk(node) -> None:
        nonlocal found
        if node.identity_id == actor_identity_id:
            found = True
            walk(node)
            return
        for child in node.children:
            find_and_walk(child)

    for root in graph.roots:
        find_and_walk(root)

    if not found:
        return BlastRadiusResult(
            organization_id=ctx.organization_id,
            hypothesis=f"extra={sorted(hypothetical_extra_capabilities)}",
            reachable_capabilities=sorted(reachable_caps),
            reachable_identity_ids=sorted(reachable_ids),
            blocked_paths=[f"actor {actor_identity_id} not found in delegation forest"],
            notes=["Simulation only — no effects produced"],
        )

    return BlastRadiusResult(
        organization_id=ctx.organization_id,
        hypothesis=f"extra={sorted(hypothetical_extra_capabilities)}",
        reachable_capabilities=sorted(reachable_caps),
        reachable_identity_ids=sorted(reachable_ids),
        notes=["Simulation only — no effects produced"],
    )


@zero_effect_operation
async def simulate_mission(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    agent_id: str,
    steps: list[str],
) -> MissionSimulationResult:
    effective = await load_effective_authority(store, ctx.organization_id, environment=ctx.environment)
    policy = await store.policies.get_policy(ctx.organization_id)
    cap_set = set(effective.capability_ids)
    results: list[MissionStepResult] = []

    identity = IdentityContext(identity_id=agent_id, kind="agent", org_id=ctx.organization_id)
    agent = AgentContext(identity=identity, organization_id=ctx.organization_id, agent_id=agent_id)

    for index, action_type in enumerate(steps):
        if action_type not in cap_set:
            results.append(
                MissionStepResult(
                    step_index=index,
                    action_type=action_type,
                    disposition="unreachable",
                    explanation="Action type not in effective capability set",
                )
            )
            continue
        action = ActionRequest(
            agent=agent,
            action_type=action_type,
            target="simulated:target",
            arguments={},
            purpose="sovereign-mission-simulation",
        )
        match = policy.evaluate(action, RiskTier.LOW)
        if action_type in effective.require_approval_for:
            disposition = "approval_required"
            explanation = "Effective authority marks action as approval-gated"
        elif match is not None and match.rule.effect in (
            GovernanceDecision.DENY,
            GovernanceDecision.REQUIRE_APPROVAL,
        ):
            disposition = (
                "approval_required"
                if match.rule.effect == GovernanceDecision.REQUIRE_APPROVAL
                else "denied"
            )
            explanation = f"Policy rule {match.rule.rule_id} -> {match.rule.effect.value}"
        else:
            disposition = "allowed"
            explanation = "Within effective capability and policy simulation"
        results.append(
            MissionStepResult(
                step_index=index,
                action_type=action_type,
                disposition=disposition,
                explanation=explanation,
            )
        )

    return MissionSimulationResult(organization_id=ctx.organization_id, steps=results)
