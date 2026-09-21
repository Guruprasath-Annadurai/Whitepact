# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign Gauntlet — pytest-orchestrated adversarial governance surface."""

from __future__ import annotations

import uuid

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.gauntlet_orchestrator import (
    GauntletCaseResult,
    GauntletCaseStatus,
    GauntletReport,
    run_registered_gauntlet,
)
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation

__all__ = [
    "GauntletCaseResult",
    "GauntletCaseStatus",
    "GauntletReport",
    "run_sovereign_gauntlet",
]


@zero_effect_operation
async def run_sovereign_gauntlet(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    probe_ids: list[str] | None = None,
    skip_subprocess: bool = False,
) -> GauntletReport:
    """Run registered pytest probes; PASS only when pytest observes passing control tests."""
    _ = store  # reserved for future org-scoped probes
    if skip_subprocess:
        return GauntletReport(
            run_id=f"gauntlet-{uuid.uuid4().hex}",
            organization_id=ctx.organization_id,
            cases=[
                GauntletCaseResult(
                    test_id="subprocess_disabled",
                    attack_family="n/a",
                    expected_control="orchestrator available",
                    observed_behavior="subprocess gauntlet skipped by caller",
                    status=GauntletCaseStatus.UNAVAILABLE,
                    duration_ms=0.0,
                )
            ],
        )
    return run_registered_gauntlet(ctx.organization_id, probe_ids=probe_ids)
