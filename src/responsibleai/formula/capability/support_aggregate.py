# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.models import CapabilityKind

# Commutative aggregate: lowest index wins (most direct / primitive support class).
_KIND_AGGREGATE_ORDER: tuple[CapabilityKind, ...] = (
    CapabilityKind.DIRECT_TOOL,
    CapabilityKind.RESOURCE,
    CapabilityKind.CREDENTIAL_DERIVED,
    CapabilityKind.INFORMATION_DERIVED,
    CapabilityKind.COMPOSED,
)


def aggregate_support_kind(witnesses: tuple[CapabilityDerivation, ...]) -> CapabilityKind:
    kinds = {w.support_kind for w in witnesses}
    for kind in _KIND_AGGREGATE_ORDER:
        if kind in kinds:
            return kind
    return CapabilityKind.COMPOSED


def aggregate_is_direct(witnesses: tuple[CapabilityDerivation, ...]) -> bool:
    return any(w.support_is_direct for w in witnesses)


def aggregate_epistemic(witnesses: tuple[CapabilityDerivation, ...]):
    if not witnesses:
        return compose_epistemic()
    return compose_epistemic(*(w.epistemic_status for w in witnesses))


def aggregate_fact_from_witnesses(
    base: CapabilityFact, witnesses: tuple[CapabilityDerivation, ...]
) -> CapabilityFact:
    """Recompute semantic fact fields from all supports (order-independent)."""
    return CapabilityFact(
        tenant_id=base.tenant_id,
        actor=base.actor,
        action=base.action,
        target_node_id=base.target_node_id,
        kind=aggregate_support_kind(witnesses),
        epistemic_status=aggregate_epistemic(witnesses),
        is_direct=aggregate_is_direct(witnesses),
    )
