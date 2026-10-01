# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.budget import ClosureStatus
from responsibleai.formula.future.envelope import SafeFutureEnvelope
from responsibleai.formula.future.models import EnvelopeStatus


def validate_gate4_invariants(envelope: SafeFutureEnvelope) -> list[str]:
    """Return violation messages; empty list means all checked invariants hold."""
    violations: list[str] = []
    fact_keys = {f.semantic_key() for f in envelope.consequence_facts}
    deriv_keys = {d.output_key for d in envelope.causal_derivations}
    witness_fps = [w.witness_fingerprint() for w in envelope.causal_derivations]
    if len(witness_fps) != len(set(witness_fps)):
        violations.append("INV-G4-04 duplicate witness fingerprints in envelope")
    for fact in envelope.consequence_facts:
        if fact.tenant_id != envelope.tenant_id:
            violations.append("INV-G4-03 tenant isolation on consequence fact")
    if envelope.status == EnvelopeStatus.INCOMPLETE and not envelope.blocked_frontier:
        violations.append("INV-G4-10 incomplete without blocked frontier evidence")
    if envelope.capability_closure_status == ClosureStatus.INCOMPLETE.value:
        if envelope.status == EnvelopeStatus.COMPLETE:
            violations.append("INV-G4-upstream incomplete closure cannot yield COMPLETE envelope")
        if "capability_closure_incomplete" not in envelope.blocked_frontier:
            violations.append("INV-G4-upstream missing capability_closure_incomplete marker")
    if not envelope.canonical_hash:
        violations.append("INV-G4-15 missing canonical hash")
    for d in envelope.causal_derivations:
        if d.output_key not in fact_keys:
            violations.append("INV-G4-02 derivation output without consequence fact")
        for prereq in d.prerequisite_keys:
            if prereq not in deriv_keys and prereq not in fact_keys:
                violations.append("INV-G4-02 missing prerequisite provenance")
    return violations
