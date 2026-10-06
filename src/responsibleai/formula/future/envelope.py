# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.future.blast import BlastRadius
from responsibleai.formula.future.budget import FutureEnvelopeBudget
from responsibleai.formula.future.facts import ConsequenceFact
from responsibleai.formula.future.models import EnvelopeStatus
from responsibleai.formula.future.provenance import CausalDerivation
from responsibleai.formula.version import FORMULA_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class ReachableWorldState:
    """Reduced world marker: active consequence semantic keys at a step."""

    step: int
    active_keys: frozenset[tuple[str, str, str, str, str]]


@dataclass(frozen=True, slots=True)
class SafeFutureEnvelope:
    """Bounded future consequence envelope — not a safety certification or authorization."""

    tenant_id: str
    snapshot_id: str
    graph_content_hash: str
    capability_closure_fingerprint: str
    capability_closure_status: str
    capability_unresolved_notes: tuple[str, ...]
    causal_rules_fingerprint: str
    horizon: int
    status: EnvelopeStatus
    consequence_facts: tuple[ConsequenceFact, ...]
    causal_derivations: tuple[CausalDerivation, ...]
    reachable_states: tuple[ReachableWorldState, ...]
    blast_radius: BlastRadius
    blocked_frontier: tuple[str, ...]
    budget: FutureEnvelopeBudget
    budget_usage: dict[str, int]
    epistemic_summary: EpistemicStatus
    canonical_hash: str
    schema_version: str = FORMULA_SCHEMA_VERSION
