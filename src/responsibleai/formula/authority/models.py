# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.immutability import freeze_mapping


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
    """Immutable context constraints (equality keys required at evaluation)."""

    _pairs: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def from_mapping(cls, mapping: Mapping[str, Any] | None = None) -> AuthorityContext:
        if not mapping:
            return cls(())
        return cls(freeze_mapping(mapping))

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(self._pairs)


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
    _condition_pairs: tuple[tuple[str, Any], ...] = ()

    @classmethod
    def build(
        cls,
        *,
        max_risk_class: int = 10,
        allow_delegation: bool = False,
        one_shot: bool = False,
        conditions: Mapping[str, Any] | None = None,
    ) -> AuthorityConstraint:
        return cls(
            max_risk_class=max_risk_class,
            allow_delegation=allow_delegation,
            one_shot=one_shot,
            _condition_pairs=freeze_mapping(conditions or {}),
        )

    @property
    def conditions(self) -> dict[str, Any]:
        return dict(self._condition_pairs)


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
    not_before: datetime
    expires_at: datetime
    risk_ceiling: int
    constraints: AuthorityConstraint
    context: AuthorityContext = field(default_factory=AuthorityContext.from_mapping)
    lifecycle: AuthorityLifecycle = AuthorityLifecycle.PENDING
    evidence_ref: str = ""
    epistemic_status: EpistemicStatus = EpistemicStatus.DECLARED
    schema_version: str = "0.1.0"
    version: int = 1
    delegation_depth: int = 0

    def valid_at(self, at: datetime) -> bool:
        from responsibleai.formula.authority.lifecycle import lifecycle_at

        return lifecycle_at(self, at) == AuthorityLifecycle.ACTIVE


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
    # Depth is enforced in grant_within_org_ceiling (mint) and validate_delegation (chain).
    max_delegation_depth: int | None = None
