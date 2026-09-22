# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical Sovereign representations — describe authority, never create it."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from responsibleai.governance.models import GovernanceDecision
from responsibleai.sovereign.graph import AuthorityGraph


class OutcomeDisposition(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    DENIED = "DENIED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    UNKNOWN = "UNKNOWN"
    INCOMPLETE = "INCOMPLETE"


class SovereignExecutionEnvelope(BaseModel):
    """Immutable-ish view of a governed operation's known facts."""

    organization_id: str
    environment: str
    principal_id: str | None = None
    agent_id: str | None = None
    application_id: str | None = None
    intent_summary: str | None = None
    action: str | None = None
    target_fingerprint: str | None = None
    authority_chain: list[str] = Field(default_factory=list)
    delegation_chain: list[str] = Field(default_factory=list)
    capability_id: str | None = None
    policy_refs: list[str] = Field(default_factory=list)
    risk_facts: dict[str, Any] = Field(default_factory=dict)
    approval_refs: list[str] = Field(default_factory=list)
    judgment: GovernanceDecision | None = None
    governance_epoch: int | None = None
    execution_grant_ref: str | None = None
    nonce_ref: str | None = None
    expires_at: str | None = None
    effect_id: str | None = None
    evidence_id: str | None = None
    outcome_id: str | None = None
    outcome: OutcomeDisposition = OutcomeDisposition.INCOMPLETE
    reconciliation_required: bool = False
    source_provenance: dict[str, Any] = Field(default_factory=dict)
    observability: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "forbid"}


class ExplanationKind(StrEnum):
    FACT = "FACT"
    DERIVED = "DERIVED"
    MISSING = "MISSING"


class ExplanationItem(BaseModel):
    kind: ExplanationKind
    code: str
    message: str
    refs: list[str] = Field(default_factory=list)


class ConstitutionalExplanation(BaseModel):
    disposition: GovernanceDecision | OutcomeDisposition
    items: list[ExplanationItem] = Field(default_factory=list)
    reconciliation_required: bool = False


class AuthorityComparison(BaseModel):
    organization_id: str
    expected_only: list[str] = Field(default_factory=list)
    effective_only: list[str] = Field(default_factory=list)
    shared: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DriftFact(BaseModel):
    code: str
    message: str
    expected_ref: str | None = None
    effective_ref: str | None = None


class AuthorityDriftReport(BaseModel):
    organization_id: str
    facts: list[DriftFact] = Field(default_factory=list)
    manifest_path: str | None = None


class XRayResult(BaseModel):
    graph: AuthorityGraph
    envelope_hints: list[str] = Field(default_factory=list)
