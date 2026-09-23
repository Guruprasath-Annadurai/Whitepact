# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

import pytest

from responsibleai.governance.models import GovernanceDecision
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.manifest import WhitepactManifest
from responsibleai.sovereign.models import OutcomeDisposition, SovereignExecutionEnvelope
from responsibleai.sovereign.service import SovereignService


def test_xray_builds_minimal_graph() -> None:
    svc = SovereignService()
    ctx = SovereignContext(organization_id="org-1", principal_id="human-1")
    result = svc.build_xray(ctx)
    assert result.graph.organization_id == "org-1"
    assert len(result.graph.nodes) >= 2


def test_trace_enforces_tenant_isolation() -> None:
    svc = SovereignService()
    ctx = SovereignContext(organization_id="org-a")
    envelope = SovereignExecutionEnvelope(organization_id="org-b", environment="development")
    with pytest.raises(SovereignTenantIsolationError):
        svc.trace_authority(ctx, envelope)


def test_drift_reports_structural_facts_not_scores() -> None:
    svc = SovereignService()
    ctx = SovereignContext(organization_id="org-1")
    manifest = WhitepactManifest(
        organization_id="org-1",
        capabilities=[{"capability_id": "cap.read", "requires_approval": False}],
    )
    report = svc.detect_drift(ctx, manifest=manifest, effective_capability_ids=["cap.write"])
    codes = {f.code for f in report.facts}
    assert "EXPECTED_CAPABILITY_ABSENT" in codes
    assert "UNEXPECTED_CAPABILITY_PRESENT" in codes


def test_explain_unknown_sets_reconciliation() -> None:
    svc = SovereignService()
    ctx = SovereignContext(organization_id="org-1")
    exp = svc.explain_decision(ctx, disposition=OutcomeDisposition.UNKNOWN)
    assert exp.reconciliation_required is True


def test_explain_governance_decision() -> None:
    svc = SovereignService()
    ctx = SovereignContext(organization_id="org-1")
    exp = svc.explain_decision(
        ctx,
        disposition=GovernanceDecision.DENY,
        facts={"rule": "policy.block"},
    )
    assert exp.disposition == GovernanceDecision.DENY
