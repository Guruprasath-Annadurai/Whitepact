# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign Gauntlet — developer adversarial governance surface."""

from __future__ import annotations

import time
import uuid
from enum import StrEnum

from pydantic import BaseModel, Field

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.tenant import assert_same_organization
from responsibleai.sovereign.zero_effect import zero_effect_operation


class GauntletVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"


class GauntletCaseResult(BaseModel):
    test_id: str
    attack: str
    expected_control: str
    observation: str
    verdict: GauntletVerdict
    evidence_refs: list[str] = Field(default_factory=list)
    duration_ms: float
    related_ids: dict[str, str] = Field(default_factory=dict)


class GauntletReport(BaseModel):
    run_id: str
    organization_id: str
    cases: list[GauntletCaseResult] = Field(default_factory=list)


@zero_effect_operation
async def run_sovereign_gauntlet(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    probe_org_id: str | None = None,
) -> GauntletReport:
    """Run in-process adversarial checks — PASS only from observed controls."""
    run_id = f"gauntlet-{uuid.uuid4().hex}"
    cases: list[GauntletCaseResult] = []

    async def _case(
        test_id: str,
        attack: str,
        expected_control: str,
        fn,
    ) -> None:
        start = time.perf_counter()
        try:
            observation, verdict, refs, ids = await fn()
        except Exception as exc:  # noqa: BLE001 — gauntlet records observation
            observation = f"unexpected_error: {exc}"
            verdict = GauntletVerdict.FAIL
            refs = []
            ids = {}
        duration = (time.perf_counter() - start) * 1000
        cases.append(
            GauntletCaseResult(
                test_id=test_id,
                attack=attack,
                expected_control=expected_control,
                observation=observation,
                verdict=verdict,
                evidence_refs=refs,
                duration_ms=duration,
                related_ids=ids,
            )
        )

    async def cross_tenant() -> tuple[str, GauntletVerdict, list[str], dict[str, str]]:
        foreign = probe_org_id or "foreign-org"
        try:
            assert_same_organization(ctx.organization_id, foreign, resource_kind="gauntlet-probe")
            return ("cross-tenant allowed", GauntletVerdict.FAIL, [], {})
        except SovereignTenantIsolationError:
            return ("cross-tenant rejected", GauntletVerdict.PASS, [], {"foreign_org": foreign})

    await _case(
        "cross_tenant_access",
        "cross-tenant access",
        "tenant isolation guard rejects foreign org",
        cross_tenant,
    )

    async def unknown_evidence() -> tuple[str, GauntletVerdict, list[str], dict[str, str]]:
        missing = await store.evidence.get_for_org("missing-evidence", ctx.organization_id)
        if missing is None:
            return ("missing evidence not leaked", GauntletVerdict.PASS, [], {})
        return ("missing evidence returned row", GauntletVerdict.FAIL, [missing.id], {})

    await _case(
        "unknown_evidence",
        "unknown evidence id",
        "repository returns None for missing evidence",
        unknown_evidence,
    )

    return GauntletReport(run_id=run_id, organization_id=ctx.organization_id, cases=cases)
