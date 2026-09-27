# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.derivation import CapabilityDerivation, SemanticKey


def witness_depends_on_semantic_key(
    fingerprint: tuple,
    target_key: SemanticKey,
    by_fingerprint: dict[tuple, CapabilityDerivation],
) -> bool:
    witness = by_fingerprint.get(fingerprint)
    if witness is None:
        return False
    if witness.output_semantic_key == target_key:
        return True
    for prereq_fp in witness.prerequisite_witness_fingerprints:
        if witness_depends_on_semantic_key(prereq_fp, target_key, by_fingerprint):
            return True
    return False


def would_create_witness_cycle(
    witness: CapabilityDerivation,
    by_fingerprint: dict[tuple, CapabilityDerivation],
) -> bool:
    output_key = witness.output_semantic_key
    for prereq_fp in witness.prerequisite_witness_fingerprints:
        if witness_depends_on_semantic_key(prereq_fp, output_key, by_fingerprint):
            return True
    return False
