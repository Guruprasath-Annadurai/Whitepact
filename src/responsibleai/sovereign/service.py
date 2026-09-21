# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign service layer — single canonical boundary for all interfaces."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from responsibleai.governance.models import GovernanceDecision
from responsibleai.sovereign.authority_engine import (
    AuthorityCompareResult,
    compare_effective_snapshots,
    compare_manifest_to_effective,
    detect_structural_drift,
)
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.debugger import explain_from_evidence, explain_from_identity
from responsibleai.sovereign.effective import EffectiveAuthoritySnapshot, load_effective_authority
from responsibleai.sovereign.errors import SovereignCapabilityError
from responsibleai.sovereign.graph import (
    AuthorityGraph,
    EdgeDerivation,
    GraphEdge,
    GraphEdgeKind,
    GraphNode,
    GraphNodeKind,
    GraphProvenance,
    GraphQueryBudget,
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
from responsibleai.sovereign.observation import SovereignObservation, observe_authority
from responsibleai.sovereign.policy_lab import PolicyLabReport, PolicyTestCase, run_policy_tests
from responsibleai.sovereign.protocol import (
    PROTOCOL_VERSION,
    SOVEREIGN_VERSION,
    SovereignCapabilities,
    SovereignFeature,
    SovereignStatus,
)
from responsibleai.sovereign.redaction import redact_for_debugger
from responsibleai.sovereign.shadow import ShadowObservation, evaluate_shadow
from responsibleai.sovereign.simulation import (
    BlastRadiusResult,
    MissionSimulationResult,
    simulate_blast_radius,
    simulate_mission,
)
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.tenant import assert_same_organization
from responsibleai.sovereign.trace_builder import AuthorityTrace, build_trace_from_evidence
from responsibleai.sovereign.xray_builder import build_repository_xray
from responsibleai.sovereign.zero_effect import zero_effect_operation


class SovereignService:
    """Read/simulation façade over canonical governance truth."""

    def __init__(
        self,
        capabilities: SovereignCapabilities | None = None,
        store: SovereignCanonicalStore | None = None,
    ) -> None:
        self._capabilities = capabilities or SovereignCapabilities.negotiate()
        self._store = store

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

    def _require_store(self) -> SovereignCanonicalStore:
        if self._store is None:
            raise SovereignCapabilityError(
                "Canonical store not configured — repository-backed Sovereign unavailable"
            )
        return self._store

    @zero_effect_operation
    def build_xray(self, ctx: SovereignContext) -> XRayResult:
        """Sync fallback when no store (Phase A compatibility)."""
        self._require(SovereignFeature.XRAY)
        if self._store is not None:
            raise SovereignCapabilityError(
                "Use async build_xray_async when a canonical store is configured"
            )
        org = ctx.organization_id
        nodes = [
            GraphNode(
                node_id=f"org:{org}",
                kind=GraphNodeKind.ORGANIZATION,
                label=org,
                organization_id=org,
            )
        ]
        edges: list[GraphEdge] = []
        if ctx.principal_id:
            nodes.append(
                GraphNode(
                    node_id=f"principal:{ctx.principal_id}",
                    kind=GraphNodeKind.HUMAN,
                    label=ctx.principal_id,
                    organization_id=org,
                )
            )
            edges.append(
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
            )
        graph = AuthorityGraph(organization_id=org, nodes=nodes, edges=edges)
        return XRayResult(graph=graph, envelope_hints=["No canonical store — context-only graph"])

    @zero_effect_operation
    async def build_xray_async(
        self,
        ctx: SovereignContext,
        *,
        budget: GraphQueryBudget | None = None,
    ) -> XRayResult:
        self._require(SovereignFeature.XRAY)
        store = self._require_store()
        graph = await build_repository_xray(store, ctx, budget=budget)
        return XRayResult(
            graph=graph,
            envelope_hints=["Repository-backed topology from canonical WhitePact stores"],
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
    async def explain_evidence_async(
        self, ctx: SovereignContext, evidence_id: str
    ) -> ConstitutionalExplanation:
        self._require(SovereignFeature.EXPLAIN)
        return await explain_from_evidence(self._require_store(), ctx, evidence_id)

    @zero_effect_operation
    async def explain_identity_async(
        self, ctx: SovereignContext, identity_id: str
    ) -> ConstitutionalExplanation:
        self._require(SovereignFeature.EXPLAIN)
        return await explain_from_identity(self._require_store(), ctx, identity_id)

    @zero_effect_operation
    def trace_authority(
        self,
        ctx: SovereignContext,
        envelope: SovereignExecutionEnvelope,
    ) -> SovereignExecutionEnvelope:
        self._require(SovereignFeature.TRACE)
        assert_same_organization(
            ctx.organization_id, envelope.organization_id, resource_kind="trace"
        )
        return envelope

    @zero_effect_operation
    async def trace_evidence_async(self, ctx: SovereignContext, evidence_id: str) -> AuthorityTrace:
        self._require(SovereignFeature.TRACE)
        return await build_trace_from_evidence(self._require_store(), ctx, evidence_id)

    @zero_effect_operation
    async def load_effective_async(self, ctx: SovereignContext) -> EffectiveAuthoritySnapshot:
        self._require(SovereignFeature.AUTHORITY_EFFECTIVE)
        return await load_effective_authority(
            self._require_store(), ctx.organization_id, environment=ctx.environment
        )

    @zero_effect_operation
    def compare_authority(
        self,
        ctx: SovereignContext,
        *,
        expected: WhitepactManifest,
        effective_capability_ids: list[str],
    ) -> AuthorityComparison:
        self._require(SovereignFeature.AUTHORITY_COMPARE)
        assert_same_organization(
            ctx.organization_id, expected.organization_id, resource_kind="manifest"
        )
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
    async def compare_manifest_async(
        self, ctx: SovereignContext, manifest: WhitepactManifest
    ) -> AuthorityCompareResult:
        self._require(SovereignFeature.AUTHORITY_COMPARE)
        return await compare_manifest_to_effective(self._require_store(), ctx, manifest)

    @zero_effect_operation
    async def compare_snapshots_async(
        self,
        ctx: SovereignContext,
        left: EffectiveAuthoritySnapshot,
        right: EffectiveAuthoritySnapshot,
    ) -> AuthorityCompareResult:
        self._require(SovereignFeature.AUTHORITY_COMPARE)
        return await compare_effective_snapshots(ctx, left, right)

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
        return AuthorityDriftReport(organization_id=ctx.organization_id, facts=facts)

    @zero_effect_operation
    async def detect_drift_async(
        self,
        ctx: SovereignContext,
        manifest: WhitepactManifest,
        *,
        prior_effective: EffectiveAuthoritySnapshot | None = None,
    ) -> AuthorityDriftReport:
        self._require(SovereignFeature.AUTHORITY_DRIFT)
        return await detect_structural_drift(
            self._require_store(), ctx, manifest, prior_effective=prior_effective
        )

    @zero_effect_operation
    async def observe_async(
        self, ctx: SovereignContext, *, previous_fingerprint: str | None = None
    ) -> SovereignObservation:
        return await observe_authority(
            self._require_store(), ctx, previous_fingerprint=previous_fingerprint
        )

    def load_expected_manifest(self, path: Path) -> WhitepactManifest:
        self._require(SovereignFeature.AUTHORITY_EXPECTED)
        return load_manifest(path)

    @zero_effect_operation
    async def simulate_blast_radius_async(
        self,
        ctx: SovereignContext,
        *,
        actor_identity_id: str,
        hypothetical_extra_capabilities: frozenset[str] = frozenset(),
    ) -> BlastRadiusResult:
        self._require(SovereignFeature.SIMULATE_BLAST_RADIUS)
        return await simulate_blast_radius(
            self._require_store(),
            ctx,
            actor_identity_id=actor_identity_id,
            hypothetical_extra_capabilities=frozenset(hypothetical_extra_capabilities),
        )

    @zero_effect_operation
    async def simulate_mission_async(
        self,
        ctx: SovereignContext,
        *,
        agent_id: str,
        steps: list[str],
    ) -> MissionSimulationResult:
        self._require(SovereignFeature.SIMULATE_MISSION)
        return await simulate_mission(self._require_store(), ctx, agent_id=agent_id, steps=steps)

    @zero_effect_operation
    def evaluate_shadow(self, ctx: SovereignContext, **kwargs: object) -> ShadowObservation:
        self._require(SovereignFeature.SHADOW)
        return evaluate_shadow(ctx, **kwargs)  # type: ignore[arg-type]

    @zero_effect_operation
    async def run_policy_tests_async(
        self, ctx: SovereignContext, cases: list[PolicyTestCase]
    ) -> PolicyLabReport:
        self._require(SovereignFeature.POLICY_LAB)
        return await run_policy_tests(self._require_store(), ctx, cases)
