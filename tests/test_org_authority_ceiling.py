"""Tests for `OrgAuthorityCeiling` (governance/ceiling.py) and
`OrgAuthorityCeilingRepository` (db/org_authority_ceiling_repository.py)
-- the structural, per-org authority ceiling enforced live on every
hosted MCP tool call via `parent_authority` (mcp/governance_integration.py).
"""

from __future__ import annotations

import pytest

from responsibleai.db import OrgAuthorityCeilingRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    OrgAuthorityCeiling,
    WhitePactRuntimeGateway,
    validate_attenuation,
)


class TestToAuthorityContext:
    def test_unrestricted_ceiling_grants_requested_action_type_only(self) -> None:
        ceiling = OrgAuthorityCeiling(org_id="org-1")
        authority = ceiling.to_authority_context("rai_scan")
        assert authority.granted_action_types == frozenset({"rai_scan"})
        assert authority.constraints == {}

    def test_max_value_usd_carried_into_constraints(self) -> None:
        ceiling = OrgAuthorityCeiling(org_id="org-1", max_value_usd=500_000)
        authority = ceiling.to_authority_context("payment.execute")
        assert authority.constraints["max_value_usd"] == 500_000

    def test_allowed_action_types_restricts_beyond_the_requested_call(self) -> None:
        ceiling = OrgAuthorityCeiling(
            org_id="org-1", allowed_action_types=["rai_scan", "rai_health"]
        )
        authority = ceiling.to_authority_context("rai_scan")
        assert authority.granted_action_types == frozenset({"rai_scan", "rai_health"})

    def test_delegated_by_names_the_ceiling(self) -> None:
        ceiling = OrgAuthorityCeiling(org_id="org-9")
        authority = ceiling.to_authority_context("x")
        assert authority.delegated_by == "org_ceiling:org-9"


class TestCeilingAsParentAuthority:
    """The actual invariant: a per-call authority checked against a
    ceiling via validate_attenuation()."""

    def test_within_ceiling_passes(self) -> None:
        ceiling = OrgAuthorityCeiling(org_id="org-1", max_value_usd=500_000)
        parent = ceiling.to_authority_context("payment.execute")
        child = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={"max_value_usd": 100_000},
        )
        assert validate_attenuation(parent, child) is None

    def test_exceeding_ceiling_denied(self) -> None:
        ceiling = OrgAuthorityCeiling(org_id="org-1", max_value_usd=500_000)
        parent = ceiling.to_authority_context("payment.execute")
        child = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={"max_value_usd": 1_000_000},
        )
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "max_value_usd" in reason

    def test_action_type_outside_allowlist_denied(self) -> None:
        ceiling = OrgAuthorityCeiling(org_id="org-1", allowed_action_types=["rai_scan"])
        parent = ceiling.to_authority_context("payment.execute")
        child = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"payment.execute"})
        )
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "granted_action_types" in reason


class TestGatewayWithCeiling:
    def test_gateway_denies_call_exceeding_org_ceiling(self) -> None:
        gw = WhitePactRuntimeGateway()
        ceiling = OrgAuthorityCeiling(org_id="org-1", max_value_usd=500_000)
        parent = ceiling.to_authority_context("mcp_tool_call")
        authority = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"mcp_tool_call"}),
            constraints={"max_value_usd": 2_000_000},
        )
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
        agent = AgentContext(identity=identity, framework="mcp-client")
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="payment_tool")

        result = gw.evaluate(action, authority, parent_authority=parent)
        assert result.decision == GovernanceDecision.DENY
        assert result.reason_codes[0].startswith("DELEGATION_AUTHORITY_ESCALATION")


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def ceiling_repo(engine):
    return OrgAuthorityCeilingRepository(engine)


class TestOrgAuthorityCeilingRepository:
    async def test_get_returns_none_when_unset(self, ceiling_repo) -> None:
        assert await ceiling_repo.get("org-1") is None

    async def test_set_and_get_round_trip(self, ceiling_repo) -> None:
        ceiling = OrgAuthorityCeiling(
            org_id="org-1",
            max_value_usd=500_000,
            allowed_targets=["payment_*"],
            denied_targets=["vendor_xyz"],
            max_delegation_depth=2,
            allowed_action_types=["payment.execute"],
            require_approval_for=frozenset({"payment.execute"}),
        )
        await ceiling_repo.set(ceiling)
        fetched = await ceiling_repo.get("org-1")
        assert fetched is not None
        assert fetched.max_value_usd == 500_000
        assert fetched.allowed_targets == ["payment_*"]
        assert fetched.denied_targets == ["vendor_xyz"]
        assert fetched.max_delegation_depth == 2
        assert fetched.allowed_action_types == ["payment.execute"]
        assert fetched.require_approval_for == frozenset({"payment.execute"})

    async def test_set_upserts_not_duplicates(self, ceiling_repo) -> None:
        await ceiling_repo.set(OrgAuthorityCeiling(org_id="org-1", max_value_usd=500_000))
        await ceiling_repo.set(OrgAuthorityCeiling(org_id="org-1", max_value_usd=100_000))
        fetched = await ceiling_repo.get("org-1")
        assert fetched is not None
        assert fetched.max_value_usd == 100_000

    async def test_orgs_are_isolated(self, ceiling_repo) -> None:
        await ceiling_repo.set(OrgAuthorityCeiling(org_id="org-1", max_value_usd=500_000))
        assert await ceiling_repo.get("org-2") is None

    async def test_delete_removes_row(self, ceiling_repo) -> None:
        await ceiling_repo.set(OrgAuthorityCeiling(org_id="org-1", max_value_usd=500_000))
        await ceiling_repo.delete("org-1")
        assert await ceiling_repo.get("org-1") is None

    async def test_unset_fields_round_trip_as_none(self, ceiling_repo) -> None:
        await ceiling_repo.set(OrgAuthorityCeiling(org_id="org-1"))
        fetched = await ceiling_repo.get("org-1")
        assert fetched is not None
        assert fetched.max_value_usd is None
        assert fetched.allowed_targets is None
        assert fetched.denied_targets is None
        assert fetched.max_delegation_depth is None
        assert fetched.allowed_action_types is None
        assert fetched.require_approval_for == frozenset()
