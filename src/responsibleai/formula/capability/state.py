# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field

from responsibleai.formula.capability.derivation import (
    CapabilityDerivation,
    SemanticKey,
    witness_sort_key,
)
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.support_aggregate import aggregate_fact_from_witnesses
from responsibleai.formula.capability.witness_dag import would_create_witness_cycle


@dataclass
class CapabilityClosureState:
    facts_by_key: dict[SemanticKey, CapabilityFact] = field(default_factory=dict)
    witnesses_by_key: dict[SemanticKey, list[CapabilityDerivation]] = field(default_factory=dict)
    witness_by_fingerprint: dict[tuple, CapabilityDerivation] = field(default_factory=dict)
    witness_fingerprints: set[tuple] = field(default_factory=set)
    frontier_blocked: bool = False
    truncation_notes: list[str] = field(default_factory=list)
    budget_truncated: bool = False

    def sorted_witnesses(self, key: SemanticKey) -> tuple[CapabilityDerivation, ...]:
        items = self.witnesses_by_key.get(key, ())
        return tuple(sorted(items, key=witness_sort_key))

    def add_witness(
        self,
        fact: CapabilityFact,
        witness: CapabilityDerivation,
        *,
        max_facts: int | None = None,
        max_derivations: int | None = None,
    ) -> tuple[bool, bool]:
        """Return (witness_added, fact_added)."""
        if would_create_witness_cycle(witness, self.witness_by_fingerprint):
            return False, False

        key = fact.semantic_key()
        fp = witness.witness_fingerprint()
        if fp in self.witness_fingerprints:
            return False, False

        if max_derivations is not None and len(self.witness_fingerprints) >= max_derivations:
            self.budget_truncated = True
            self.truncation_notes.append("max_derivations limit reached")
            return False, False

        new_fact = key not in self.facts_by_key
        if new_fact and max_facts is not None and len(self.facts_by_key) >= max_facts:
            self.budget_truncated = True
            self.truncation_notes.append("max_facts limit reached")
            return False, False

        self.witness_fingerprints.add(fp)
        self.witness_by_fingerprint[fp] = witness
        self.witnesses_by_key.setdefault(key, []).append(witness)

        if new_fact:
            self.facts_by_key[key] = fact
        else:
            base = self.facts_by_key[key]
            self.facts_by_key[key] = aggregate_fact_from_witnesses(base, self.sorted_witnesses(key))
        return True, new_fact

    def all_witnesses(self) -> tuple[CapabilityDerivation, ...]:
        items: list[CapabilityDerivation] = []
        for key in sorted(self.witnesses_by_key.keys()):
            items.extend(self.sorted_witnesses(key))
        return tuple(items)

    def ordered_facts(self) -> tuple[CapabilityFact, ...]:
        return tuple(self.facts_by_key[k] for k in sorted(self.facts_by_key.keys()))
