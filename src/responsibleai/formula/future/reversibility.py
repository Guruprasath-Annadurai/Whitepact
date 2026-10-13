# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.future.models import Reversibility


def compose_reversibility(
    left: Reversibility,
    right: Reversibility,
    *,
    recovery_rule: bool = False,
) -> Reversibility:
    """Conservative reversibility lattice — UNKNOWN never becomes REVERSIBLE."""
    if recovery_rule and left == Reversibility.IRREVERSIBLE and right == Reversibility.REVERSIBLE:
        return Reversibility.CONDITIONALLY_REVERSIBLE
    if left == Reversibility.IRREVERSIBLE or right == Reversibility.IRREVERSIBLE:
        return Reversibility.IRREVERSIBLE
    if left == Reversibility.UNKNOWN or right == Reversibility.UNKNOWN:
        return Reversibility.UNKNOWN
    if (
        left == Reversibility.CONDITIONALLY_REVERSIBLE
        or right == Reversibility.CONDITIONALLY_REVERSIBLE
    ):
        return Reversibility.CONDITIONALLY_REVERSIBLE
    return Reversibility.REVERSIBLE
