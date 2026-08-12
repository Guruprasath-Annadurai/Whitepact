"""Core entities for the WhitePact runtime governance pipeline —
SPEC.md Section 3. Each dataclass below is the concrete, executable
form of a **[TARGET]** entity SPEC.md defines; see that document for
the full rationale and the [TODAY] precedent each one builds on.

Risk-tiered routing (Phase 9, ``governance/risk.py``) and a first policy
engine (Phase 10, ``governance/policy.py``) now exist and are wired into
``WhitePactRuntimeGateway`` — see those modules' docstrings.
``EvidenceRecord`` is persisted and hash-chained
(``db/evidence_repository.py``, Phase 12) — ``DecisionResult`` below
remains the in-memory decision output ``build_evidence_record()``
converts into that immutable form; it doesn't persist anything itself.
``GovernanceDecision.QUARANTINE`` is genuinely reachable, not just a
defined enum member — ``governance/quarantine.py`` computes the
cross-request violation count `WhitePactRuntimeGateway.evaluate()``
consults. ``AgentContext.trust_state`` below is populated by
``governance/trust_integration.py`` when an action names a third-party
model/provider, and consulted by the gateway to downgrade a low-trust
``ALLOW`` to ``REQUIRE_APPROVAL``.

What's still genuinely not built, stated honestly: a richer policy rule
language (OPA/Rego) beyond ``governance/policy.py``'s flat
risk-tier/action-type/target matching, and wiring the gateway into
every governed surface (the MCP dispatch path is wired as of
MIGRATION_WHITEPACT_V2.md's gap-closure phase; direct Python-library
callers of the underlying engines bypass it by design — see
``THREAT_MODEL.md``'s governance-pipeline section).
"""

from __future__ import annotations

import fnmatch
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from responsibleai.governance.reason_codes import ReasonCode, format_reason
from responsibleai.governance.risk import RiskTier
from responsibleai.integrations.client import TrustCheckResult
from responsibleai.rbac.models import OrgContext

# Recognized numeric argument keys a value-limit constraint checks
# against, in priority order — the first one present in
# ActionRequest.arguments wins. A fixed, small list rather than
# scanning every numeric argument: an unrelated numeric argument (e.g.
# a page size) must never accidentally trip a dollar-value limit.
_VALUE_ARGUMENT_KEYS = ("amount_usd", "value_usd", "amount")


class GovernanceDecision(StrEnum):
    """SPEC.md Section 3.6 — the five outcomes a governed action can
    receive. The single most consequential net-new piece of Phase 8:
    every existing decision-shaped output in this codebase before this
    (``GuardrailsResult.is_blocked``, etc.) was binary."""

    ALLOW = "ALLOW"
    ALLOW_WITH_REDACTION = "ALLOW_WITH_REDACTION"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"
    QUARANTINE = "QUARANTINE"


@dataclass
class IdentityContext:
    """SPEC.md Section 3.2 — generalizes ``OrgContext`` (human/API-key
    access to the REST API and dashboard) to also cover agent and future
    workload identities, without replacing or modifying it. An
    ``IdentityContext`` either wraps a real ``OrgContext`` (the common,
    [TODAY]-backed case) or stands alone for an identity kind
    ``OrgContext`` was never meant to model (e.g. a workload identity
    with no API key at all)."""

    identity_id: str
    kind: str  # "human" | "api_key" | "agent" | "oidc" | "workload"
    org_id: str | None = None
    display_name: str | None = None
    org_context: OrgContext | None = None

    @classmethod
    def from_org_context(cls, ctx: OrgContext) -> IdentityContext:
        """The [TODAY] path: every request that already resolves to an
        ``OrgContext`` (static API key or OIDC JWT, per
        ``mcp/server.py``'s ``_authenticate``) has a real identity —
        this just describes it in the vocabulary the governance pipeline
        uses, it doesn't invent new trust."""
        return cls(
            identity_id=ctx.key_id,
            kind="oidc" if ctx.key_id.startswith("oidc:") else "api_key",
            org_id=ctx.org_id,
            display_name=ctx.org_name,
            org_context=ctx,
        )


@dataclass
class AgentContext:
    """SPEC.md Section 3.1 — an autonomous or semi-autonomous software
    actor requesting an action, distinct from the human/org identity
    that authorized it (``identity``)."""

    identity: IdentityContext
    organization_id: str | None = None
    agent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    framework: str | None = None  # "langchain" | "langgraph" | "adk" | "mcp-client" | ...
    provider: str | None = None  # "openai" | "anthropic" | "azure-openai" | ...
    model: str | None = None
    trust_state: TrustCheckResult | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.organization_id is None:
            self.organization_id = self.identity.org_id


@dataclass
class AuthorityContext:
    """SPEC.md Section 3.3 — what this *specific agent* has actually
    been delegated to do, deliberately distinct from a raw RBAC role
    (an agent's identity may hold the ADMIN role and still not have been
    delegated authority to take a given action in a given context).

    ``constraints`` is a deliberately open, deterministic key/value bag
    rather than a policy DSL — building an actual constraint language
    (OPA/Rego or similar) remains explicitly out of scope (SPEC.md's
    documented non-goal). What *is* built, in ``constraint_violation()``
    below: a fixed, small set of recognized keys, each a plain
    equality/threshold/pattern check, no expression language:

    - ``max_value_usd`` (float): denies if the action's arguments carry
      a recognized numeric value key (``amount_usd``, ``value_usd``, or
      ``amount``, first one present wins) exceeding this limit. Absent
      value argument -> not applicable, never blocks.
    - ``allowed_targets`` (list[str]): fnmatch glob patterns (e.g.
      ``"payment_*"``); the action's ``target`` must match at least one
      or the action is denied. Absent/empty -> not applicable.
    - ``denied_targets`` (list[str]): fnmatch glob patterns; a match
      denies regardless of ``allowed_targets``. Checked first.
    - ``allowed_hours_utc`` (list[int, int]): ``[start, end)`` in UTC
      hours (0-23); outside this window the action is denied. A
      deliberately simple fixed window, not a timezone-aware calendar —
      matches this package's "no feature beyond a real, stated
      requirement" rule.

    An unrecognized key in ``constraints`` is silently ignored, not an
    error — this bag was designed as forward-open (SPEC.md Section 3.3),
    and a typo'd key should not be able to accidentally disable
    enforcement of a different action's constraints checked elsewhere.
    """

    delegated_by: str  # org_id or human identity_id that granted this authority
    granted_action_types: frozenset[str]
    constraints: dict[str, Any] = field(default_factory=dict)
    require_approval_for: frozenset[str] = field(default_factory=frozenset)

    def permits(self, action_type: str) -> bool:
        return action_type in self.granted_action_types

    def constraint_violation(self, action: ActionRequest) -> str | None:
        """``None`` if every recognized constraint passes (or none
        apply); otherwise a ``format_reason()``-formatted string
        identifying which one failed. Order: denied_targets ->
        allowed_targets -> max_value_usd -> allowed_hours_utc — denies
        checked before allow-lists, narrowest scope first."""
        denied_targets = self.constraints.get("denied_targets")
        if denied_targets and any(fnmatch.fnmatch(action.target, pattern) for pattern in denied_targets):
            return format_reason(ReasonCode.TARGET_NOT_ALLOWED, target=action.target, rule="denied_targets")

        allowed_targets = self.constraints.get("allowed_targets")
        if allowed_targets and not any(fnmatch.fnmatch(action.target, pattern) for pattern in allowed_targets):
            return format_reason(ReasonCode.TARGET_NOT_ALLOWED, target=action.target, rule="allowed_targets")

        max_value_usd = self.constraints.get("max_value_usd")
        if max_value_usd is not None:
            for key in _VALUE_ARGUMENT_KEYS:
                if key in action.arguments:
                    value = action.arguments[key]
                    if isinstance(value, int | float) and value > max_value_usd:
                        return format_reason(
                            ReasonCode.VALUE_LIMIT_EXCEEDED, argument=key, value=value, limit=max_value_usd,
                        )
                    break

        allowed_hours_utc = self.constraints.get("allowed_hours_utc")
        if allowed_hours_utc is not None:
            start, end = allowed_hours_utc
            current_hour = action.proposed_at.astimezone(UTC).hour
            in_window = start <= current_hour < end if start <= end else current_hour >= start or current_hour < end
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
    """SPEC.md Section 3.4 — a proposed operation an agent wants to
    execute. ``arguments`` is whatever the target action needs (an MCP
    tool's arguments dict, an API call's payload, ...); callers are
    responsible for not putting raw secrets in it, same expectation
    SPEC.md states for the eventual ``EvidenceRecord``."""

    agent: AgentContext
    action_type: str
    target: str
    arguments: dict[str, Any] = field(default_factory=dict)
    action_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DecisionResult:
    """The gateway's output. Explicitly **not** SPEC.md's
    ``EvidenceRecord`` — no persistence, no hash chain, no
    ``policies_evaluated``/``deterministic_checks`` breakdown yet. This
    is the minimal, honest, in-memory decision output Phase 8 commits
    to; Phase 12 is what turns this (or its successor) into real,
    exportable evidence.
    """

    decision: GovernanceDecision
    action_id: str
    reason_codes: list[str] = field(default_factory=list)
    redacted_arguments: dict[str, Any] | None = None
    risk_tier: RiskTier | None = None
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # None whenever no Policy reached evaluation for this action at all
    # (a quarantine/authority/constraint short-circuit before the
    # policy-check step never consulted one) -- distinct from a Policy
    # that was consulted and had no matching rule, which still stamps
    # its version here. See Policy.version's docstring.
    policy_version: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "action_id": self.action_id,
            "reason_codes": self.reason_codes,
            "redacted_arguments": self.redacted_arguments,
            "risk_tier": self.risk_tier.value if self.risk_tier is not None else None,
            "evaluated_at": self.evaluated_at.isoformat(),
            "policy_version": self.policy_version,
        }
