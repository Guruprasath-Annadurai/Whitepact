# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.errors import CapabilityTenantMismatch


@dataclass(frozen=True, slots=True)
class CapabilityActor:
    """Canonical actor or coalition (sorted member IDs, single tenant)."""

    tenant_id: str
    member_ids: tuple[str, ...]

    @classmethod
    def single(cls, tenant_id: str, actor_id: str) -> CapabilityActor:
        return cls(tenant_id, (actor_id,))

    @classmethod
    def coalition(cls, tenant_id: str, member_ids: tuple[str, ...] | list[str]) -> CapabilityActor:
        members = tuple(sorted(set(member_ids)))
        if not members:
            raise ValueError("coalition requires at least one member")
        return cls(tenant_id, members)

    def assert_tenant(self, tenant_id: str) -> None:
        if self.tenant_id != tenant_id:
            raise CapabilityTenantMismatch(f"actor tenant {self.tenant_id} != expected {tenant_id}")
