# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""In-process shadow observation store — distinct from execution evidence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field

from responsibleai.sovereign.shadow import ShadowObservation


class PersistedShadowRecord(BaseModel):
    """Analytical shadow row — never satisfies approval or execution."""

    shadow_id: str
    organization_id: str
    simulated: bool = True
    non_authoritative: bool = True
    observation: ShadowObservation
    created_at: str
    labels: list[str] = Field(default_factory=lambda: ["SHADOW", "SIMULATED"])


class ShadowObservationStore:
    """Tenant-scoped shadow observations (process-local; not execution truth)."""

    def __init__(self) -> None:
        self._rows: dict[str, PersistedShadowRecord] = {}

    def save(self, observation: ShadowObservation) -> PersistedShadowRecord:
        shadow_id = f"shadow-{uuid.uuid4().hex}"
        record = PersistedShadowRecord(
            shadow_id=shadow_id,
            organization_id=observation.organization_id,
            observation=observation,
            created_at=datetime.now(UTC).isoformat(),
        )
        self._rows[shadow_id] = record
        return record

    def get(self, organization_id: str, shadow_id: str) -> PersistedShadowRecord | None:
        row = self._rows.get(shadow_id)
        if row is None or row.organization_id != organization_id:
            return None
        return row

    def list_for_org(self, organization_id: str) -> list[PersistedShadowRecord]:
        return [r for r in self._rows.values() if r.organization_id == organization_id]


_GLOBAL_SHADOW_STORE = ShadowObservationStore()


def global_shadow_store() -> ShadowObservationStore:
    return _GLOBAL_SHADOW_STORE
