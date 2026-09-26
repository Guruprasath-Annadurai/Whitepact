# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.capability.budget import CapabilityClosureBudget, ClosureStatus
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.extraction import extract_direct_into_state
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.joint import JointCapabilityRule, apply_joint_rules
from responsibleai.formula.capability.rules import apply_composition_rules
from responsibleai.formula.capability.seeds import validate_and_ingest_seeds
from responsibleai.formula.capability.state import CapabilityClosureState
from responsibleai.formula.graph.snapshot import GraphSnapshot
from responsibleai.formula.version import FORMULA_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class CapabilityClosureResult:
    tenant_id: str
    graph_version_number: int
    graph_content_hash: str
    facts: tuple[CapabilityFact, ...]
    derivations: tuple[CapabilityDerivation, ...]
    status: ClosureStatus
    iterations: int
    rule_applications: int
    budget: CapabilityClosureBudget
    unresolved_notes: tuple[str, ...]
    schema_version: str = FORMULA_SCHEMA_VERSION


def compute_capability_closure(
    snapshot: GraphSnapshot,
    *,
    seeds: tuple[CapabilityFact, ...] = (),
    budget: CapabilityClosureBudget | None = None,
    joint_rules: tuple[JointCapabilityRule, ...] = (),
) -> CapabilityClosureResult:
    """Least fixed-point capability closure over explicit rules and seeds."""
    b = budget or CapabilityClosureBudget()
    b.validate()
    state = CapabilityClosureState()

    validate_and_ingest_seeds(snapshot, seeds, state)
    extract_direct_into_state(snapshot, state, max_path_depth=b.max_path_depth)

    iterations = 0
    rule_apps = 0
    changed = True

    while changed and iterations < b.max_iterations:
        iterations += 1
        if len(state.facts_by_key) >= b.max_facts:
            state.budget_truncated = True
            state.truncation_notes.append("max_facts limit reached")
            break
        remaining = b.max_rule_applications - rule_apps
        if remaining <= 0:
            state.budget_truncated = True
            state.truncation_notes.append("max_rule_applications limit reached")
            break
        if len(state.all_witnesses()) >= b.max_derivations:
            state.budget_truncated = True
            state.truncation_notes.append("max_derivations limit reached")
            break

        produced = apply_composition_rules(
            snapshot,
            state,
            max_path_depth=b.max_path_depth,
            rule_budget=remaining,
        )
        produced += apply_joint_rules(
            state,
            joint_rules,
            max_path_depth=b.max_path_depth,
            rule_budget=remaining - produced,
        )
        rule_apps += produced
        changed = produced > 0
    else:
        if iterations >= b.max_iterations:
            state.budget_truncated = True
            state.truncation_notes.append("max_iterations limit reached")

    notes = list(dict.fromkeys(state.truncation_notes))
    if state.frontier_blocked or state.budget_truncated:
        status = ClosureStatus.INCOMPLETE
    else:
        status = ClosureStatus.COMPLETE

    return CapabilityClosureResult(
        tenant_id=snapshot.tenant_id,
        graph_version_number=snapshot.version.version_number,
        graph_content_hash=snapshot.content_hash,
        facts=state.ordered_facts(),
        derivations=state.all_witnesses(),
        status=status,
        iterations=iterations,
        rule_applications=rule_apps,
        budget=b,
        unresolved_notes=tuple(notes),
    )
