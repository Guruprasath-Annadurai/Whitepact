# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    authority_subset,
    grant_restriction,
    grant_union,
    validate_delegation,
)
from responsibleai.formula.authority.delegation import DelegationChain
from responsibleai.formula.authority.lifecycle import lifecycle_at
from responsibleai.formula.authority.models import (
    AuthorityGrant,
    AuthorityLifecycle,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.epistemic import EpistemicStatus, is_authoritative_for_hard_proof
from responsibleai.formula.fence import CommitFence, EvaluationPin
from responsibleai.formula.trace.semantics import TraceAuthorized
from responsibleai.formula.trace.trace import FormulaTrace


class InvariantId(StrEnum):
    INV_CAPABILITY_NOT_AUTHORITY = "INV_CAPABILITY_NOT_AUTHORITY"
    INV_UNKNOWN_NOT_AUTHORITY = "INV_UNKNOWN_NOT_AUTHORITY"
    INV_DELEGATION_SUBSET = "INV_DELEGATION_SUBSET"
    INV_ORG_CEILING = "INV_ORG_CEILING"
    INV_EXPIRED_INVALID = "INV_EXPIRED_INVALID"
    INV_REVOKED_INVALID = "INV_REVOKED_INVALID"
    INV_CONSUMED_INVALID = "INV_CONSUMED_INVALID"
    INV_TENANT_ISOLATION = "INV_TENANT_ISOLATION"
    INV_TRACE_AUTHORITY = "INV_TRACE_AUTHORITY"
    INV_VERSION_PINNING = "INV_VERSION_PINNING"


@dataclass(frozen=True, slots=True)
class InvariantViolation:
    invariant: InvariantId
    detail: str


@dataclass
class FormulaInvariantChecker:
    def check_capability_not_authority(
        self, has_capability: bool, authorized: bool, grant_backed: bool
    ) -> list[InvariantViolation]:
        if authorized and has_capability and not grant_backed:
            return [
                InvariantViolation(
                    InvariantId.INV_CAPABILITY_NOT_AUTHORITY,
                    "authorization must not be inferred from capability alone",
                )
            ]
        return []

    def check_unknown_not_authority(
        self, grant: AuthorityGrant, authorize_execute: bool
    ) -> list[InvariantViolation]:
        if authorize_execute and not is_authoritative_for_hard_proof(grant.epistemic_status):
            if grant.epistemic_status == EpistemicStatus.UNKNOWN:
                return [
                    InvariantViolation(
                        InvariantId.INV_UNKNOWN_NOT_AUTHORITY,
                        "UNKNOWN epistemic status cannot authorize execute",
                    )
                ]
        return []

    def check_org_ceiling(
        self,
        grants: tuple[AuthorityGrant, ...],
        ceiling: OrgAuthorityCeilingModel,
        at: datetime,
        subject_id: str,
        tenant_id: str,
    ) -> list[InvariantViolation]:
        ev = EffectiveAuthorityEvaluator(ceiling=ceiling)
        effective = ev.effective(grants, (), subject_id, tenant_id, at)
        raw = grant_union([g for g in grants if g.valid_at(at)])
        restricted = grant_restriction(raw, ceiling)
        if not effective.issubset(restricted):
            return [
                InvariantViolation(
                    InvariantId.INV_ORG_CEILING,
                    "effective authority exceeds org ceiling envelope",
                )
            ]
        return []

    def check_delegation_chain(self, chain: DelegationChain) -> list[InvariantViolation]:
        try:
            chain.validate()
        except Exception as exc:  # noqa: BLE001
            return [InvariantViolation(InvariantId.INV_DELEGATION_SUBSET, str(exc))]
        return []

    def check_grant_temporal(self, grant: AuthorityGrant, at: datetime) -> list[InvariantViolation]:
        state = lifecycle_at(grant, at)
        violations: list[InvariantViolation] = []
        if state == AuthorityLifecycle.EXPIRED:
            violations.append(InvariantViolation(InvariantId.INV_EXPIRED_INVALID, grant.grant_id))
        if state == AuthorityLifecycle.REVOKED:
            violations.append(InvariantViolation(InvariantId.INV_REVOKED_INVALID, grant.grant_id))
        if state == AuthorityLifecycle.CONSUMED:
            violations.append(InvariantViolation(InvariantId.INV_CONSUMED_INVALID, grant.grant_id))
        return violations

    def check_tenant(self, tenant_a: str, tenant_b: str) -> list[InvariantViolation]:
        if tenant_a != tenant_b:
            return [
                InvariantViolation(
                    InvariantId.INV_TENANT_ISOLATION,
                    f"tenant mismatch {tenant_a} vs {tenant_b}",
                )
            ]
        return []

    def check_trace_authority(
        self, trace: FormulaTrace, authorized_ids: frozenset[str]
    ) -> list[InvariantViolation]:
        if not TraceAuthorized(trace, authorized_ids):
            return [InvariantViolation(InvariantId.INV_TRACE_AUTHORITY, "unauthorized trace event")]
        return []

    def check_version_pin(
        self,
        pin: EvaluationPin,
        fence: CommitFence,
        authority_version: int,
        graph_version: int,
    ) -> list[InvariantViolation]:
        try:
            fence.validate(pin, authority_version, graph_version)
        except Exception as exc:  # noqa: BLE001
            return [InvariantViolation(InvariantId.INV_VERSION_PINNING, str(exc))]
        return []

    def check_parent_child_subset(
        self, parent: AuthorityGrant, child: AuthorityGrant
    ) -> list[InvariantViolation]:
        if not authority_subset(child, parent):
            return [
                InvariantViolation(InvariantId.INV_DELEGATION_SUBSET, "child not subset of parent")
            ]
        try:
            validate_delegation(parent, child)
        except Exception as exc:  # noqa: BLE001
            return [InvariantViolation(InvariantId.INV_DELEGATION_SUBSET, str(exc))]
        return []
