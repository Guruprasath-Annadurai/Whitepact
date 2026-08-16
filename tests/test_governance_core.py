"""Tests for the WhitePact runtime governance core (SPEC.md Section 2-3,
MIGRATION_WHITEPACT_V2.md Phase 8): the core entities in
`governance/models.py` and `WhitePactRuntimeGateway.evaluate()`'s
deterministic decision logic.
"""

from __future__ import annotations

from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
    Policy,
    PolicyRule,
    RiskTier,
    WhitePactRuntimeGateway,
)
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.rbac.models import OrgContext, Plan, Role


class TestGovernanceDecisionEnum:
    def test_five_members(self) -> None:
        assert {d.value for d in GovernanceDecision} == {
            "ALLOW",
            "ALLOW_WITH_REDACTION",
            "REQUIRE_APPROVAL",
            "DENY",
            "QUARANTINE",
        }


class TestIdentityContext:
    def test_from_org_context_api_key(self) -> None:
        ctx = OrgContext(key_id="key-1", role=Role.ANALYST, org_id="org-1", plan=Plan.PRO)
        identity = IdentityContext.from_org_context(ctx)
        assert identity.identity_id == "key-1"
        assert identity.kind == "api_key"
        assert identity.org_id == "org-1"
        assert identity.org_context is ctx

    def test_from_org_context_oidc(self) -> None:
        ctx = OrgContext(key_id="oidc:user-1", role=Role.VIEWER, org_id="org-2")
        identity = IdentityContext.from_org_context(ctx)
        assert identity.kind == "oidc"


class TestAgentContext:
    def test_organization_id_defaults_from_identity(self) -> None:
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-9")
        agent = AgentContext(identity=identity)
        assert agent.organization_id == "org-9"

    def test_explicit_organization_id_not_overridden(self) -> None:
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-9")
        agent = AgentContext(identity=identity, organization_id="org-override")
        assert agent.organization_id == "org-override"

    def test_agent_id_is_generated_and_unique(self) -> None:
        identity = IdentityContext(identity_id="k1", kind="api_key")
        a1 = AgentContext(identity=identity)
        a2 = AgentContext(identity=identity)
        assert a1.agent_id != a2.agent_id


class TestActionRequest:
    def test_action_id_generated_and_unique(self) -> None:
        identity = IdentityContext(identity_id="k1", kind="api_key")
        agent = AgentContext(identity=identity)
        r1 = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        r2 = ActionRequest(agent=agent, action_type="mcp_tool_call", target="rai_health")
        assert r1.action_id != r2.action_id


class TestAuthorityContext:
    def test_permits_granted_action(self) -> None:
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"})
        )
        assert authority.permits("mcp_tool_call") is True
        assert authority.permits("payment") is False


def _agent(org_id: str = "org-1") -> AgentContext:
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)
    return AgentContext(identity=identity, framework="mcp-client")


def _authority(**kwargs) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"mcp_tool_call"}))
    return AuthorityContext(**kwargs)


class TestGatewayAuthority:
    def test_denies_ungranted_action_type(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(), action_type="payment", target="stripe")
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.DENY
        assert result.reason_codes == ["AUTHORITY_NOT_DELEGATED:action_type=payment"]

    def test_allows_granted_action_with_clean_arguments(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="rai_health",
            arguments={"query": "hello world"},
        )
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.ALLOW
        assert result.reason_codes == []
        assert result.redacted_arguments is None

    def test_non_string_arguments_pass_through_unscanned(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"count": 5, "enabled": True, "tags": ["a", "b"]},
        )
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.ALLOW


class TestGatewayAttenuation:
    """Wiring for `validate_attenuation()` (governance/models.py) into
    `WhitePactRuntimeGateway.evaluate()` — see gateway.py's module
    docstring, step 0."""

    def test_no_parent_authority_unaffected(self) -> None:
        """Every caller not passing `parent_authority` behaves exactly
        as before this wiring existed."""
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.ALLOW

    def test_attenuated_child_proceeds_normally(self) -> None:
        gw = WhitePactRuntimeGateway()
        parent = _authority(constraints={"max_value_usd": 500_000})
        child = _authority(constraints={"max_value_usd": 100_000})
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")
        result = gw.evaluate(action, child, parent_authority=parent)
        assert result.decision == GovernanceDecision.ALLOW

    def test_flagship_demo_scenario_denied_at_gateway(self) -> None:
        """Agent A holds Rs 500,000 authority. Agent B's authority
        requests Rs 1,000,000 -- the gateway denies before even checking
        whether the action type itself is granted."""
        gw = WhitePactRuntimeGateway()
        agent_a_authority = _authority(constraints={"max_value_usd": 500_000})
        agent_b_authority = _authority(constraints={"max_value_usd": 1_000_000})
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="payment_tool")

        result = gw.evaluate(action, agent_b_authority, parent_authority=agent_a_authority)

        assert result.decision == GovernanceDecision.DENY
        assert len(result.reason_codes) == 1
        assert result.reason_codes[0].startswith("DELEGATION_AUTHORITY_ESCALATION")
        assert "max_value_usd" in result.reason_codes[0]

    def test_escalation_checked_before_quarantine(self) -> None:
        """Quarantine (recent_violation_count) still wins even when an
        escalation is also present -- quarantine is step 0 in the
        gateway's own numbering, attenuation is the new step immediately
        after it, so quarantine must still short-circuit first."""
        gw = WhitePactRuntimeGateway()
        from responsibleai.governance.quarantine import QUARANTINE_VIOLATION_THRESHOLD

        parent = _authority(constraints={"max_value_usd": 500_000})
        child = _authority(constraints={"max_value_usd": 1_000_000})
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")

        result = gw.evaluate(
            action,
            child,
            parent_authority=parent,
            recent_violation_count=QUARANTINE_VIOLATION_THRESHOLD,
        )
        assert result.decision == GovernanceDecision.QUARANTINE

    def test_escalation_checked_before_action_type_grant(self) -> None:
        """An escalated child authority is denied for the escalation even
        when it also wasn't granted the action type at all -- the
        attenuation check runs first, so that's the reason surfaced."""
        gw = WhitePactRuntimeGateway()
        parent = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        child = _authority(granted_action_types=frozenset({"mcp_tool_call", "payment.execute"}))
        action = ActionRequest(agent=_agent(), action_type="payment.execute", target="x")

        result = gw.evaluate(action, child, parent_authority=parent)

        assert result.decision == GovernanceDecision.DENY
        assert result.reason_codes[0].startswith("DELEGATION_AUTHORITY_ESCALATION")


class TestGatewayApprovalTrigger:
    def test_require_approval_action_type_short_circuits_before_scan(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(
            granted_action_types=frozenset({"deployment"}),
            require_approval_for=frozenset({"deployment"}),
        )
        action = ActionRequest(agent=_agent(), action_type="deployment", target="prod")
        result = gw.evaluate(action, authority)
        assert result.decision == GovernanceDecision.REQUIRE_APPROVAL
        assert result.reason_codes == ["APPROVAL_REQUIRED:action_type=deployment"]

    def test_authority_check_still_wins_over_approval_list(self) -> None:
        """An action_type in require_approval_for but NOT in
        granted_action_types is still denied outright -- approval is for
        actions the agent is otherwise allowed to attempt."""
        gw = WhitePactRuntimeGateway()
        authority = _authority(
            granted_action_types=frozenset({"mcp_tool_call"}),
            require_approval_for=frozenset({"deployment"}),
        )
        action = ActionRequest(agent=_agent(), action_type="deployment", target="prod")
        result = gw.evaluate(action, authority)
        assert result.decision == GovernanceDecision.DENY


class TestGatewayContentScan:
    def test_pii_triggers_redaction_not_denial(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"note": "contact me at test@example.com"},
        )
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.ALLOW_WITH_REDACTION
        assert result.redacted_arguments is not None
        assert "test@example.com" not in result.redacted_arguments["note"]
        assert "[REDACTED]" in result.redacted_arguments["note"]

    def test_non_pii_fields_untouched_by_redaction(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"note": "email me at a@b.com", "label": "unrelated text"},
        )
        result = gw.evaluate(action, _authority())
        assert result.redacted_arguments is not None
        assert result.redacted_arguments["label"] == "unrelated text"

    def test_toxicity_hard_denies_even_with_pii_present(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"note": "I will kill you, contact me at a@b.com"},
        )
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.DENY
        assert result.redacted_arguments is None

    def test_reason_codes_are_field_qualified(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"contact": "reach me at a@b.com"},
        )
        result = gw.evaluate(action, _authority())
        assert result.reason_codes == ["REDACTION_REQUIRED:field=contact"]


class TestDecisionResultSerialization:
    def test_to_dict_shape(self) -> None:
        result = DecisionResult(decision=GovernanceDecision.ALLOW, action_id="a1")
        d = result.to_dict()
        assert d["decision"] == "ALLOW"
        assert d["action_id"] == "a1"
        assert isinstance(d["evaluated_at"], str)
        assert d["risk_tier"] is None

    def test_to_dict_includes_risk_tier_value(self) -> None:
        result = DecisionResult(
            decision=GovernanceDecision.ALLOW, action_id="a1", risk_tier=RiskTier.HIGH
        )
        assert result.to_dict()["risk_tier"] == "HIGH"


class TestGatewayRiskClassification:
    """Phase 9 wiring: risk_tier is always populated once the gateway
    reaches the content-scan stage, whether or not a Policy is supplied."""

    def test_risk_tier_populated_without_a_policy(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="rai_hallucination"
        )
        result = gw.evaluate(action, authority)
        assert result.risk_tier == RiskTier.HIGH

    def test_risk_tier_populated_on_authority_denial(self) -> None:
        """Risk is now classified before the authority check (the
        quarantine short-circuit needs a risk_tier to attach to its own
        result, so classification moved ahead of every other check) --
        a denied action's evidence still records what risk tier it
        would have been, which is more useful than None, not less."""
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(), action_type="payment", target="stripe")
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.DENY
        assert result.risk_tier is not None

    def test_minimal_risk_tool_still_allows_normally(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="rai_health")
        result = gw.evaluate(action, authority)
        assert result.decision == GovernanceDecision.ALLOW
        assert result.risk_tier == RiskTier.MINIMAL


class TestFastPathSkipsGuardrailsForArgumentFreeActions:
    """Locks in the claim gateway.py's module docstring makes about the
    v3 risk-router investigation (Task #141): an action with zero
    string-valued arguments already never invokes GuardrailsEngine at
    all, regardless of risk tier -- no risk-tier-gated skip needed to
    get this, and this test proves it stays true rather than just
    being asserted in prose."""

    def test_no_string_arguments_never_calls_guardrails_scan(self) -> None:
        from unittest.mock import MagicMock

        spy_guardrails = MagicMock(wraps=GuardrailsEngine())
        gw = WhitePactRuntimeGateway(guardrails=spy_guardrails)
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="rai_health",
            arguments={"count": 5, "enabled": True},
        )
        result = gw.evaluate(action, authority)
        assert result.decision == GovernanceDecision.ALLOW
        spy_guardrails.scan.assert_not_called()

    def test_a_string_argument_does_invoke_guardrails_scan(self) -> None:
        """Contrast case: the moment there IS a string argument, the
        scan still runs -- this isn't a risk-tier skip, it's a
        genuinely-nothing-to-scan skip."""
        from unittest.mock import MagicMock

        spy_guardrails = MagicMock(wraps=GuardrailsEngine())
        gw = WhitePactRuntimeGateway(guardrails=spy_guardrails)
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="rai_health",
            arguments={"note": "hello"},
        )
        gw.evaluate(action, authority)
        spy_guardrails.scan.assert_called_once_with("hello")


class TestGatewayPolicyIntegration:
    """Phase 10 wiring: an optional Policy evaluated after risk
    classification, before the content scan."""

    def test_no_policy_behaves_exactly_as_phase_8(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="rai_scan", arguments={}
        )
        result = gw.evaluate(action, authority, policy=None)
        assert result.decision == GovernanceDecision.ALLOW
        assert result.reason_codes == []

    def test_policy_deny_short_circuits_before_content_scan(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="no-high-risk",
                    reason_code="high_risk_blocked",
                    effect=GovernanceDecision.DENY,
                    risk_tiers=frozenset({RiskTier.HIGH}),
                ),
            ],
        )
        # Clean arguments -- would otherwise ALLOW; policy must be what denies it.
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="rai_hallucination",
            arguments={"text": "nothing objectionable here"},
        )
        result = gw.evaluate(action, authority, policy)
        assert result.decision == GovernanceDecision.DENY
        assert result.reason_codes == [
            "POLICY_EXPLICIT_DENY:rule_id=no-high-risk;rule_reason=high_risk_blocked"
        ]
        assert result.risk_tier == RiskTier.HIGH

    def test_policy_require_approval_short_circuits(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="writes-need-approval",
                    reason_code="write_action",
                    effect=GovernanceDecision.REQUIRE_APPROVAL,
                    targets=frozenset({"rai_incident_log"}),
                ),
            ],
        )
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="rai_incident_log"
        )
        result = gw.evaluate(action, authority, policy)
        assert result.decision == GovernanceDecision.REQUIRE_APPROVAL
        assert result.reason_codes == [
            "POLICY_REQUIRES_APPROVAL:rule_id=writes-need-approval;rule_reason=write_action",
        ]

    def test_policy_allow_does_not_skip_content_scan(self) -> None:
        """An explicit ALLOW policy match still goes through
        GuardrailsEngine -- defense in depth."""
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="allow-low", reason_code="low_risk_ok", effect=GovernanceDecision.ALLOW
                ),
            ],
        )
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="rai_scan",
            arguments={"text": "contact me at a@b.com"},
        )
        result = gw.evaluate(action, authority, policy)
        assert result.decision == GovernanceDecision.ALLOW_WITH_REDACTION
        assert "policy_allow:rule_id=allow-low;rule_reason=low_risk_ok" in result.reason_codes
        assert any(code.startswith("REDACTION_REQUIRED:") for code in result.reason_codes)

    def test_policy_allow_reason_present_on_clean_final_allow(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="allow-low", reason_code="low_risk_ok", effect=GovernanceDecision.ALLOW
                ),
            ],
        )
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="rai_scan", arguments={}
        )
        result = gw.evaluate(action, authority, policy)
        assert result.decision == GovernanceDecision.ALLOW
        assert result.reason_codes == ["policy_allow:rule_id=allow-low;rule_reason=low_risk_ok"]

    def test_no_matching_policy_rule_falls_through_to_scan(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(granted_action_types=frozenset({"mcp_tool_call"}))
        policy = Policy(
            org_id="org-1",
            rules=[
                PolicyRule(
                    rule_id="critical-only",
                    reason_code="x",
                    effect=GovernanceDecision.DENY,
                    targets=frozenset({"nonexistent_tool"}),
                ),
            ],
        )
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="rai_scan", arguments={}
        )
        result = gw.evaluate(action, authority, policy)
        assert result.decision == GovernanceDecision.ALLOW
        assert result.reason_codes == []
