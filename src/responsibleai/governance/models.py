"""Core entities for the WhitePact runtime governance pipeline —
SPEC.md Section 3. Each dataclass below is the concrete, executable
form of a **[TARGET]** entity SPEC.md defines; see that document for
the full rationale and the [TODAY] precedent each one builds on.

Risk-tiered routing (Phase 9, ``governance/risk.py``) and a first policy
engine (Phase 10, ``governance/policy.py``) now exist and are wired into
``WhitePactRuntimeGateway`` — see those modules' docstrings. Still
deliberately not included here (real gaps, not oversights — later
phases per MIGRATION_WHITEPACT_V2.md):

- ``EvidenceRecord`` / persisted, hash-chained decision evidence
  (Phase 12) — ``DecisionResult`` below is an in-memory, unpersisted
  decision output, not the immutable audit trail SPEC.md Section 3.7
  describes. The existing hash-chaining primitive it will generalize
  from already exists and is real
  (``db/public_incident_repository.py``); wiring it to decisions is
  separate work.
- A standing "pattern of violations" tracker — ``GovernanceDecision.QUARANTINE``
  is a real member of the enum (the decision model is genuinely
  five-way), but nothing in this package ever *produces* it yet: that
  requires cross-request state this phase doesn't build.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from responsibleai.governance.risk import RiskTier
from responsibleai.integrations.client import TrustCheckResult
from responsibleai.rbac.models import OrgContext


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
    (e.g. ``{"max_transaction_usd": 500}``) rather than a policy DSL —
    building an actual constraint language is Phase 10's job, not
    this one's.
    """

    delegated_by: str  # org_id or human identity_id that granted this authority
    granted_action_types: frozenset[str]
    constraints: dict[str, Any] = field(default_factory=dict)
    require_approval_for: frozenset[str] = field(default_factory=frozenset)

    def permits(self, action_type: str) -> bool:
        return action_type in self.granted_action_types


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "action_id": self.action_id,
            "reason_codes": self.reason_codes,
            "redacted_arguments": self.redacted_arguments,
            "risk_tier": self.risk_tier.value if self.risk_tier is not None else None,
            "evaluated_at": self.evaluated_at.isoformat(),
        }
