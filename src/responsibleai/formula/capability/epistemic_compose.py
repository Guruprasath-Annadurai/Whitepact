# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.epistemic import EpistemicStatus

_ORDER: tuple[EpistemicStatus, ...] = (
    EpistemicStatus.UNKNOWN,
    EpistemicStatus.ASSUMED,
    EpistemicStatus.INFERRED,
    EpistemicStatus.DECLARED,
    EpistemicStatus.OBSERVED,
    EpistemicStatus.VERIFIED,
)


def compose_epistemic(*statuses: EpistemicStatus) -> EpistemicStatus:
    """Weakest-link composition: derived strength cannot exceed weakest premise."""
    if not statuses:
        return EpistemicStatus.UNKNOWN
    return min(statuses, key=lambda s: _ORDER.index(s))
