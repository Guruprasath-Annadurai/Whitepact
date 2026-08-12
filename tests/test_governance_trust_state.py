"""Tests for AgentContext.trust_state population (governance/
trust_integration.py) and WhitePactRuntimeGateway's consultation of it —
closing the gap where the field existed but nothing populated or
consulted it.
"""

from __future__ import annotations

import httpx
import respx

from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
    enrich_agent_trust_state,
)
from responsibleai.governance.gateway import LOW_TRUST_SCORE_THRESHOLD
from responsibleai.integrations.client import TrustClient


def _identity() -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")


class TestEnrichAgentTrustState:
    async def test_noop_without_provider_and_model(self) -> None:
        agent = AgentContext(identity=_identity())
        client = TrustClient("https://api.test")
        result = await enrich_agent_trust_state(agent, client)
        assert result.trust_state is None

    @respx.mock
    async def test_populates_trust_state_when_provider_and_model_set(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "gpt-4o", "provider": "openai", "known": True,
                "trust_score": {"overall": 88.0}, "certified": True,
                "has_reported_incidents": False,
            })
        )
        agent = AgentContext(identity=_identity(), provider="openai", model="gpt-4o")
        client = TrustClient("https://api.test")
        result = await enrich_agent_trust_state(agent, client)
        assert result.trust_state is not None
        assert result.trust_state.known is True
        assert result.trust_state.overall_score == 88.0

    @respx.mock
    async def test_fails_open_on_network_error(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            side_effect=httpx.ConnectError("boom")
        )
        agent = AgentContext(identity=_identity(), provider="openai", model="gpt-4o")
        client = TrustClient("https://api.test")
        result = await enrich_agent_trust_state(agent, client)
        assert result.trust_state is not None
        assert result.trust_state.error is not None
        assert result.trust_state.known is False


class TestGatewayLowTrustDowngrade:
    def _gateway_authority(self) -> tuple[WhitePactRuntimeGateway, AuthorityContext]:
        return (
            WhitePactRuntimeGateway(),
            AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"rai_scan"})),
        )

    def test_no_trust_state_allows_normally(self) -> None:
        gateway, authority = self._gateway_authority()
        agent = AgentContext(identity=_identity())
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})
        result = gateway.evaluate(action, authority)
        assert result.decision == GovernanceDecision.ALLOW

    @respx.mock
    async def test_unknown_model_allows_normally(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "totally-obscure-model", "provider": "openai", "known": False,
                "trust_score": None, "certified": False, "has_reported_incidents": False,
            })
        )
        gateway, authority = self._gateway_authority()
        agent = AgentContext(identity=_identity(), provider="openai", model="totally-obscure-model")
        agent = await enrich_agent_trust_state(agent, TrustClient("https://api.test"))
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})
        result = gateway.evaluate(action, authority)
        assert result.decision == GovernanceDecision.ALLOW

    @respx.mock
    async def test_high_trust_score_allows_normally(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "gpt-4o", "provider": "openai", "known": True,
                "trust_score": {"overall": 90.0}, "certified": True, "has_reported_incidents": False,
            })
        )
        gateway, authority = self._gateway_authority()
        agent = AgentContext(identity=_identity(), provider="openai", model="gpt-4o")
        agent = await enrich_agent_trust_state(agent, TrustClient("https://api.test"))
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})
        result = gateway.evaluate(action, authority)
        assert result.decision == GovernanceDecision.ALLOW

    @respx.mock
    async def test_low_trust_score_downgrades_allow_to_require_approval(self) -> None:
        assert LOW_TRUST_SCORE_THRESHOLD == 40.0
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "sketchy-model", "provider": "unknown-vendor", "known": True,
                "trust_score": {"overall": 15.0}, "certified": False, "has_reported_incidents": True,
            })
        )
        gateway, authority = self._gateway_authority()
        agent = AgentContext(identity=_identity(), provider="unknown-vendor", model="sketchy-model")
        agent = await enrich_agent_trust_state(agent, TrustClient("https://api.test"))
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})
        result = gateway.evaluate(action, authority)
        assert result.decision == GovernanceDecision.REQUIRE_APPROVAL
        assert any(code.startswith("LOW_TRUST_SCORE:") for code in result.reason_codes)

    @respx.mock
    async def test_low_trust_does_not_override_pii_redaction(self) -> None:
        """Low trust escalates an ALLOW, but never overrides
        ALLOW_WITH_REDACTION/DENY — those already carry their own,
        higher-priority handling."""
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "sketchy-model", "provider": "unknown-vendor", "known": True,
                "trust_score": {"overall": 5.0}, "certified": False, "has_reported_incidents": True,
            })
        )
        gateway, authority = self._gateway_authority()
        agent = AgentContext(identity=_identity(), provider="unknown-vendor", model="sketchy-model")
        agent = await enrich_agent_trust_state(agent, TrustClient("https://api.test"))
        action = ActionRequest(
            agent=agent, action_type="rai_scan", target="rai_scan",
            arguments={"text": "Contact me at alice@example.com"},
        )
        result = gateway.evaluate(action, authority)
        assert result.decision == GovernanceDecision.ALLOW_WITH_REDACTION
