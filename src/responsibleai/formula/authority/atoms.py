# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PermissionAtom:
    """Semantic authority atom (no grant provenance)."""

    action: str
    resource: str
    purpose: str
    risk_ceiling: int


@dataclass(frozen=True, slots=True)
class AuthorityTuple:
    """Authority tuple with provenance."""

    action: str
    resource: str
    purpose: str
    risk_ceiling: int
    grant_id: str

    def atom(self) -> PermissionAtom:
        return PermissionAtom(self.action, self.resource, self.purpose, self.risk_ceiling)
