# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.capability.actors import CapabilityActor
from responsibleai.formula.capability.models import CapabilityKind
from responsibleai.formula.epistemic import EpistemicStatus


@dataclass(frozen=True, slots=True)
class CapabilityFact:
    """Semantic capability fact (reachability only — not authority)."""

    tenant_id: str
    actor: CapabilityActor
    action: str
    target_node_id: str
    kind: CapabilityKind
    epistemic_status: EpistemicStatus
    is_direct: bool

    def semantic_key(self) -> tuple[str, str, tuple[str, ...], str, str]:
        return (
            self.tenant_id,
            self.actor.tenant_id,
            self.actor.member_ids,
            self.action,
            self.target_node_id,
        )

    def __post_init__(self) -> None:
        if self.actor.tenant_id != self.tenant_id:
            raise ValueError("capability fact actor tenant mismatch")
