# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.authority.models import OrgAuthorityCeilingModel


@dataclass(frozen=True, slots=True)
class TenantRootPrincipal:
    """Explicit tenant-bound root authority — not inferred from string prefixes."""

    tenant_id: str
    principal_id: str
    org_id: str
    evidence_ref: str
    policy_version: str
    ceiling: OrgAuthorityCeilingModel | None = None

    def is_issuer(self, issuer_id: str, tenant_id: str) -> bool:
        return issuer_id == self.principal_id and tenant_id == self.tenant_id
