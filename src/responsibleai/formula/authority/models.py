# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from responsibleai.formula.epistemic import EpistemicStatus


class AuthorityLifecycle(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    CONSUMED = "CONSUMED"
    SUPERSEDED = "SUPERSEDED"


@dataclass(frozen=True, slots=True)
class AuthoritySubject:
    subject_id: str
    tenant_id: str
    kind: str = "AGENT"


@dataclass(frozen=True, slots=True)
class AuthorityAction:
    action_type: str
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthorityResource:
    resource_id: str
    resource_type: str = "*"


@dataclass(frozen=True, slots=True)
class AuthorityPurpose:
    purpose: str


@dataclass(frozen=True, slots=True)
class AuthorityContext:
    """Context constraints that must match for grant applicability."""

    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthorityScope:
    actions: frozenset[str]
    resources: frozenset[str]
    purposes: frozenset[str]
    context_keys: frozenset[str] = frozenset()


@dataclass(frozen=True, slots=True)
class AuthorityConstraint:
    max_risk_class: int = 10
    allow_delegation: bool = False
    one_shot: bool = False
    conditions: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuthorityGrant:
    grant_id: str
    tenant_id: str
    subject: AuthoritySubject
    issuer_id: str
    delegator_id: str | None
    actions: frozenset[str]
    resources: frozenset[str]
    purposes: frozenset[str]
    context: AuthorityContext
    not_before: datetime
    expires_at: datetime
    risk_ceiling: int
    constraints: AuthorityConstraint
    lifecycle: AuthorityLifecycle = AuthorityLifecycle.PENDING
    evidence_ref: str = ""
    epistemic_status: EpistemicStatus = EpistemicStatus.DECLARED
    schema_version: str = "0.1.0"
    version: int = 1

    def valid_at(self, at: datetime) -> bool:
        if self.lifecycle not in (AuthorityLifecycle.ACTIVE, AuthorityLifecycle.PENDING):
            return False
        if self.lifecycle == AuthorityLifecycle.PENDING and at < self.not_before:
            return False
        return self.not_before <= at < self.expires_at


@dataclass(frozen=True, slots=True)
class ExplicitDeny:
    deny_id: str
    tenant_id: str
    subject_id: str
    actions: frozenset[str]
    resources: frozenset[str]
    expires_at: datetime | None = None
    specificity: int = 1


@dataclass(frozen=True, slots=True)
class OrgAuthorityCeilingModel:
    """Formula-side org ceiling (domain model, not governance.ceiling integration)."""

    tenant_id: str
    org_id: str
    allowed_actions: frozenset[str] | None = None
    allowed_resources: frozenset[str] | None = None
    max_risk_class: int | None = None
    max_delegation_depth: int | None = None
