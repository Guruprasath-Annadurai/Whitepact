# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
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

import hashlib
import json
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

_GENESIS_HASH = "0" * 64
_PROTECTED_EVIDENCE_FIELDS = (
    "evidence_id",
    "organization_id",
    "action_id",
    "agent_id",
    "identity_id",
    "authentication_method",
    "action_type",
    "target",
    "argument_keys",
    "request_fingerprint",
    "arguments_fingerprint",
    "purpose",
    "authority_delegated_by",
    "delegation_chain",
    "authority_version",
    "consent_id",
    "consent_version",
    "consent_state",
    "risk_tier",
    "policy_version",
    "governance_epoch",
    "approval_id",
    "execution_authorization_id",
    "execution_nonce_reference",
    "execution_target",
    "decision",
    "reason_codes",
    "framework",
    "provider",
    "model",
    "evaluated_at",
    "recorded_at",
    "integrity_version",
    "integrity_status",
    "chain_sequence",
)


def compute_canonical_evidence_hash(
    prev_hash: str | None, record: EvidenceRecord | dict[str, Any]
) -> str:
    """SHA-256 over deterministic JSON for every protected evidence field."""
    source = record.to_dict() if isinstance(record, EvidenceRecord) else dict(record)
    aliases = {"id": "evidence_id", "org_id": "organization_id"}
    for source_key, canonical_key in aliases.items():
        if canonical_key not in source and source_key in source:
            source[canonical_key] = source[source_key]
    protected = {key: source.get(key) for key in _PROTECTED_EVIDENCE_FIELDS}
    for key in ("argument_keys", "delegation_chain", "reason_codes"):
        value = protected[key]
        if isinstance(value, str):
            protected[key] = json.loads(value)
        elif protected[key] is None:
            protected[key] = []
    if isinstance(protected["evaluated_at"], datetime):
        protected["evaluated_at"] = protected["evaluated_at"].isoformat()
    protected["prev_hash"] = prev_hash or _GENESIS_HASH
    serialized = json.dumps(
        protected,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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
    # DecisionResult.policy_version's value, carried through -- None
    # whenever no Policy reached evaluation for this action, otherwise
    # exactly which persisted policy version this decision was
    # evaluated against (Policy.version's docstring).
    policy_version: int | None = None
    authentication_method: str | None = None
    request_fingerprint: str | None = None
    arguments_fingerprint: str | None = None
    purpose: str | None = None
    authority_version: str | None = None
    consent_id: str | None = None
    consent_version: str | None = None
    consent_state: str | None = None
    governance_epoch: int | None = None
    approval_id: str | None = None
    execution_authorization_id: str | None = None
    execution_nonce_reference: str | None = None
    execution_target: str | None = None
    integrity_version: int = 2
    integrity_status: str = "CANONICAL_CHAINED"
    chain_sequence: int | None = None
    # AuthorityContext.delegation_chain, carried through for the audit
    # trail -- who delegated to whom, through however many hops, not
    # just the immediate grantor authority_delegated_by already
    # records. Empty for every action whose AuthorityContext never set
    # a chain (the default), identical to before this field existed.
    delegation_chain: list[str] = field(default_factory=list)
    framework: str | None = None
    provider: str | None = None
    model: str | None = None
    prev_hash: str | None = None
    hash: str | None = None
    # ISO-8601, filled in by EvidenceRepository.record()/read back from
    # the DB row -- distinct from evaluated_at (when the gateway made
    # the decision): recorded_at is when it was actually persisted, and
    # is part of the hash material (db/evidence_repository.py's
    # _compute_entry_hash()), so an Evidence Bundle export (v3
    # authority-layer work) needs it on the record itself to recompute
    # hashes offline, without a second DB round-trip. None for any
    # EvidenceRecord built but not yet persisted (e.g. straight out of
    # build_evidence_record(), before .record() is called).
    recorded_at: str | None = None

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
            "delegation_chain": self.delegation_chain,
            "risk_tier": self.risk_tier,
            "policy_version": self.policy_version,
            "authentication_method": self.authentication_method,
            "request_fingerprint": self.request_fingerprint,
            "arguments_fingerprint": self.arguments_fingerprint,
            "purpose": self.purpose,
            "authority_version": self.authority_version,
            "consent_id": self.consent_id,
            "consent_version": self.consent_version,
            "consent_state": self.consent_state,
            "governance_epoch": self.governance_epoch,
            "approval_id": self.approval_id,
            "execution_authorization_id": self.execution_authorization_id,
            "execution_nonce_reference": self.execution_nonce_reference,
            "execution_target": self.execution_target,
            "integrity_version": self.integrity_version,
            "integrity_status": self.integrity_status,
            "chain_sequence": self.chain_sequence,
            "decision": self.decision,
            "reason_codes": self.reason_codes,
            "framework": self.framework,
            "provider": self.provider,
            "model": self.model,
            "evaluated_at": self.evaluated_at.isoformat(),
            "recorded_at": self.recorded_at,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }


def build_evidence_record(
    action: ActionRequest,
    agent: AgentContext,
    authority: AuthorityContext,
    decision: DecisionResult,
    *,
    authentication_method: str | None = None,
    authority_version: str | None = None,
    consent_id: str | None = None,
    consent_version: str | None = None,
    governance_epoch: int | None = None,
    approval_id: str | None = None,
    execution_authorization_id: str | None = None,
    execution_nonce_reference: str | None = None,
) -> EvidenceRecord:
    """Assemble an `EvidenceRecord` from a completed decision. Pure —
    no I/O, no hashing, callable from a sync context (matching
    `WhitePactRuntimeGateway.evaluate()`, which is itself sync). Persist
    the result via `EvidenceRepository.record()` to get a chained hash.
    """
    argument_material = json.dumps(
        action.arguments, sort_keys=True, separators=(",", ":"), allow_nan=False, default=str
    ).encode("utf-8")
    request_material = json.dumps(
        {
            "organization_id": agent.organization_id,
            "principal_id": agent.identity.identity_id,
            "agent_id": agent.agent_id,
            "action_type": action.action_type,
            "target": action.target,
            "purpose": action.purpose,
            "arguments_sha256": hashlib.sha256(argument_material).hexdigest(),
        },
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return EvidenceRecord(
        action_id=action.action_id,
        agent_id=agent.agent_id,
        identity_id=agent.identity.identity_id,
        action_type=action.action_type,
        target=action.target,
        argument_keys=sorted(action.arguments.keys()),
        authority_delegated_by=authority.delegated_by,
        delegation_chain=list(authority.delegation_chain),
        decision=decision.decision.value,
        reason_codes=list(decision.reason_codes),
        evaluated_at=decision.evaluated_at,
        organization_id=agent.organization_id,
        risk_tier=decision.risk_tier.value if isinstance(decision.risk_tier, RiskTier) else None,
        policy_version=decision.policy_version,
        authentication_method=authentication_method,
        request_fingerprint=hashlib.sha256(request_material).hexdigest(),
        arguments_fingerprint=hashlib.sha256(argument_material).hexdigest(),
        purpose=action.purpose,
        authority_version=authority_version,
        consent_id=consent_id,
        consent_version=consent_version,
        consent_state="VALID" if consent_id else None,
        governance_epoch=governance_epoch,
        approval_id=approval_id,
        execution_authorization_id=execution_authorization_id,
        execution_nonce_reference=(
            hashlib.sha256(execution_nonce_reference.encode("utf-8")).hexdigest()
            if execution_nonce_reference
            else None
        ),
        execution_target=action.target,
        framework=agent.framework,
        provider=agent.provider,
        model=agent.model,
    )
