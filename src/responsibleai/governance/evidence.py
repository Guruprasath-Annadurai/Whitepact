"""The evidence model — SPEC.md Section 3.7, Phase 12. This module holds
the pure, in-memory shape (`EvidenceRecord`) and its pure assembly
function (`build_evidence_record`); persistence and hash-chaining live
in `db/evidence_repository.py`, the same separation
`WhitePactRuntimeGateway` (pure decision logic) already has from
`db/mcp_usage_repository.py` (persistence) — a decision or a piece of
evidence is a value, computing one shouldn't require a database.

Honest scoping against SPEC.md's full `EvidenceRecord` shape:

- ``sanitized_arguments_metadata`` (SPEC.md's field) is implemented here
  as ``argument_keys: list[str]`` — the argument *field names* an action
  carried, never the values. This is a deliberately minimal, safe
  interpretation: field names alone can't leak a secret the way even a
  truncated or hashed value sometimes can, and no argument-classification
  logic (which fields look sensitive, etc.) exists to justify claiming
  anything richer.
- ``trust_signals`` is not populated — nothing upstream computes a
  `TrustCheckResult` automatically yet (see `models.py`'s
  `AgentContext.trust_state`, still an unpopulated field in practice).
- ``deterministic_checks`` / ``probabilistic_checks`` are not broken out
  as separate structured fields — `DecisionResult.reason_codes` already
  carries what a `GuardrailsResult`/`Policy` match found; splitting that
  into the two named buckets SPEC.md describes is real, separate,
  deferred work, not implied here.
- ``execution_result_metadata`` is not populated — this package has no
  visibility into whether/how an allowed action was actually executed
  (that happens outside the gateway entirely, wherever a caller acts on
  a `DecisionResult`).
- ``human_identity`` — SPEC.md distinguishes this from `agent_id` ("the
  ultimate human/service accountable"). Populated from
  `AgentContext.identity.identity_id`, since that's the only accountable
  identity this package tracks; no separate concept of "the human behind
  the agent, distinct from the API key/OIDC identity that authorized it"
  exists yet.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
)
from responsibleai.governance.risk import RiskTier


@dataclass
class EvidenceRecord:
    """An unpersisted, unhashed evidence record. `hash`/`prev_hash` are
    filled in by `EvidenceRepository.record()` at write time, since a
    hash chain is inherently a property of *storage order*, not
    something a pure function can compute — see that module for why.
    """

    action_id: str
    agent_id: str
    identity_id: str
    action_type: str
    target: str
    argument_keys: list[str]
    authority_delegated_by: str
    decision: str  # GovernanceDecision.value -- str so this stays JSON-native end to end
    reason_codes: list[str]
    evaluated_at: datetime
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str | None = None
    risk_tier: str | None = None  # RiskTier.value, or None if never classified
    framework: str | None = None
    provider: str | None = None
    model: str | None = None
    prev_hash: str | None = None
    hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "organization_id": self.organization_id,
            "action_id": self.action_id,
            "agent_id": self.agent_id,
            "identity_id": self.identity_id,
            "action_type": self.action_type,
            "target": self.target,
            "argument_keys": self.argument_keys,
            "authority_delegated_by": self.authority_delegated_by,
            "risk_tier": self.risk_tier,
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "framework": self.framework,
            "provider": self.provider,
            "model": self.model,
            "evaluated_at": self.evaluated_at.isoformat(),
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


def build_evidence_record(
    action: ActionRequest,
    agent: AgentContext,
    authority: AuthorityContext,
    decision: DecisionResult,
) -> EvidenceRecord:
    """Assemble an `EvidenceRecord` from a completed decision. Pure —
    no I/O, no hashing, callable from a sync context (matching
    `WhitePactRuntimeGateway.evaluate()`, which is itself sync). Persist
    the result via `EvidenceRepository.record()` to get a chained hash.
    """
    return EvidenceRecord(
        action_id=action.action_id,
        agent_id=agent.agent_id,
        identity_id=agent.identity.identity_id,
        action_type=action.action_type,
        target=action.target,
        argument_keys=sorted(action.arguments.keys()),
        authority_delegated_by=authority.delegated_by,
        decision=decision.decision.value,
        reason_codes=list(decision.reason_codes),
        evaluated_at=decision.evaluated_at,
        organization_id=agent.organization_id,
        risk_tier=decision.risk_tier.value if isinstance(decision.risk_tier, RiskTier) else None,
        framework=agent.framework,
        provider=agent.provider,
        model=agent.model,
    )
