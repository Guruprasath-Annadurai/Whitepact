# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field

from responsibleai.formula.capability.derivation import CapabilityDerivation, SemanticKey
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.models import CapabilityKind


@dataclass
class CapabilityClosureState:
    facts_by_key: dict[SemanticKey, CapabilityFact] = field(default_factory=dict)
    witnesses_by_key: dict[SemanticKey, list[CapabilityDerivation]] = field(default_factory=dict)
    depth_by_key: dict[SemanticKey, int] = field(default_factory=dict)
    witness_fingerprints: set[tuple] = field(default_factory=set)
    frontier_blocked: bool = False
    truncation_notes: list[str] = field(default_factory=list)
    budget_truncated: bool = False

    def max_depth(self, key: SemanticKey) -> int:
        return self.depth_by_key.get(key, 0)

    def best_route(self, key: SemanticKey) -> tuple[str, ...]:
        witnesses = self.witnesses_by_key.get(key, ())
        if not witnesses:
            fact = self.facts_by_key.get(key)
            if fact is None:
                return ()
            return (fact.actor.member_ids[0], fact.target_node_id)
        return max(witnesses, key=lambda w: len(w.route_node_ids)).route_node_ids

    def add_witness(
        self,
        fact: CapabilityFact,
        witness: CapabilityDerivation,
        *,
        is_direct: bool,
    ) -> tuple[bool, bool]:
        """Return (witness_added, fact_added)."""
        key = fact.semantic_key()
        fp = witness.witness_fingerprint()
        new_fp = fp not in self.witness_fingerprints
        if new_fp:
            self.witness_fingerprints.add(fp)
            self.witnesses_by_key.setdefault(key, []).append(witness)
        existing = self.facts_by_key.get(key)
        new_fact = existing is None
        if existing is None:
            self.facts_by_key[key] = fact
            self.depth_by_key[key] = witness.derivation_depth
            return new_fp, new_fact
        merged_epistemic = compose_epistemic(existing.epistemic_status, fact.epistemic_status)
        kind = existing.kind
        if is_direct and existing.kind != CapabilityKind.COMPOSED:
            kind = fact.kind
        elif not is_direct and existing.kind == CapabilityKind.COMPOSED:
            kind = existing.kind
        self.facts_by_key[key] = CapabilityFact(
            tenant_id=existing.tenant_id,
            actor=existing.actor,
            action=existing.action,
            target_node_id=existing.target_node_id,
            kind=kind,
            epistemic_status=merged_epistemic,
            is_direct=existing.is_direct or is_direct,
        )
        self.depth_by_key[key] = max(self.depth_by_key[key], witness.derivation_depth)
        return new_fp, new_fact

    def all_witnesses(self) -> tuple[CapabilityDerivation, ...]:
        items: list[CapabilityDerivation] = []
        for key in sorted(self.witnesses_by_key.keys()):
            items.extend(
                sorted(
                    self.witnesses_by_key[key],
                    key=lambda w: w.witness_fingerprint(),
                )
            )
        return tuple(items)

    def ordered_facts(self) -> tuple[CapabilityFact, ...]:
        return tuple(self.facts_by_key[k] for k in sorted(self.facts_by_key.keys()))
