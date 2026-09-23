# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Time machine — THEN vs NOW without retrospective policy fiction."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from responsibleai.sovereign.authority_engine import compare_effective_snapshots
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.effective import EffectiveAuthoritySnapshot, load_effective_authority
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation


class HistoricalFactKind(StrEnum):
    KNOWN_HISTORICAL_FACT = "KNOWN_HISTORICAL_FACT"
    DERIVED_RECONSTRUCTION = "DERIVED_RECONSTRUCTION"
    MISSING_HISTORICAL_DATA = "MISSING_HISTORICAL_DATA"


class TimeMachineComparison(BaseModel):
    organization_id: str
    then_snapshot: EffectiveAuthoritySnapshot | None = None
    now_snapshot: EffectiveAuthoritySnapshot | None = None
    then_kind: HistoricalFactKind
    now_kind: HistoricalFactKind = HistoricalFactKind.KNOWN_HISTORICAL_FACT
    capability_delta: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@zero_effect_operation
async def compare_then_now(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    then_snapshot: EffectiveAuthoritySnapshot | None,
) -> TimeMachineComparison:
    now = await load_effective_authority(store, ctx.organization_id, environment=ctx.environment)
    then_kind = (
        HistoricalFactKind.KNOWN_HISTORICAL_FACT
        if then_snapshot is not None
        else HistoricalFactKind.MISSING_HISTORICAL_DATA
    )
    notes = [
        "Current policy is not applied retrospectively to historical snapshots",
        "Historical replay remains zero-effect",
    ]
    delta: list[str] = []
    if then_snapshot is not None:
        diff = await compare_effective_snapshots(ctx, then_snapshot, now)
        delta = [f"{d.category.value}:{d.capability_id}" for d in diff.diffs]
    return TimeMachineComparison(
        organization_id=ctx.organization_id,
        then_snapshot=then_snapshot,
        now_snapshot=now,
        then_kind=then_kind,
        capability_delta=delta,
        notes=notes,
    )
