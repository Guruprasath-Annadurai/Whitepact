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
    - ``max_delegation_depth`` (int): denies if ``len(delegation_chain)``
      exceeds this — see ``delegation_chain`` below.
    - ``memory_scope`` (str, Memory Authority/Memory Firewall, v3
      authority-layer work): a namespace prefix (e.g.
      ``"org:acme:agent:bot1"``); denies if the action's ``memory_scope``
      argument is neither exactly this value nor a sub-scope of it
      (``requested == memory_scope`` or
      ``requested.startswith(f"{memory_scope}:")``) — cross-tenant/
      cross-agent memory isolation. Absent ``memory_scope`` argument ->
      not applicable, never blocks (same "argument-driven, not
      action-type-gated" pattern as ``max_value_usd``).

    An unrecognized key in ``constraints`` is silently ignored, not an
    error — this bag was designed as forward-open (SPEC.md Section 3.3),
    and a typo'd key should not be able to accidentally disable
    enforcement of a different action's constraints checked elsewhere.

    ``delegation_chain`` (v3 authority-layer work) closes "authority
    model remains coarse... no delegation chains": the full ordered
    path of identity_ids from the ultimate root authority down through
    every intermediate sub-delegation to ``delegated_by`` itself (the
    last element, when the chain is non-empty, always equals
    ``delegated_by`` — enforced in ``__post_init__``). Empty (the
    default) means "no multi-hop chain was recorded, this is a direct
    grant" — every ``AuthorityContext`` built before this field existed
    behaves identically to one with an empty chain, since nothing reads
    it unless a caller opts in by setting ``max_delegation_depth``.
    This is deliberately *not* a trust-scoring or transitive-permission
    algebra (e.g. "B may only grant what A granted B") — that's a much
    larger, separate feature; what's built here is the audit trail (who
    delegated to whom, recorded on every `EvidenceRecord`) and a single
    bounded-depth guard, which is the concrete, stated requirement.
    """

    delegated_by: str  # org_id or human identity_id that granted this authority
    granted_action_types: frozenset[str]
    constraints: dict[str, Any] = field(default_factory=dict)
    require_approval_for: frozenset[str] = field(default_factory=frozenset)
    delegation_chain: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.delegation_chain and self.delegation_chain[-1] != self.delegated_by:
            raise ValueError(
                f"AuthorityContext.delegation_chain[-1] ({self.delegation_chain[-1]!r}) must equal "
                f"delegated_by ({self.delegated_by!r}) -- the chain's last link is who actually "
                "granted this authority."
            )

    def permits(self, action_type: str) -> bool:
        return action_type in self.granted_action_types

    def constraint_violation(self, action: ActionRequest) -> str | None:
        """``None`` if every recognized constraint passes (or none
        apply); otherwise a ``format_reason()``-formatted string
        identifying which one failed. Order: denied_targets ->
        allowed_targets -> max_value_usd -> allowed_hours_utc ->
        max_delegation_depth -> memory_scope — denies checked before
        allow-lists, narrowest scope first."""
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

        max_delegation_depth = self.constraints.get("max_delegation_depth")
        if max_delegation_depth is not None and len(self.delegation_chain) > max_delegation_depth:
            return format_reason(
                ReasonCode.ACTION_NOT_ALLOWED,
                rule="max_delegation_depth",
                depth=len(self.delegation_chain),
                limit=max_delegation_depth,
            )

        memory_scope = self.constraints.get("memory_scope")
        if memory_scope is not None:
            requested_scope = action.arguments.get("memory_scope")
            if isinstance(requested_scope, str) and not (
                requested_scope == memory_scope or requested_scope.startswith(f"{memory_scope}:")
            ):
                return format_reason(
                    ReasonCode.MEMORY_SCOPE_VIOLATION,
                    requested_scope=requested_scope,
                    allowed_scope=memory_scope,
                )

        return None

    def validate_delegation_to(self, child: AuthorityContext) -> str | None:
        """Convenience wrapper — see module-level `validate_attenuation()`
        for what this actually checks and its documented limitations."""
        return validate_attenuation(self, child)


def validate_attenuation(parent: AuthorityContext, child: AuthorityContext) -> str | None:
    """The authority-attenuation invariant: a delegated ``AuthorityContext``
    must never grant more than the ``AuthorityContext`` that delegated it
    held. ``None`` if ``child`` is attenuated (equal or narrower) relative
    to ``parent``; otherwise a `format_reason()`-formatted string naming
    the field that expanded.

    This is deliberately checked between two already-constructed
    ``AuthorityContext`` objects, not wired into a "spawn a child from a
    parent" constructor — no such constructor exists yet in this
    codebase, and inventing one wasn't part of the concrete, stated
    requirement. Callers that build a delegated authority (a future
    delegation-issuance endpoint, or an agent-management surface) should
    call this before persisting/using the child authority they're about
    to grant.

    What is checked, one violation short-circuits (first one found wins,
    same "narrowest scope first" convention as ``constraint_violation()``):

    - ``granted_action_types``: child's must be a subset of parent's —
      a delegated authority can never be granted an action type its
      delegator didn't itself hold.
    - ``constraints["max_value_usd"]``: child's limit (if parent has one)
      must be set and must not exceed parent's. Parent having no limit
      at all means parent is unconstrained here — nothing to attenuate.
    - ``constraints["denied_targets"]``: every pattern the parent denied
      must still be denied by the child — delegation can add denials,
      never lift one.
    - ``constraints["allowed_targets"]``: if parent restricts targets,
      child must also restrict targets, and every child pattern must
      already appear in parent's list. This is an exact-pattern-string
      subset check, not full glob-algebra subset reasoning (e.g.
      recognizing that ``"payment_a"`` is covered by ``"payment_*"``) —
      a deliberately simple, honestly-scoped first version; a child
      using a differently-worded but semantically-narrower pattern than
      its parent's will incorrectly fail this check rather than pass.
    - ``constraints["max_delegation_depth"]``: if parent sets one,
      child's (if set) must not exceed it, and child must set one too —
      leaving it unset where the parent constrained it would let the
      child's own future re-delegation go unbounded.
    - ``require_approval_for``: for every action type the parent both
      granted and required approval for, if the child was also granted
      that action type, the child must keep the approval requirement —
      delegation can't silently drop a human-in-the-loop gate.

    Explicitly **not** checked here (documented, not silently skipped):
    ``constraints["allowed_hours_utc"]`` (comparing two time windows for
    subset-ness, including UTC wraparound, is real interval math this
    first version doesn't attempt) and ``delegation_chain`` identity/
    depth consistency (already covered separately by
    ``constraint_violation()``'s own ``max_delegation_depth`` check
    against ``len(self.delegation_chain)`` at evaluation time).
    """
    if not child.granted_action_types <= parent.granted_action_types:
        expanded = child.granted_action_types - parent.granted_action_types
        return format_reason(
            ReasonCode.DELEGATION_AUTHORITY_ESCALATION,
            field="granted_action_types",
            expanded=",".join(sorted(expanded)),
        )

    parent_max_value = parent.constraints.get("max_value_usd")
    if parent_max_value is not None:
        child_max_value = child.constraints.get("max_value_usd")
        if child_max_value is None or child_max_value > parent_max_value:
            return format_reason(
                ReasonCode.DELEGATION_AUTHORITY_ESCALATION,
                field="max_value_usd",
                parent_limit=parent_max_value,
                child_limit=child_max_value,
            )

    parent_denied = set(parent.constraints.get("denied_targets") or [])
    child_denied = set(child.constraints.get("denied_targets") or [])
    if not parent_denied <= child_denied:
        lifted = parent_denied - child_denied
        return format_reason(
            ReasonCode.DELEGATION_AUTHORITY_ESCALATION,
            field="denied_targets",
            lifted=",".join(sorted(lifted)),
        )

    parent_allowed = parent.constraints.get("allowed_targets")
    if parent_allowed is not None:
        child_allowed = child.constraints.get("allowed_targets")
        if child_allowed is None or not set(child_allowed) <= set(parent_allowed):
            return format_reason(
                ReasonCode.DELEGATION_AUTHORITY_ESCALATION,
                field="allowed_targets",
                child_allowed=",".join(sorted(child_allowed)) if child_allowed else "<unset>",
            )

    parent_max_depth = parent.constraints.get("max_delegation_depth")
    if parent_max_depth is not None:
        child_max_depth = child.constraints.get("max_delegation_depth")
        if child_max_depth is None or child_max_depth > parent_max_depth:
            return format_reason(
                ReasonCode.DELEGATION_AUTHORITY_ESCALATION,
                field="max_delegation_depth",
                parent_limit=parent_max_depth,
                child_limit=child_max_depth,
            )

    relevant_parent_approval = parent.require_approval_for & child.granted_action_types
    if not relevant_parent_approval <= child.require_approval_for:
        dropped = relevant_parent_approval - child.require_approval_for
        return format_reason(
            ReasonCode.DELEGATION_AUTHORITY_ESCALATION,
            field="require_approval_for",
            dropped=",".join(sorted(dropped)),
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
