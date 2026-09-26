# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.capability.budget import CapabilityClosureBudget, ClosureStatus
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.extraction import extract_direct_capabilities
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.rules import apply_composition_rules
from responsibleai.formula.errors import CapabilityTenantMismatch
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
) -> CapabilityClosureResult:
    """Least fixed-point capability closure over explicit rules and seeds."""
    b = budget or CapabilityClosureBudget()
    facts_by_key: dict[tuple, CapabilityFact] = {}
    derivations: list[CapabilityDerivation] = []
    unresolved: list[str] = []

    for seed in seeds:
        if seed.tenant_id != snapshot.tenant_id:
            raise CapabilityTenantMismatch("seed tenant mismatch")
        facts_by_key[seed.semantic_key()] = seed

    for fact in extract_direct_capabilities(snapshot):
        facts_by_key.setdefault(fact.semantic_key(), fact)

    iterations = 0
    rule_apps = 0
    status = ClosureStatus.COMPLETE
    hit_limit = False

    while iterations < b.max_iterations:
        iterations += 1
        if len(facts_by_key) >= b.max_facts:
            hit_limit = True
            break
        remaining_rule_budget = b.max_rule_applications - rule_apps
        if remaining_rule_budget <= 0:
            hit_limit = True
            break
        apps = apply_composition_rules(
            snapshot,
            facts_by_key,
            max_path_depth=b.max_path_depth,
            rule_budget=remaining_rule_budget,
        )
        if not apps:
            break
        new_any = False
        for app in apps:
            rule_apps += 1
            if len(derivations) >= b.max_derivations:
                hit_limit = True
                break
            key = app.fact.semantic_key()
            if key not in facts_by_key:
                facts_by_key[key] = app.fact
                new_any = True
            derivations.append(app.witness)
        if hit_limit:
            break
        if not new_any:
            break
    else:
        hit_limit = True

    if hit_limit:
        status = ClosureStatus.INCOMPLETE
    elif any(f.epistemic_status.name == "UNKNOWN" for f in facts_by_key.values()):
        status = ClosureStatus.UNKNOWN
        unresolved.append("one or more facts retain UNKNOWN epistemic status")

    ordered_facts = tuple(facts_by_key[k] for k in sorted(facts_by_key.keys()))
    ordered_derivations = tuple(
        sorted(derivations, key=lambda d: (d.rule_id, d.output_semantic_key))
    )

    return CapabilityClosureResult(
        tenant_id=snapshot.tenant_id,
        graph_version_number=snapshot.version.version_number,
        graph_content_hash=snapshot.content_hash,
        facts=ordered_facts,
        derivations=ordered_derivations,
        status=status,
        iterations=iterations,
        rule_applications=rule_apps,
        budget=b,
        unresolved_notes=tuple(unresolved),
    )
