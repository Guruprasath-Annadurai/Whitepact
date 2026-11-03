"""SDK and local governance kernel functional tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from whitepact_community import (
    ActionRequest,
    AuthorityGrant,
    CommunityCapabilityUnavailable,
    GovernanceClient,
    GovernanceDecision,
    GovernanceDenied,
)
from whitepact_community.authorization import (
    authorize_execution,
    consume_authorization,
)
from whitepact_community.errors import AuthorizationError
from whitepact_community.revocation import LocalRevocationRegistry


def test_sdk_import_and_init() -> None:
    client = GovernanceClient.local()
    assert client.version
    assert client.api_compatibility == "community.v1"


def test_authorized_local_echo() -> None:
    client = GovernanceClient.local()
    action = ActionRequest(action_type="local_echo", target="local_echo", arguments={"text": "hi"})
    authority = AuthorityGrant(
        delegated_by="op",
        granted_action_types=frozenset({"local_echo"}),
        organization_id="local",
    )
    result = client.execute_local(action, authority)
    assert result["ok"] is True
    assert result["echo"] == "hi"
    assert result["decision"]["decision"] == "ALLOW"


def test_unauthorized_action_refused() -> None:
    client = GovernanceClient.local()
    action = ActionRequest(action_type="tenant_admin", target="tenant_admin")
    authority = AuthorityGrant(
        delegated_by="op",
        granted_action_types=frozenset({"local_echo"}),
        organization_id="local",
    )
    decision = client.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.DENY
    assert any(code.startswith("AUTHORITY_NOT_DELEGATED") for code in decision.reason_codes)
    with pytest.raises(GovernanceDenied):
        client.evaluate_or_raise(action, authority)


def test_expired_authority() -> None:
    client = GovernanceClient.local()
    action = ActionRequest(action_type="local_echo", target="local_echo", arguments={"text": "x"})
    authority = AuthorityGrant(
        delegated_by="op",
        granted_action_types=frozenset({"local_echo"}),
        organization_id="local",
        expires_at=datetime.now(UTC) - timedelta(seconds=5),
    )
    decision = client.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.DENY
    assert any(code.startswith("AUTHORITY_EXPIRED") for code in decision.reason_codes)


def test_revoked_authority() -> None:
    registry = LocalRevocationRegistry()
    client = GovernanceClient.local()
    client.kernel.revocation = registry
    registry.revoke("local", "authority")
    action = ActionRequest(action_type="local_echo", target="local_echo", arguments={"text": "x"})
    authority = AuthorityGrant(
        delegated_by="op",
        granted_action_types=frozenset({"local_echo"}),
        organization_id="local",
        revocation_epoch=0,
    )
    decision = client.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.DENY
    assert any(code.startswith("AUTHORITY_REVOKED") for code in decision.reason_codes)


def test_deny_by_default_unmatched_policy() -> None:
    client = GovernanceClient.local()
    action = ActionRequest(action_type="unknown_tool", target="unknown_tool")
    authority = AuthorityGrant(
        delegated_by="op",
        granted_action_types=frozenset({"unknown_tool"}),
        organization_id="local",
    )
    decision = client.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.DENY
    assert any(code.startswith("POLICY_DENY_BY_DEFAULT") for code in decision.reason_codes)


def test_replay_authorization_blocked() -> None:
    client = GovernanceClient.local()
    action = ActionRequest(action_type="local_echo", target="local_echo", arguments={"text": "once"})
    authority = AuthorityGrant(
        delegated_by="op",
        granted_action_types=frozenset({"local_echo"}),
        organization_id="local",
    )
    decision = client.evaluate(action, authority)
    auth = authorize_execution(action, decision)
    consume_authorization(auth, action)
    with pytest.raises(AuthorizationError):
        consume_authorization(auth, action)


def test_evidence_chain_consistent() -> None:
    client = GovernanceClient.local()
    for text in ("a", "b", "c"):
        action = ActionRequest(
            action_type="local_echo", target="local_echo", arguments={"text": text}
        )
        authority = AuthorityGrant(
            delegated_by="op",
            granted_action_types=frozenset({"local_echo"}),
            organization_id="local",
        )
        client.evaluate(action, authority)
    assert client.kernel.evidence.verify_chain() is True


def test_enterprise_capability_not_simulated() -> None:
    client = GovernanceClient.local()
    with pytest.raises(CommunityCapabilityUnavailable):
        client.enterprise_capability("stripe_checkout")
    with pytest.raises(CommunityCapabilityUnavailable):
        client.require_signed_cross_host_permit()


def test_value_limit_constraint() -> None:
    client = GovernanceClient.local()
    action = ActionRequest(
        action_type="governed_local_action",
        target="governed_local_action",
        arguments={"amount_usd": 500},
    )
    authority = AuthorityGrant(
        delegated_by="op",
        granted_action_types=frozenset({"governed_local_action"}),
        organization_id="local",
        constraints={"max_value_usd": 100},
    )
    decision = client.evaluate(action, authority)
    assert decision.decision == GovernanceDecision.DENY
    assert any(code.startswith("VALUE_LIMIT_EXCEEDED") for code in decision.reason_codes)
