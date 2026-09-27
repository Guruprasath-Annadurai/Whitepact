# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.errors import CausalCycleError
from responsibleai.formula.future.facts import ConsequenceSemanticKey
from responsibleai.formula.future.models import Reversibility

WitnessFingerprint = tuple


@dataclass(frozen=True, slots=True)
class CausalDerivation:
    rule_id: str
    output_key: ConsequenceSemanticKey
    prerequisite_keys: tuple[ConsequenceSemanticKey, ...]
    prerequisite_witness_fingerprints: tuple[WitnessFingerprint, ...]
    graph_edge_ids: tuple[str, ...]
    trajectory_depth: int
    causal_depth: int
    epistemic_status: EpistemicStatus
    reversibility: Reversibility
    information_sensitive: bool
    subject_id: str
    capability_semantic_key: tuple | None = None

    def witness_fingerprint(self) -> WitnessFingerprint:
        return (
            self.rule_id,
            self.output_key,
            self.prerequisite_keys,
            self.prerequisite_witness_fingerprints,
            self.graph_edge_ids,
            self.trajectory_depth,
            self.causal_depth,
            self.epistemic_status.value,
            self.reversibility.value,
            self.information_sensitive,
            self.subject_id,
            self.capability_semantic_key,
        )


class CausalWitnessDag:
    """Multi-witness provenance per semantic consequence key."""

    def __init__(self) -> None:
        self._children: dict[ConsequenceSemanticKey, set[ConsequenceSemanticKey]] = {}
        self._by_fingerprint: dict[WitnessFingerprint, CausalDerivation] = {}
        self._by_output: dict[ConsequenceSemanticKey, list[WitnessFingerprint]] = {}

    def add_witness(self, witness: CausalDerivation) -> bool:
        fp = witness.witness_fingerprint()
        if fp in self._by_fingerprint:
            return False
        key = witness.output_key
        for prereq in witness.prerequisite_keys:
            if self._can_reach_output_to_prereq(key, prereq):
                raise CausalCycleError(
                    f"causal provenance cycle: {prereq!r} -> {key!r} via {witness.rule_id!r}"
                )
        self._by_fingerprint[fp] = witness
        self._by_output.setdefault(key, []).append(fp)
        self._by_output[key].sort()
        for prereq in witness.prerequisite_keys:
            self._children.setdefault(prereq, set()).add(key)
        return True

    def _can_reach_output_to_prereq(
        self, output: ConsequenceSemanticKey, prereq: ConsequenceSemanticKey
    ) -> bool:
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

    def get_witnesses(self, key: ConsequenceSemanticKey) -> tuple[CausalDerivation, ...]:
        fps = self._by_output.get(key, ())
        return tuple(self._by_fingerprint[fp] for fp in fps)

    def get_witness(self, key: ConsequenceSemanticKey) -> CausalDerivation | None:
        witnesses = self.get_witnesses(key)
        return witnesses[0] if witnesses else None

    def has_fingerprint(self, fp: WitnessFingerprint) -> bool:
        return fp in self._by_fingerprint

    def get_by_fingerprint(self, fp: WitnessFingerprint) -> CausalDerivation | None:
        return self._by_fingerprint.get(fp)

    def all_witnesses(self) -> tuple[CausalDerivation, ...]:
        return tuple(sorted(self._by_fingerprint.values(), key=lambda w: w.witness_fingerprint()))
