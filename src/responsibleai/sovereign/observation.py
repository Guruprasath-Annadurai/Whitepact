# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Safe read-only authority observation (non-authoritative, zero side effects)."""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, Field

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.effective import EffectiveAuthoritySnapshot, load_effective_authority
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation


class SovereignObservation(BaseModel):
    organization_id: str
    fingerprint: str
    effective: EffectiveAuthoritySnapshot
    changed_from_previous: bool | None = None
    notes: list[str] = Field(default_factory=list)


def _fingerprint(snapshot: EffectiveAuthoritySnapshot) -> str:
    material = json.dumps(
        {
            "capabilities": snapshot.capability_ids,
            "policy_version": snapshot.policy_version,
            "epoch": snapshot.governance_epoch,
        },
        sort_keys=True,
    )
    return hashlib.sha256(material.encode()).hexdigest()


@zero_effect_operation
async def observe_authority(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    *,
    previous_fingerprint: str | None = None,
) -> SovereignObservation:
    effective = await load_effective_authority(
        store, ctx.organization_id, environment=ctx.environment
    )
    fp = _fingerprint(effective)
    changed = None
    if previous_fingerprint is not None:
        changed = fp != previous_fingerprint
    return SovereignObservation(
        organization_id=ctx.organization_id,
        fingerprint=fp,
        effective=effective,
        changed_from_previous=changed,
        notes=["Observation is non-authoritative and does not modify governance state"],
    )
