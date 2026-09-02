"""Tests for Enterprise Neural Phase 10 (Brain Policy + Risk Engine).

Per `docs/enterprise-neural/10_PHASE10_DESIGN.md`: the "Brain"
(SPEC.md §2.5's name for `governance/gateway.py`'s risk classification
+ policy evaluation pipeline) already exists, is real, tested, and
unconditionally wired into every live governed-call path — this
directive's own Phase 10 name refers to SPEC.md's pre-existing
"Phase 9" (`risk.py`) and "Phase 10" (`policy.py`) work, not a
component to build from scratch. This phase's job is to *prove* the
properties that make it trustworthy against the real, existing code —
not fixtures, not mocks — the same evidence-not-rebuild approach Phase
8 took for the LLM/agent security boundary.

Two kinds of evidence:
1. Structural regression guards: source-text scans confirming
   `Policy.evaluate()` and `classify_action_risk()` are each called
   only from the known, audited call sites. Heuristic (text-based, not
   a full AST/import-graph analysis), documented as such — same
   honesty as Phase 8's own guards and
   `scripts/rotate_field_encryption_key.py`'s legacy-ciphertext check.
2. Runtime tests: every decision the gateway produces carries a real
   risk tier, a matching `Policy` rule actually gates the outcome
   through the real gateway, and attacker-controlled
   `ActionRequest.arguments` cannot forge either.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.policy import Policy, PolicyRule
from responsibleai.governance.risk import RiskTier, classify_action_risk

_SRC_ROOT = Path(__file__).parent.parent / "src" / "responsibleai"


def _call_sites(pattern_text: str, defining_file: Path) -> list[Path]:
    """Every `.py` file under `_SRC_ROOT` containing `pattern_text`,
    other than `defining_file` itself. Heuristic text scan — see
    module docstring."""
    pattern = re.compile(pattern_text)
    hits = []
    for path in _SRC_ROOT.rglob("*.py"):
        if path == defining_file:
            continue
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            hits.append(path)
    return hits


class TestPolicyEvaluateSingleCallSite:
    def test_policy_evaluate_is_only_called_from_gateway(self) -> None:
        """`Policy.evaluate()` must only ever be consulted from
        `WhitePactRuntimeGateway.evaluate()`'s own ordered decision
        chain -- a second call site anywhere else would mean a policy
        rule could gate (or fail to gate) an action outside the
        gateway's documented step ordering, silently changing what
        "Policy (Phase 10)" actually governs."""
        defining_file = _SRC_ROOT / "governance" / "gateway.py"
        hits = _call_sites(r"\bpolicy\.evaluate\(", defining_file)
        assert hits == [], (
            f"Policy.evaluate() called outside governance/gateway.py: {hits} -- "
            "WhitePactRuntimeGateway.evaluate() must be the only caller."
        )


class TestClassifyActionRiskKnownCallSites:
    def test_classify_action_risk_has_only_the_three_audited_call_sites(self) -> None:
        """Per `10_PHASE10_DESIGN.md`'s audit: `classify_action_risk()`
        is called from `gateway.py` (the gated evaluation itself) and
        two documented pre-gateway short-circuit paths in
        `upstream_dispatch.py` (unregistered server, BLOCKED trust
        tier) that still need a risk_tier value for evidence
        consistency on an early exit. A new call site would mean risk
        tiering is happening somewhere this audit doesn't account
        for.

        Security Remediation Gap 2 (`REMEDIATION_GAP2_STDIO_GOVERNANCE.md`)
        briefly added a fourth call site in `mcp/server.py`'s
        `_call_tool()`, gated behind `enterprise_mode`, to decide
        whether a self-hosted stdio call was privileged enough to
        block. Heart Enforcement Chokepoint Closure Phase E2 removed
        it again: `enterprise_mode=true` now blocks ALL stdio tool
        calls unconditionally (stdio has no identity to check Heart
        legitimacy against at any risk tier), so there is no longer
        anything for a per-call risk-tier lookup to decide on that
        path -- back down to the original three call sites, not a
        regression."""
        defining_file = _SRC_ROOT / "governance" / "risk.py"
        hits = _call_sites(r"\bclassify_action_risk\(", defining_file)
        known = {
            _SRC_ROOT / "governance" / "gateway.py",
            _SRC_ROOT / "mcp" / "upstream_dispatch.py",
        }
        unexpected = [h for h in hits if h not in known]
        assert unexpected == [], (
            f"classify_action_risk() called from unaudited location(s): {unexpected} -- "
            "update the design doc's audit deliberately if this is intentional new wiring, "
            "don't leave this guard silently broken."
        )
        assert set(hits) == known, (
            f"expected call sites {known}, found {set(hits)} -- "
            "one of the two known upstream_dispatch.py short-circuits may have been removed."
        )


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(
        identity=IdentityContext(identity_id="agent1", kind="api_key", org_id=org_id)
    )


def _authority(action_types: frozenset[str]) -> AuthorityContext:
    return AuthorityContext(delegated_by="org-1", granted_action_types=action_types)


class TestEveryDecisionCarriesARealRiskTier:
    """gateway.py's own docstring, step 3: 'every action gets a
    RiskTier, always recorded on the result, whether or not a Policy
    is supplied.' Enforced here as a property, not left as a comment
    someone could silently stop honoring."""

    def test_allowed_action_carries_risk_tier(self) -> None:
        gateway = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="rai_scan")
        decision = gateway.evaluate(action, _authority(frozenset({"mcp_tool_call"})))
        assert decision.risk_tier is not None
        assert decision.risk_tier == RiskTier.LOW

    def test_denied_action_still_carries_risk_tier(self) -> None:
        gateway = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="rai_scan")
        decision = gateway.evaluate(action, _authority(frozenset()))
        assert decision.decision == GovernanceDecision.DENY
        assert decision.risk_tier is not None

    def test_quarantined_action_still_carries_risk_tier(self) -> None:
        gateway = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="rai_scan")
        decision = gateway.evaluate(
            action, _authority(frozenset({"mcp_tool_call"})), recent_violation_count=999
        )
        assert decision.decision == GovernanceDecision.QUARANTINE
        assert decision.risk_tier is not None


class TestPolicyRuleActuallyGatesTheRealGateway:
    """Not a test of Policy.evaluate() in isolation (test_governance_policy.py
    already covers that) -- this proves a policy rule reaches and
    controls the outcome through the real
    WhitePactRuntimeGateway.evaluate() call chain, matching what
    mcp/governance_integration.py and mcp/upstream_dispatch.py
    actually invoke in production."""

    def test_matching_deny_rule_denies_through_the_real_gateway(self) -> None:
        gateway = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="rai_hallucination"
        )
        risk_tier = classify_action_risk(action.action_type, action.target)
        assert risk_tier == RiskTier.HIGH
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="r1",
                    reason_code="no_high_risk_tools",
                    effect=GovernanceDecision.DENY,
                    risk_tiers=frozenset({RiskTier.HIGH}),
                )
            ],
        )
        decision = gateway.evaluate(action, _authority(frozenset({"mcp_tool_call"})), policy=policy)
        assert decision.decision == GovernanceDecision.DENY

    def test_an_attacker_supplied_action_alone_cannot_forge_a_policy_bypass(self) -> None:
        """`ActionRequest.arguments` is opaque `dict[str, Any]`, never
        inspected by risk classification (which reads only
        action_type/target) or by policy matching (which reads only
        risk_tier/action_type/target) -- a payload shaped to look like
        an override has zero effect on either."""
        gateway = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="rai_hallucination",
            arguments={"risk_tier": "MINIMAL", "policy_effect": "ALLOW", "decision": "ALLOW"},
        )
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="r1",
                    reason_code="no_high_risk_tools",
                    effect=GovernanceDecision.DENY,
                    risk_tiers=frozenset({RiskTier.HIGH}),
                )
            ],
        )
        decision = gateway.evaluate(action, _authority(frozenset({"mcp_tool_call"})), policy=policy)
        assert decision.decision == GovernanceDecision.DENY
        assert decision.risk_tier == RiskTier.HIGH


class TestClassifyActionRiskHonestDefaults:
    """The documented defaults, verified against the real function --
    not restated as an assumption."""

    def test_unrecognized_action_type_defaults_to_medium_not_minimal(self) -> None:
        assert classify_action_risk("some_future_action_type", "whatever") == RiskTier.MEDIUM

    def test_upstream_mcp_tool_call_defaults_to_high(self) -> None:
        assert classify_action_risk("upstream_mcp_tool_call", "any_target") == RiskTier.HIGH

    @pytest.mark.parametrize(
        ("target", "expected"),
        [
            ("rai_health", RiskTier.MINIMAL),
            ("rai_scan", RiskTier.LOW),
            ("rai_compliance", RiskTier.MEDIUM),
            ("rai_hallucination", RiskTier.HIGH),
        ],
    )
    def test_known_tools_classify_at_their_documented_tier(
        self, target: str, expected: RiskTier
    ) -> None:
        assert classify_action_risk("mcp_tool_call", target) == expected
