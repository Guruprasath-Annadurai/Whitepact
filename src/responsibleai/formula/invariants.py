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
from responsibleai.formula.capability.budget import ClosureStatus
from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.epistemic import EpistemicStatus, is_authoritative_for_hard_proof
from responsibleai.formula.fence import CommitFence, EvaluationPin
from responsibleai.formula.trace.semantics import TraceAuthorized
from responsibleai.formula.trace.trace import FormulaTrace


class InvariantId(StrEnum):
    INV_CAPABILITY_NOT_AUTHORITY = "INV_CAPABILITY_NOT_AUTHORITY"
    INV_CAPABILITY_TENANT_ISOLATION = "INV_CAPABILITY_TENANT_ISOLATION"
    INV_CAPABILITY_PROVENANCE = "INV_CAPABILITY_PROVENANCE"
    INV_CAPABILITY_NO_SPONTANEOUS_EXPANSION = "INV_CAPABILITY_NO_SPONTANEOUS_EXPANSION"
    INV_CAPABILITY_EPISTEMIC_NON_UPGRADE = "INV_CAPABILITY_EPISTEMIC_NON_UPGRADE"
    INV_CAPABILITY_CLOSURE_IDEMPOTENT = "INV_CAPABILITY_CLOSURE_IDEMPOTENT"
    INV_CAPABILITY_BUDGET_FAILS_INCOMPLETE = "INV_CAPABILITY_BUDGET_FAILS_INCOMPLETE"
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

    def check_capability_tenant_isolation(
        self, result: CapabilityClosureResult
    ) -> list[InvariantViolation]:
        for fact in result.facts:
            if fact.tenant_id != result.tenant_id:
                return [
                    InvariantViolation(
                        InvariantId.INV_CAPABILITY_TENANT_ISOLATION,
                        "capability fact tenant mismatch",
                    )
                ]
            if fact.actor.tenant_id != result.tenant_id:
                return [
                    InvariantViolation(
                        InvariantId.INV_CAPABILITY_TENANT_ISOLATION,
                        "capability actor tenant mismatch",
                    )
                ]
        return []

    def check_capability_provenance(
        self, result: CapabilityClosureResult
    ) -> list[InvariantViolation]:
        direct_keys = {f.semantic_key() for f in result.facts if f.is_direct}
        derived_keys = {d.output_semantic_key for d in result.derivations}
        for fact in result.facts:
            if fact.is_direct:
                continue
            if fact.semantic_key() not in derived_keys:
                return [
                    InvariantViolation(
                        InvariantId.INV_CAPABILITY_PROVENANCE,
                        "non-direct capability missing derivation witness",
                    )
                ]
        for d in result.derivations:
            for prereq in d.prerequisite_keys:
                if prereq not in direct_keys and prereq not in derived_keys:
                    # prerequisite may be another derived fact from earlier iteration
                    if not any(f.semantic_key() == prereq for f in result.facts):
                        return [
                            InvariantViolation(
                                InvariantId.INV_CAPABILITY_PROVENANCE,
                                "derivation references missing prerequisite",
                            )
                        ]
        return []

    def check_capability_budget_status(
        self, result: CapabilityClosureResult
    ) -> list[InvariantViolation]:
        exhausted = (
            result.iterations >= result.budget.max_iterations
            or len(result.facts) >= result.budget.max_facts
            or result.rule_applications >= result.budget.max_rule_applications
        )
        if exhausted and result.status == ClosureStatus.COMPLETE:
            return [
                InvariantViolation(
                    InvariantId.INV_CAPABILITY_BUDGET_FAILS_INCOMPLETE,
                    "budget exhausted but closure reported COMPLETE",
                )
            ]
        return []

    def check_derivation_epistemic_non_upgrade(
        self, derivation: CapabilityDerivation, premises: tuple
    ) -> list[InvariantViolation]:

        statuses = [p.epistemic_status for p in premises if hasattr(p, "epistemic_status")]
        if not statuses:
            return []
        weakest = compose_epistemic(*statuses)
        if _epistemic_rank(derivation.epistemic_status) > _epistemic_rank(weakest):
            return [
                InvariantViolation(
                    InvariantId.INV_CAPABILITY_EPISTEMIC_NON_UPGRADE,
                    "derivation epistemic status exceeds weakest premise",
                )
            ]
        return []


def _epistemic_rank(status) -> int:
    from responsibleai.formula.epistemic import EpistemicStatus

    order = list(EpistemicStatus)
    return order.index(status)
