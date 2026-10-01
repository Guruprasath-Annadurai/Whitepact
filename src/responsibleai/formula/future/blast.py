# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BlastRadius:
    """Bounded blast-radius dimensions — absent fields mean unknown/unmodeled."""

    tenant_id: str
    affected_actors: frozenset[str]
    affected_resources: frozenset[str]
    affected_systems: frozenset[str]
    affected_data_objects: frozenset[str]
    external_targets: frozenset[str]
    propagation_depth: int
    persistence_scope: str | None = None
    financial_exposure_class: str | None = None

    def merge(self, other: BlastRadius) -> BlastRadius:
        if self.tenant_id != other.tenant_id:
            raise ValueError("cross-tenant blast radius merge")
        return BlastRadius(
            tenant_id=self.tenant_id,
            affected_actors=self.affected_actors | other.affected_actors,
            affected_resources=self.affected_resources | other.affected_resources,
            affected_systems=self.affected_systems | other.affected_systems,
            affected_data_objects=self.affected_data_objects | other.affected_data_objects,
            external_targets=self.external_targets | other.external_targets,
            propagation_depth=max(self.propagation_depth, other.propagation_depth),
            persistence_scope=self.persistence_scope or other.persistence_scope,
            financial_exposure_class=self.financial_exposure_class
            or other.financial_exposure_class,
        )
