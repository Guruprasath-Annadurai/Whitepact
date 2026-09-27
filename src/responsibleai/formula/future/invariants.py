# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.future.envelope import SafeFutureEnvelope
from responsibleai.formula.future.models import EnvelopeStatus


def validate_gate4_invariants(envelope: SafeFutureEnvelope) -> list[str]:
    """Return violation messages; empty list means all checked invariants hold."""
    violations: list[str] = []
    for fact in envelope.consequence_facts:
        if fact.tenant_id != envelope.tenant_id:
            violations.append("INV-G4-03 tenant isolation on consequence fact")
    if envelope.status == EnvelopeStatus.INCOMPLETE and not envelope.blocked_frontier:
        violations.append("INV-G4-10 incomplete without blocked frontier evidence")
    if not envelope.canonical_hash:
        violations.append("INV-G4-15 missing canonical hash")
    deriv_keys = {d.output_key for d in envelope.causal_derivations}
    for d in envelope.causal_derivations:
        for prereq in d.prerequisite_keys:
            if prereq not in deriv_keys and prereq not in {
                f.semantic_key() for f in envelope.consequence_facts
            }:
                violations.append("INV-G4-02 missing prerequisite provenance")
    return violations
