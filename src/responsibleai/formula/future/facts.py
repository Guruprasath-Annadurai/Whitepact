# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.future.models import (
    ConsequenceKind,
    ConsequenceReachability,
    Reversibility,
)

ConsequenceSemanticKey = tuple[str, str, str, str, str]


@dataclass(frozen=True, slots=True)
class ConsequenceFact:
    """Immutable consequence semantic fact — does not imply authority or permission."""

    tenant_id: str
    subject_id: str
    target_id: str
    consequence_kind: ConsequenceKind
    scope: str
    reversibility: Reversibility
    persistence: bool
    information_sensitive: bool
    epistemic_status: EpistemicStatus
    reachability: ConsequenceReachability
    magnitude_class: str | None = None

    def semantic_key(self) -> ConsequenceSemanticKey:
        return (
            self.tenant_id,
            self.subject_id,
            self.target_id,
            self.consequence_kind.value,
            self.scope,
        )

    def __post_init__(self) -> None:
        if not self.tenant_id.strip():
            raise ValueError("tenant_id required")
        if not self.subject_id.strip():
            raise ValueError("subject_id required")
        if not self.target_id.strip():
            raise ValueError("target_id required")
