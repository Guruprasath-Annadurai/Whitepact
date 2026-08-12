"""Tests for delegation chains on AuthorityContext (v3 authority-layer
work, Task #143): "authority model remains coarse... no delegation
chains" from the gap reports. Deliberately NOT a transitive-permission
algebra (see governance/models.py's AuthorityContext docstring for why
that's out of scope) -- what's built: a validated, audited multi-hop
delegation path plus a single bounded-depth guard.
"""

from __future__ import annotations

import pytest

from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.evidence import build_evidence_record


def _agent(org_id: str = "org-1") -> AgentContext:
    identity = IdentityContext(identity_id="bot-service-42", kind="api_key", org_id=org_id)
    return AgentContext(identity=identity, framework="mcp-client")


def _action(target: str = "rai_health") -> ActionRequest:
    return ActionRequest(agent=_agent(), action_type="mcp_tool_call", target=target)


class TestDelegationChainValidation:
    def test_empty_chain_is_the_default_and_valid(self) -> None:
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"}))
        assert authority.delegation_chain == ()

    def test_chain_ending_in_delegated_by_is_valid(self) -> None:
        authority = AuthorityContext(
            delegated_by="bot-service-42",
            granted_action_types=frozenset({"mcp_tool_call"}),
            delegation_chain=("org-1", "alice", "bot-service-42"),
        )
        assert authority.delegation_chain == ("org-1", "alice", "bot-service-42")

    def test_chain_not_ending_in_delegated_by_raises(self) -> None:
        with pytest.raises(ValueError, match="delegated_by"):
            AuthorityContext(
                delegated_by="bot-service-42",
                granted_action_types=frozenset({"mcp_tool_call"}),
                delegation_chain=("org-1", "alice", "someone-else"),
            )


class TestMaxDelegationDepthConstraint:
    def test_chain_within_limit_passes(self) -> None:
        authority = AuthorityContext(
            delegated_by="bot-service-42",
            granted_action_types=frozenset({"mcp_tool_call"}),
            delegation_chain=("org-1", "bot-service-42"),
            constraints={"max_delegation_depth": 3},
        )
        assert authority.constraint_violation(_action()) is None

    def test_chain_exceeding_limit_denies(self) -> None:
        authority = AuthorityContext(
            delegated_by="bot-service-42",
            granted_action_types=frozenset({"mcp_tool_call"}),
            delegation_chain=("org-1", "alice", "bob", "carol", "bot-service-42"),
            constraints={"max_delegation_depth": 2},
        )
        violation = authority.constraint_violation(_action())
        assert violation is not None
        assert violation.startswith("ACTION_NOT_ALLOWED:")
        assert "max_delegation_depth" in violation

    def test_no_constraint_set_means_unlimited(self) -> None:
        authority = AuthorityContext(
            delegated_by="bot-service-42",
            granted_action_types=frozenset({"mcp_tool_call"}),
            delegation_chain=("a", "b", "c", "d", "e", "bot-service-42"),
        )
        assert authority.constraint_violation(_action()) is None

    def test_gateway_denies_over_depth_end_to_end(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="bot-service-42",
            granted_action_types=frozenset({"mcp_tool_call"}),
            delegation_chain=("org-1", "alice", "bob", "bot-service-42"),
            constraints={"max_delegation_depth": 1},
        )
        result = gw.evaluate(_action(), authority)
        assert result.decision == GovernanceDecision.DENY
        assert any("max_delegation_depth" in code for code in result.reason_codes)


class TestDelegationChainInEvidence:
    def test_chain_carried_through_to_evidence_record(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = AuthorityContext(
            delegated_by="bot-service-42",
            granted_action_types=frozenset({"mcp_tool_call"}),
            delegation_chain=("org-1", "alice", "bot-service-42"),
        )
        action = _action()
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, action.agent, authority, decision)
        assert evidence.delegation_chain == ["org-1", "alice", "bot-service-42"]
        assert evidence.to_dict()["delegation_chain"] == ["org-1", "alice", "bot-service-42"]

    def test_no_chain_set_means_empty_list_in_evidence(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"}))
        action = _action()
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, action.agent, authority, decision)
        assert evidence.delegation_chain == []
