# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Flight recorder — canonical lifecycle timeline reconstruction."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.trace_builder import AuthorityTrace, build_trace_from_evidence
from responsibleai.sovereign.zero_effect import zero_effect_operation


class FactProvenance(StrEnum):
    DATABASE_FACT = "DATABASE_FACT"
    DERIVED_FROM_FACTS = "DERIVED_FROM_FACTS"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class FlightEvent(BaseModel):
    stage: str
    provenance: FactProvenance
    status: str
    identifier: str | None = None
    summary: str
    refs: list[str] = Field(default_factory=list)


class FlightRecording(BaseModel):
    organization_id: str
    recording_id: str
    events: list[FlightEvent] = Field(default_factory=list)
    trace: AuthorityTrace | None = None


@zero_effect_operation
async def build_flight_recording(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    evidence_id: str,
) -> FlightRecording:
    trace = await build_trace_from_evidence(store, ctx, evidence_id)
    events: list[FlightEvent] = []
    for stage in trace.stages:
        prov = FactProvenance.DATABASE_FACT
        if stage.status == "MISSING":
            prov = FactProvenance.MISSING
        elif stage.status == "UNKNOWN":
            prov = FactProvenance.UNKNOWN
        elif stage.provenance.startswith("DERIVED"):
            prov = FactProvenance.DERIVED_FROM_FACTS
        events.append(
            FlightEvent(
                stage=stage.stage.value,
                provenance=prov,
                status=stage.status,
                identifier=stage.identifier,
                summary=stage.summary,
                refs=stage.refs,
            )
        )
    return FlightRecording(
        organization_id=ctx.organization_id,
        recording_id=f"flight-{evidence_id}",
        events=events,
        trace=trace,
    )
