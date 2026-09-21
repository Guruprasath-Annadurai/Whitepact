# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign service layer — single canonical boundary for all interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from responsibleai.governance.models import GovernanceDecision
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignCapabilityError
from responsibleai.sovereign.graph import (
    AuthorityGraph,
    EdgeDerivation,
    GraphEdge,
    GraphEdgeKind,
    GraphNode,
    GraphNodeKind,
    GraphProvenance,
)
from responsibleai.sovereign.manifest import WhitepactManifest, load_manifest
from responsibleai.sovereign.models import (
    AuthorityComparison,
    AuthorityDriftReport,
    ConstitutionalExplanation,
    DriftFact,
    ExplanationItem,
    ExplanationKind,
    OutcomeDisposition,
    SovereignExecutionEnvelope,
    XRayResult,
)
from responsibleai.sovereign.protocol import (
    PROTOCOL_VERSION,
    SOVEREIGN_VERSION,
    SovereignCapabilities,
    SovereignFeature,
    SovereignStatus,
)
from responsibleai.sovereign.redaction import redact_for_debugger
from responsibleai.sovereign.tenant import assert_same_organization
from responsibleai.sovereign.zero_effect import zero_effect_operation


class SovereignService:
    """Read/simulation façade over canonical governance truth."""

    def __init__(self, capabilities: SovereignCapabilities | None = None) -> None:
        self._capabilities = capabilities or SovereignCapabilities.negotiate()

    def get_capabilities(self) -> SovereignCapabilities:
        return self._capabilities

    def get_status(self) -> SovereignStatus:
        return SovereignStatus(
            sovereign_version=SOVEREIGN_VERSION,
            protocol_version=PROTOCOL_VERSION,
            capabilities=self._capabilities,
        )

    def _require(self, feature: SovereignFeature) -> None:
        try:
            self._capabilities.require(feature)
        except SovereignCapabilityError:
            raise

    @zero_effect_operation
    def build_xray(self, ctx: SovereignContext) -> XRayResult:
        self._require(SovereignFeature.XRAY)
        org = ctx.organization_id
        nodes = [
            GraphNode(
                node_id=f"org:{org}",
                kind=GraphNodeKind.ORGANIZATION,
                label=org,
                organization_id=org,
            )
        ]
        if ctx.principal_id:
            nodes.append(
                GraphNode(
                    node_id=f"principal:{ctx.principal_id}",
                    kind=GraphNodeKind.HUMAN,
                    label=ctx.principal_id,
                    organization_id=org,
                )
            )
            edges = [
                GraphEdge(
                    edge_id=f"edge:member:{ctx.principal_id}",
                    kind=GraphEdgeKind.MEMBER_OF,
                    from_node_id=f"principal:{ctx.principal_id}",
                    to_node_id=f"org:{org}",
                    provenance=GraphProvenance(
                        source="sovereign_context",
                        derivation=EdgeDerivation.DIRECT,
                        explanation="Principal scoped to organization from SovereignContext",
                    ),
                )
            ]
        else:
            edges = []
        graph = AuthorityGraph(organization_id=org, nodes=nodes, edges=edges)
        return XRayResult(
            graph=graph,
            envelope_hints=["Phase A: minimal topology from request context only"],
        )

    @zero_effect_operation
    def explain_decision(
        self,
        ctx: SovereignContext,
        *,
        disposition: GovernanceDecision | OutcomeDisposition,
        facts: dict[str, Any] | None = None,
    ) -> ConstitutionalExplanation:
        self._require(SovereignFeature.EXPLAIN)
        items: list[ExplanationItem] = []
        safe_facts = redact_for_debugger(facts or {})
        for key, value in safe_facts.items():
            items.append(
                ExplanationItem(
                    kind=ExplanationKind.FACT,
                    code=str(key),
                    message=str(value),
                )
            )
        if disposition == OutcomeDisposition.UNKNOWN:
            items.append(
                ExplanationItem(
                    kind=ExplanationKind.MISSING,
                    code="UNKNOWN_STATE",
                    message="Outcome is UNKNOWN; reconciliation may be required",
                )
            )
        reconciliation = disposition == OutcomeDisposition.UNKNOWN
        return ConstitutionalExplanation(
            disposition=disposition,
            items=items,
            reconciliation_required=reconciliation,
        )

    @zero_effect_operation
    def trace_authority(
        self,
        ctx: SovereignContext,
        envelope: SovereignExecutionEnvelope,
    ) -> SovereignExecutionEnvelope:
        self._require(SovereignFeature.TRACE)
        assert_same_organization(ctx.organization_id, envelope.organization_id, resource_kind="trace")
        return envelope

    @zero_effect_operation
    def compare_authority(
        self,
        ctx: SovereignContext,
        *,
        expected: WhitepactManifest,
        effective_capability_ids: list[str],
    ) -> AuthorityComparison:
        self._require(SovereignFeature.AUTHORITY_COMPARE)
        assert_same_organization(ctx.organization_id, expected.organization_id, resource_kind="manifest")
        expected_ids = {c.capability_id for c in expected.capabilities}
        effective_ids = set(effective_capability_ids)
        return AuthorityComparison(
            organization_id=ctx.organization_id,
            expected_only=sorted(expected_ids - effective_ids),
            effective_only=sorted(effective_ids - expected_ids),
            shared=sorted(expected_ids & effective_ids),
            notes=["Manifest declares expected authority only; it does not grant capabilities"],
        )

    @zero_effect_operation
    def detect_drift(
        self,
        ctx: SovereignContext,
        *,
        manifest: WhitepactManifest,
        effective_capability_ids: list[str],
    ) -> AuthorityDriftReport:
        self._require(SovereignFeature.AUTHORITY_DRIFT)
        comparison = self.compare_authority(
            ctx, expected=manifest, effective_capability_ids=effective_capability_ids
        )
        facts: list[DriftFact] = []
        for cap in comparison.expected_only:
            facts.append(
                DriftFact(
                    code="EXPECTED_CAPABILITY_ABSENT",
                    message=f"Expected capability {cap} not present in effective authority",
                    expected_ref=cap,
                )
            )
        for cap in comparison.effective_only:
            facts.append(
                DriftFact(
                    code="UNEXPECTED_CAPABILITY_PRESENT",
                    message=f"Effective capability {cap} not declared in manifest",
                    effective_ref=cap,
                )
            )
        return AuthorityDriftReport(
            organization_id=ctx.organization_id,
            facts=facts,
        )

    def load_expected_manifest(self, path: Path) -> WhitepactManifest:
        self._require(SovereignFeature.AUTHORITY_EXPECTED)
        return load_manifest(path)
