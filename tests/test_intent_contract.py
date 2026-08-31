# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Intent Contract (Authority Everywhere Phase 4) --
`governance/intent.py`'s `IntentContract`/`intent_violation()`,
`WhitePactRuntimeGateway.evaluate()`'s new optional `intent` parameter,
and `db/intent_repository.py`'s `IntentContractRepository`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from responsibleai.db import IntentContractRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.intent import IntentContract, build_intent_contract


def _identity() -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")


def _agent() -> AgentContext:
    return AgentContext(identity=_identity(), organization_id="org-1", framework="test")


def _action(target: str = "payment_tool", arguments: dict | None = None) -> ActionRequest:
    return ActionRequest(
        agent=_agent(), action_type="mcp_tool_call", target=target, arguments=arguments or {}
    )


def _authority() -> AuthorityContext:
    return AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"}))


def _contract(**kwargs) -> IntentContract:
    return build_intent_contract("org-1", "k1", kwargs.pop("goal", "test task"), **kwargs)


class TestIsActive:
    def test_active_by_default(self) -> None:
        assert _contract().is_active() is True

    def test_not_yet_valid(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        contract = IntentContract(
            organization_id="org-1", agent_id="k1", goal="g", valid_from=future
        )
        assert contract.is_active() is False

    def test_expired(self) -> None:
        past = datetime.now(UTC) - timedelta(minutes=1)
        contract = _contract(expires_at=past)
        assert contract.is_active() is False

    def test_not_yet_expired(self) -> None:
        future = datetime.now(UTC) + timedelta(hours=1)
        contract = _contract(expires_at=future)
        assert contract.is_active() is True

    def test_no_expiry_stays_active(self) -> None:
        contract = _contract(expires_at=None)
        assert contract.is_active(datetime.now(UTC) + timedelta(days=365)) is True


class TestIntentViolation:
    def test_no_bounds_declared_never_violates(self) -> None:
        contract = _contract()
        assert contract.intent_violation(_action()) is None

    def test_denied_target_matched(self) -> None:
        contract = _contract(denied_targets=["payment_*"])
        violation = contract.intent_violation(_action(target="payment_tool"))
        assert violation is not None
        assert violation.startswith("INTENT_VIOLATED:")
        assert "denied_targets" in violation

    def test_denied_target_not_matched_passes(self) -> None:
        contract = _contract(denied_targets=["admin_*"])
        assert contract.intent_violation(_action(target="payment_tool")) is None

    def test_allowed_targets_excludes_others(self) -> None:
        contract = _contract(allowed_targets=["read_*"])
        violation = contract.intent_violation(_action(target="payment_tool"))
        assert violation is not None
        assert "allowed_targets" in violation

    def test_allowed_targets_includes_match(self) -> None:
        contract = _contract(allowed_targets=["payment_*"])
        assert contract.intent_violation(_action(target="payment_tool")) is None

    def test_denied_checked_before_allowed(self) -> None:
        contract = _contract(allowed_targets=["payment_*"], denied_targets=["payment_*"])
        violation = contract.intent_violation(_action(target="payment_tool"))
        assert violation is not None
        assert "denied_targets" in violation

    def test_allowed_action_types_excludes_others(self) -> None:
        contract = _contract(allowed_action_types=["api_call"])
        violation = contract.intent_violation(_action())
        assert violation is not None
        assert "allowed_action_types" in violation

    def test_allowed_action_types_includes_match(self) -> None:
        contract = _contract(allowed_action_types=["mcp_tool_call"])
        assert contract.intent_violation(_action()) is None

    def test_value_under_limit_passes(self) -> None:
        contract = _contract(max_value_usd=500)
        assert contract.intent_violation(_action(arguments={"amount_usd": 100})) is None

    def test_value_over_limit_denies(self) -> None:
        contract = _contract(max_value_usd=500)
        violation = contract.intent_violation(_action(arguments={"amount_usd": 501}))
        assert violation is not None
        assert "max_value_usd" in violation

    def test_no_value_argument_not_applicable(self) -> None:
        contract = _contract(max_value_usd=500)
        assert contract.intent_violation(_action(arguments={"note": "no amount"})) is None

    def test_to_dict_shape(self) -> None:
        contract = _contract(allowed_targets=["a"], max_value_usd=100.0)
        d = contract.to_dict()
        assert d["organization_id"] == "org-1"
        assert d["agent_id"] == "k1"
        assert d["goal"] == "test task"
        assert d["allowed_targets"] == ["a"]
        assert d["max_value_usd"] == 100.0
        assert d["denied_targets"] is None


class TestGatewayIntentParameter:
    def test_no_intent_supplied_behaves_as_before(self) -> None:
        gateway = WhitePactRuntimeGateway()
        decision = gateway.evaluate(_action(), _authority())
        assert decision.decision == GovernanceDecision.ALLOW

    def test_intent_within_bounds_allows(self) -> None:
        gateway = WhitePactRuntimeGateway()
        contract = _contract(max_value_usd=500)
        decision = gateway.evaluate(
            _action(arguments={"amount_usd": 100}), _authority(), intent=contract
        )
        assert decision.decision == GovernanceDecision.ALLOW

    def test_intent_violation_denies(self) -> None:
        gateway = WhitePactRuntimeGateway()
        contract = _contract(denied_targets=["payment_*"])
        decision = gateway.evaluate(_action(target="payment_tool"), _authority(), intent=contract)
        assert decision.decision == GovernanceDecision.DENY
        assert any(r.startswith("INTENT_VIOLATED:") for r in decision.reason_codes)

    def test_intent_checked_before_authority_permits(self) -> None:
        """An intent violation on an action type the authority doesn't
        even grant still reports INTENT_VIOLATED, not
        AUTHORITY_NOT_DELEGATED -- proving the intent check runs first,
        per the gateway's own documented ordering."""
        gateway = WhitePactRuntimeGateway()
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset())
        contract = _contract(denied_targets=["payment_*"])
        decision = gateway.evaluate(_action(target="payment_tool"), authority, intent=contract)
        assert decision.decision == GovernanceDecision.DENY
        assert any(r.startswith("INTENT_VIOLATED:") for r in decision.reason_codes)


class TestIntentContractRepository:
    async def _engine(self):
        engine = create_engine(":memory:")
        await engine.init()
        return engine

    async def test_declare_and_get(self) -> None:
        engine = await self._engine()
        try:
            repo = IntentContractRepository(engine)
            contract = _contract(goal="deploy service")
            await repo.declare(contract)
            fetched = await repo.get(contract.contract_id)
            assert fetched is not None
            assert fetched.goal == "deploy service"
            assert fetched.agent_id == "k1"
        finally:
            await engine.close()

    async def test_get_active_for_agent_latest_wins(self) -> None:
        engine = await self._engine()
        try:
            repo = IntentContractRepository(engine)
            older = _contract(goal="first task")
            await repo.declare(older)
            newer = build_intent_contract("org-1", "k1", "second task")
            await repo.declare(newer)
            active = await repo.get_active_for_agent("org-1", "k1")
            assert active is not None
            assert active.goal == "second task"
        finally:
            await engine.close()

    async def test_expired_contract_not_returned_as_active(self) -> None:
        engine = await self._engine()
        try:
            repo = IntentContractRepository(engine)
            past = datetime.now(UTC) - timedelta(minutes=1)
            contract = _contract(expires_at=past)
            await repo.declare(contract)
            active = await repo.get_active_for_agent("org-1", "k1")
            assert active is None
        finally:
            await engine.close()

    async def test_no_contract_returns_none(self) -> None:
        engine = await self._engine()
        try:
            repo = IntentContractRepository(engine)
            active = await repo.get_active_for_agent("org-1", "unknown-agent")
            assert active is None
        finally:
            await engine.close()

    async def test_get_unknown_id_returns_none(self) -> None:
        engine = await self._engine()
        try:
            repo = IntentContractRepository(engine)
            assert await repo.get("does-not-exist") is None
        finally:
            await engine.close()
