"""Typed governance request and decision models for Community Core.

Semantics mirror the approved WhitePact community governance contract
(deny-by-default authority grants; five-way decisions) without importing
enterprise RBAC, OrgContext, TrustClient, or dashboard types.
"""

from __future__ import annotations

import fnmatch
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from whitepact_community.reason_codes import ReasonCode, format_reason
from whitepact_community.risk import RiskTier

_VALUE_ARGUMENT_KEYS = ("amount_usd", "value_usd", "amount")


class GovernanceDecision(StrEnum):
    ALLOW = "ALLOW"
    ALLOW_WITH_REDACTION = "ALLOW_WITH_REDACTION"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"
    QUARANTINE = "QUARANTINE"


@dataclass(frozen=True)
class IdentityContext:
    identity_id: str
    kind: str = "local"  # local | human | agent | workload
    org_id: str | None = None
    display_name: str | None = None


@dataclass
class AuthorityGrant:
    """Scoped authority for a local agent/operator.

    ``permits()`` is deny-by-default: only explicitly granted action types
    are allowed. Unrecognized constraint keys are ignored (forward-open).
    """

    delegated_by: str
    granted_action_types: frozenset[str]
    constraints: dict[str, Any] = field(default_factory=dict)
    require_approval_for: frozenset[str] = field(default_factory=frozenset)
    expires_at: datetime | None = None
    revocation_epoch: int = 0
    organization_id: str | None = None
    delegation_chain: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.delegation_chain and self.delegation_chain[-1] != self.delegated_by:
            raise ValueError(
                "AuthorityGrant.delegation_chain[-1] must equal delegated_by"
            )

    def permits(self, action_type: str) -> bool:
        return action_type in self.granted_action_types

    def is_expired(self, now: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        clock = now or datetime.now(UTC)
        expires = self.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        return clock >= expires

    def constraint_violation(self, action: ActionRequest) -> str | None:
        denied_targets = self.constraints.get("denied_targets")
        if denied_targets and any(
            fnmatch.fnmatch(action.target, pattern) for pattern in denied_targets
        ):
            return format_reason(
                ReasonCode.TARGET_NOT_ALLOWED, target=action.target, rule="denied_targets"
            )

        allowed_targets = self.constraints.get("allowed_targets")
        if allowed_targets and not any(
            fnmatch.fnmatch(action.target, pattern) for pattern in allowed_targets
        ):
            return format_reason(
                ReasonCode.TARGET_NOT_ALLOWED, target=action.target, rule="allowed_targets"
            )

        max_value_usd = self.constraints.get("max_value_usd")
        if max_value_usd is not None:
            for key in _VALUE_ARGUMENT_KEYS:
                if key in action.arguments:
                    value = action.arguments[key]
                    if isinstance(value, int | float) and value > max_value_usd:
                        return format_reason(
                            ReasonCode.VALUE_LIMIT_EXCEEDED,
                            argument=key,
                            value=value,
                            limit=max_value_usd,
                        )
                    break

        allowed_hours_utc = self.constraints.get("allowed_hours_utc")
        if allowed_hours_utc is not None:
            start, end = allowed_hours_utc
            current_hour = action.proposed_at.astimezone(UTC).hour
            in_window = (
                start <= current_hour < end
                if start <= end
                else current_hour >= start or current_hour < end
            )
            if not in_window:
                return format_reason(
                    ReasonCode.ACTION_NOT_ALLOWED,
                    rule="allowed_hours_utc",
                    hour=current_hour,
                    window=f"{start}-{end}",
                )
        return None


@dataclass
class ActionRequest:
    action_type: str
    target: str
    arguments: dict[str, Any] = field(default_factory=dict)
    identity: IdentityContext = field(
        default_factory=lambda: IdentityContext(identity_id="local-operator")
    )
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DecisionResult:
    decision: GovernanceDecision
    action_id: str
    reason_codes: list[str] = field(default_factory=list)
    risk_tier: RiskTier | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    policy_version: int | None = None
    evidence_id: str | None = None

    @property
    def allowed(self) -> bool:
        return self.decision in {
            GovernanceDecision.ALLOW,
            GovernanceDecision.ALLOW_WITH_REDACTION,
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "action_id": self.action_id,
            "reason_codes": list(self.reason_codes),
            "risk_tier": self.risk_tier.value if self.risk_tier is not None else None,
            "evaluated_at": self.evaluated_at.isoformat(),
            "policy_version": self.policy_version,
            "evidence_id": self.evidence_id,
            "allowed": self.allowed,
        }
