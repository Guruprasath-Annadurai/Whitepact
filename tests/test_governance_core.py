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
    WhitePactRuntimeGateway,
)
from responsibleai.rbac.models import OrgContext, Plan, Role


class TestGovernanceDecisionEnum:
    def test_five_members(self) -> None:
        assert {d.value for d in GovernanceDecision} == {
            "ALLOW", "ALLOW_WITH_REDACTION", "REQUIRE_APPROVAL", "DENY", "QUARANTINE",
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
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"}))
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
        assert result.reason_codes == ["authority_not_granted:payment"]

    def test_allows_granted_action_with_clean_arguments(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="rai_health",
            arguments={"query": "hello world"},
        )
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.ALLOW
        assert result.reason_codes == []
        assert result.redacted_arguments is None

    def test_non_string_arguments_pass_through_unscanned(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="x",
            arguments={"count": 5, "enabled": True, "tags": ["a", "b"]},
        )
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.ALLOW


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
        assert result.reason_codes == ["approval_required:deployment"]

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
            agent=_agent(), action_type="mcp_tool_call", target="x",
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
            agent=_agent(), action_type="mcp_tool_call", target="x",
            arguments={"note": "email me at a@b.com", "label": "unrelated text"},
        )
        result = gw.evaluate(action, _authority())
        assert result.redacted_arguments is not None
        assert result.redacted_arguments["label"] == "unrelated text"

    def test_toxicity_hard_denies_even_with_pii_present(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="x",
            arguments={"note": "I will kill you, contact me at a@b.com"},
        )
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.DENY
        assert result.redacted_arguments is None

    def test_reason_codes_are_field_qualified(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="x",
            arguments={"contact": "reach me at a@b.com"},
        )
        result = gw.evaluate(action, _authority())
        assert result.reason_codes == ["contact:pii_redacted"]


class TestDecisionResultSerialization:
    def test_to_dict_shape(self) -> None:
        result = DecisionResult(decision=GovernanceDecision.ALLOW, action_id="a1")
        d = result.to_dict()
        assert d["decision"] == "ALLOW"
        assert d["action_id"] == "a1"
        assert isinstance(d["evaluated_at"], str)
