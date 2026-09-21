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
from responsibleai.sovereign.graph import GraphQueryBudget
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.tenant import assert_same_organization
from responsibleai.sovereign.zero_effect import zero_effect_operation


class SimulationMarker(StrEnum):
    COUNTERFACTUAL = "COUNTERFACTUAL"
    ZERO_EFFECT = "ZERO_EFFECT"


class MissionDisposition(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    UNKNOWN = "UNKNOWN"
    UNREACHABLE = "UNREACHABLE"


class BlastRadiusResult(BaseModel):
    marker: SimulationMarker = SimulationMarker.COUNTERFACTUAL
    organization_id: str
    hypothesis: str
    reachable_capabilities: list[str] = Field(default_factory=list)
    newly_reachable_capabilities: list[str] = Field(default_factory=list)
    no_longer_reachable_capabilities: list[str] = Field(default_factory=list)
    reachable_identity_ids: list[str] = Field(default_factory=list)
    transitive_paths: list[list[str]] = Field(default_factory=list)
    blocked_paths: list[str] = Field(default_factory=list)
    policy_boundaries: list[str] = Field(default_factory=list)
    unknown_paths: list[str] = Field(default_factory=list)
    affected_targets: list[str] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)
    truncated: bool = False
    budget: GraphQueryBudget = Field(default_factory=GraphQueryBudget)
    unknowns: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MissionStepSpec(BaseModel):
    action_type: str
    target: str = "simulated:target"
    risk_tier: str = "LOW"
    requires_prior_step: bool = False


class MissionStepResult(BaseModel):
    step_index: int
    action: str
    target: str
    required_capability: str
    disposition: MissionDisposition
    policy_result: str | None = None
    approval_required: bool = False
    depends_on_previous: bool = False
    stop_reason: str | None = None
    unknown_facts: list[str] = Field(default_factory=list)
    explanation: str


class MissionSimulationResult(BaseModel):
    marker: SimulationMarker = SimulationMarker.COUNTERFACTUAL
    organization_id: str
    steps: list[MissionStepResult] = Field(default_factory=list)
    would_stop_at_step: int | None = None


def _collect_actor_subtree(
    node,
    *,
    budget: GraphQueryBudget,
    visited: set[str],
    paths: list[list[str]],
    reachable_ids: set[str],
    reachable_caps: set[str],
    state: dict[str, int],
    prefix: list[str],
) -> None:
    if state["nodes"] > budget.max_nodes or node.identity_id in visited:
        return
    visited.add(node.identity_id)
    state["nodes"] += 1
    reachable_ids.add(node.identity_id)
    if node.delegation and node.delegation.is_active():
        for cap in node.delegation.granted_action_types:
            reachable_caps.add(cap)
            if len(paths) < budget.max_edges:
                paths.append(prefix + [cap])
    if state["depth"] >= budget.max_depth:
        return
    for child in node.children:
        state["depth"] += 1
        _collect_actor_subtree(
            child,
            budget=budget,
            visited=visited,
            paths=paths,
            reachable_ids=reachable_ids,
            reachable_caps=reachable_caps,
            state=state,
            prefix=prefix + [child.identity_id],
        )
        state["depth"] -= 1


def _find_actor_and_collect(
    node,
    *,
    actor_id: str,
    budget: GraphQueryBudget,
    visited: set[str],
    paths: list[list[str]],
    reachable_ids: set[str],
    reachable_caps: set[str],
    state: dict[str, int],
) -> bool:
    if node.identity_id == actor_id:
        _collect_actor_subtree(
            node,
            budget=budget,
            visited=visited,
            paths=paths,
            reachable_ids=reachable_ids,
            reachable_caps=reachable_caps,
            state=state,
            prefix=[actor_id],
        )
        return True
    for child in node.children:
        if _find_actor_and_collect(
            child,
            actor_id=actor_id,
            budget=budget,
            visited=visited,
            paths=paths,
            reachable_ids=reachable_ids,
            reachable_caps=reachable_caps,
            state=state,
        ):
            return True
    return False


@zero_effect_operation
async def simulate_blast_radius(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    actor_identity_id: str,
    hypothetical_extra_capabilities: frozenset[str] = frozenset(),
    hypothetical_removed_capabilities: frozenset[str] = frozenset(),
    target: str | None = None,
    budget: GraphQueryBudget | None = None,
) -> BlastRadiusResult:
    """Counterfactual reachability — never executes consequential actions."""
    assert_same_organization(ctx.organization_id, ctx.organization_id, resource_kind="blast-radius")
    query_budget = budget or GraphQueryBudget()
    effective = await load_effective_authority(
        store, ctx.organization_id, environment=ctx.environment
    )
    graph = await store.delegations.get_org_graph(ctx.organization_id)
    baseline_caps = set(effective.capability_ids)
    reachable_ids: set[str] = set()
    reachable_caps: set[str] = set(baseline_caps)
    paths: list[list[str]] = []
    visited: set[str] = set()
    state = {"nodes": 0, "depth": 0}

    actor_found = False
    for root in graph.roots:
        if _find_actor_and_collect(
            root,
            actor_id=actor_identity_id,
            budget=query_budget,
            visited=visited,
            paths=paths,
            reachable_ids=reachable_ids,
            reachable_caps=reachable_caps,
            state=state,
        ):
            actor_found = True

    counterfactual = set(reachable_caps)
    counterfactual.update(hypothetical_extra_capabilities)
    counterfactual.difference_update(hypothetical_removed_capabilities)

    newly = sorted(counterfactual - baseline_caps)
    lost = sorted(baseline_caps - counterfactual)

    policy = await store.policies.get_policy(ctx.organization_id)
    policy_boundaries = [f"policy_version={policy.version}"]

    truncated = state["nodes"] >= query_budget.max_nodes
    result = BlastRadiusResult(
        organization_id=ctx.organization_id,
        hypothesis=(
            f"extra={sorted(hypothetical_extra_capabilities)} "
            f"removed={sorted(hypothetical_removed_capabilities)}"
        ),
        reachable_capabilities=sorted(counterfactual),
        newly_reachable_capabilities=newly,
        no_longer_reachable_capabilities=lost,
        reachable_identity_ids=sorted(reachable_ids),
        transitive_paths=paths[: query_budget.max_edges],
        policy_boundaries=policy_boundaries,
        affected_targets=[target] if target else [],
        provenance=["DelegationRepository.get_org_graph", "load_effective_authority"],
        truncated=truncated,
        budget=query_budget,
        notes=["Simulation only — no effects produced"],
    )
    if not actor_found:
        result.blocked_paths.append(f"actor {actor_identity_id} not found in delegation forest")
        result.unknowns.append("actor_subtree_unreachable")
    if truncated:
        result.unknown_paths.append("graph_budget_exceeded")
    return result


@zero_effect_operation
async def simulate_mission(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    agent_id: str,
    steps: list[MissionStepSpec] | list[str],
) -> MissionSimulationResult:
    effective = await load_effective_authority(
        store, ctx.organization_id, environment=ctx.environment
    )
    policy = await store.policies.get_policy(ctx.organization_id)
    cap_set = set(effective.capability_ids)
    results: list[MissionStepResult] = []
    prior_ok = True
    stop_at: int | None = None

    identity = IdentityContext(identity_id=agent_id, kind="agent", org_id=ctx.organization_id)
    agent = AgentContext(identity=identity, organization_id=ctx.organization_id, agent_id=agent_id)

    normalized: list[MissionStepSpec] = []
    for item in steps:
        if isinstance(item, str):
            normalized.append(MissionStepSpec(action_type=item))
        else:
            normalized.append(item)

    for index, spec in enumerate(normalized):
        action_type = spec.action_type
        if spec.requires_prior_step and not prior_ok:
            disposition = MissionDisposition.UNREACHABLE
            explanation = "Prior required step did not succeed in simulation"
            results.append(
                MissionStepResult(
                    step_index=index,
                    action=action_type,
                    target=spec.target,
                    required_capability=action_type,
                    disposition=disposition,
                    depends_on_previous=True,
                    stop_reason="dependency_failed",
                    explanation=explanation,
                )
            )
            if stop_at is None:
                stop_at = index
            prior_ok = False
            continue

        if action_type not in cap_set:
            results.append(
                MissionStepResult(
                    step_index=index,
                    action=action_type,
                    target=spec.target,
                    required_capability=action_type,
                    disposition=MissionDisposition.UNREACHABLE,
                    explanation="Action type not in effective capability set",
                    stop_reason="capability_missing",
                )
            )
            if stop_at is None:
                stop_at = index
            prior_ok = False
            continue

        tier = RiskTier(spec.risk_tier) if spec.risk_tier in RiskTier.__members__ else RiskTier.LOW
        action = ActionRequest(
            agent=agent,
            action_type=action_type,
            target=spec.target,
            arguments={},
            purpose="sovereign-mission-simulation",
        )
        match = policy.evaluate(action, tier)
        approval_required = action_type in effective.require_approval_for
        unknown_facts: list[str] = []
        policy_result: str | None = None
        if approval_required:
            disposition = MissionDisposition.APPROVAL_REQUIRED
            explanation = "Effective authority marks action as approval-gated"
            policy_result = "REQUIRE_APPROVAL"
            step_ok = False
        elif match is None:
            disposition = MissionDisposition.UNKNOWN
            explanation = "No policy rule matched — disposition UNKNOWN"
            policy_result = None
            step_ok = False
            unknown_facts = ["policy_match_missing"]
        elif match is not None and match.rule.effect == GovernanceDecision.REQUIRE_APPROVAL:
            disposition = MissionDisposition.APPROVAL_REQUIRED
            explanation = f"Policy rule {match.rule.rule_id} -> REQUIRE_APPROVAL"
            policy_result = match.rule.effect.value
            step_ok = False
        elif match is not None and match.rule.effect == GovernanceDecision.DENY:
            disposition = MissionDisposition.DENY
            explanation = f"Policy rule {match.rule.rule_id} -> DENY"
            policy_result = match.rule.effect.value
            step_ok = False
        else:
            disposition = MissionDisposition.ALLOW
            explanation = "Within effective capability and policy simulation"
            policy_result = match.rule.effect.value if match else None
            step_ok = True

        results.append(
            MissionStepResult(
                step_index=index,
                action=action_type,
                target=spec.target,
                required_capability=action_type,
                disposition=disposition,
                policy_result=policy_result,
                approval_required=approval_required,
                depends_on_previous=spec.requires_prior_step,
                stop_reason=None if step_ok else disposition.value,
                unknown_facts=unknown_facts if disposition == MissionDisposition.UNKNOWN else [],
                explanation=explanation,
            )
        )
        if not step_ok and stop_at is None:
            stop_at = index
        prior_ok = step_ok

    return MissionSimulationResult(
        organization_id=ctx.organization_id,
        steps=results,
        would_stop_at_step=stop_at,
    )
