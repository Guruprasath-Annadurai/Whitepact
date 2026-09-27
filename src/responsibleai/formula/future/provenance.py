# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CausalCycleError
from responsibleai.formula.future.facts import ConsequenceSemanticKey


@dataclass(frozen=True, slots=True)
class CausalDerivation:
    rule_id: str
    output_key: ConsequenceSemanticKey
    prerequisite_keys: tuple[ConsequenceSemanticKey, ...]
    prerequisite_witness_fingerprints: tuple[tuple, ...]
    graph_edge_ids: tuple[str, ...]
    trajectory_depth: int
    epistemic_status: EpistemicStatus
    capability_semantic_key: tuple | None = None

    def witness_fingerprint(self) -> tuple:
        return (
            self.rule_id,
            self.output_key,
            self.prerequisite_keys,
            self.prerequisite_witness_fingerprints,
            self.graph_edge_ids,
            self.trajectory_depth,
            self.epistemic_status.value,
            self.capability_semantic_key,
        )


class CausalWitnessDag:
    """Prevent provenance cycles at insertion time."""

    def __init__(self) -> None:
        self._children: dict[ConsequenceSemanticKey, set[ConsequenceSemanticKey]] = {}
        self._parents: dict[ConsequenceSemanticKey, set[ConsequenceSemanticKey]] = {}
        self._witnesses: dict[ConsequenceSemanticKey, CausalDerivation] = {}

    def add_witness(self, witness: CausalDerivation) -> None:
        key = witness.output_key
        for prereq in witness.prerequisite_keys:
            if self._can_reach_output_to_prereq(key, prereq):
                raise CausalCycleError(
                    f"causal provenance cycle: {prereq!r} -> {key!r} via {witness.rule_id!r}"
                )
        if key in self._witnesses:
            return
        self._witnesses[key] = witness
        for prereq in witness.prerequisite_keys:
            self._children.setdefault(prereq, set()).add(key)
            self._parents.setdefault(key, set()).add(prereq)

    def _can_reach_output_to_prereq(
        self, output: ConsequenceSemanticKey, prereq: ConsequenceSemanticKey
    ) -> bool:
        """True if adding `prereq -> output` would close a cycle in the derivation DAG."""
        if output == prereq:
            return True
        stack = [output]
        seen: set[ConsequenceSemanticKey] = set()
        while stack:
            current = stack.pop()
            if current == prereq:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(self._children.get(current, ()))
        return False

    def get_witness(self, key: ConsequenceSemanticKey) -> CausalDerivation | None:
        return self._witnesses.get(key)

    def all_witnesses(self) -> tuple[CausalDerivation, ...]:
        return tuple(sorted(self._witnesses.values(), key=lambda w: w.witness_fingerprint()))
