"""Tests for `AuthorityContext.constraint_violation()` (v3 authority-layer
work, Task #136): the authority model's first real granularity beyond
action-type membership — value limits, target patterns, time windows.
See `governance/models.py`'s `AuthorityContext` docstring for the fixed,
recognized constraint keys.
"""

from __future__ import annotations

from datetime import UTC, datetime

from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)


def _identity() -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")


def _agent() -> AgentContext:
    return AgentContext(identity=_identity(), organization_id="org-1", framework="test")


def _action(target: str = "payment_tool", arguments: dict | None = None, proposed_at=None) -> ActionRequest:
    kwargs = {"agent": _agent(), "action_type": "mcp_tool_call", "target": target, "arguments": arguments or {}}
    if proposed_at is not None:
        kwargs["proposed_at"] = proposed_at
    return ActionRequest(**kwargs)


def _authority(**constraints) -> AuthorityContext:
    return AuthorityContext(
        delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"}), constraints=constraints,
    )


class TestValueLimit:
    def test_under_limit_passes(self) -> None:
        authority = _authority(max_value_usd=500)
        action = _action(arguments={"amount_usd": 100})
        assert authority.constraint_violation(action) is None

    def test_over_limit_denies(self) -> None:
        authority = _authority(max_value_usd=500)
        action = _action(arguments={"amount_usd": 501})
        violation = authority.constraint_violation(action)
        assert violation is not None
        assert violation.startswith("VALUE_LIMIT_EXCEEDED:")

    def test_no_value_argument_is_not_applicable(self) -> None:
        authority = _authority(max_value_usd=500)
        action = _action(arguments={"note": "no numeric amount here"})
        assert authority.constraint_violation(action) is None

    def test_first_recognized_key_wins(self) -> None:
        authority = _authority(max_value_usd=100)
        action = _action(arguments={"amount_usd": 50, "value_usd": 99999})
        assert authority.constraint_violation(action) is None

    def test_gateway_denies_over_limit_end_to_end(self) -> None:
        gw = WhitePactRuntimeGateway()
        authority = _authority(max_value_usd=1000)
        action = _action(arguments={"amount_usd": 5000})
        result = gw.evaluate(action, authority)
        assert result.decision == GovernanceDecision.DENY
        assert any(code.startswith("VALUE_LIMIT_EXCEEDED:") for code in result.reason_codes)


class TestTargetPatterns:
    def test_allowed_targets_permits_match(self) -> None:
        authority = _authority(allowed_targets=["payment_*"])
        action = _action(target="payment_stripe")
        assert authority.constraint_violation(action) is None

    def test_allowed_targets_denies_non_match(self) -> None:
        authority = _authority(allowed_targets=["payment_*"])
        action = _action(target="admin_delete_user")
        violation = authority.constraint_violation(action)
        assert violation is not None
        assert violation.startswith("TARGET_NOT_ALLOWED:")

    def test_denied_targets_denies_match_even_if_also_allowed(self) -> None:
        authority = _authority(allowed_targets=["*"], denied_targets=["payment_refund_*"])
        action = _action(target="payment_refund_stripe")
        violation = authority.constraint_violation(action)
        assert violation is not None
        assert violation.startswith("TARGET_NOT_ALLOWED:")
        assert "denied_targets" in violation

    def test_no_target_constraints_is_not_applicable(self) -> None:
        authority = _authority()
        action = _action(target="anything")
        assert authority.constraint_violation(action) is None


class TestTimeWindow:
    def test_inside_window_passes(self) -> None:
        authority = _authority(allowed_hours_utc=[9, 17])
        action = _action(proposed_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC))
        assert authority.constraint_violation(action) is None

    def test_outside_window_denies(self) -> None:
        authority = _authority(allowed_hours_utc=[9, 17])
        action = _action(proposed_at=datetime(2026, 8, 12, 23, 0, tzinfo=UTC))
        violation = authority.constraint_violation(action)
        assert violation is not None
        assert violation.startswith("ACTION_NOT_ALLOWED:")

    def test_overnight_window_wraps_midnight(self) -> None:
        authority = _authority(allowed_hours_utc=[22, 6])
        assert authority.constraint_violation(_action(proposed_at=datetime(2026, 8, 12, 23, 0, tzinfo=UTC))) is None
        assert authority.constraint_violation(_action(proposed_at=datetime(2026, 8, 12, 12, 0, tzinfo=UTC))) is not None


class TestMemoryScope:
    """Memory Authority / Memory Firewall (v3 authority-layer work):
    cross-tenant/cross-agent memory isolation via the `memory_scope`
    constraint."""

    def test_exact_scope_match_passes(self) -> None:
        authority = _authority(memory_scope="org:acme:agent:bot1")
        action = _action(arguments={"memory_scope": "org:acme:agent:bot1"})
        assert authority.constraint_violation(action) is None

    def test_nested_sub_scope_passes(self) -> None:
        authority = _authority(memory_scope="org:acme")
        action = _action(arguments={"memory_scope": "org:acme:agent:bot1"})
        assert authority.constraint_violation(action) is None

    def test_different_scope_denies(self) -> None:
        authority = _authority(memory_scope="org:acme:agent:bot1")
        action = _action(arguments={"memory_scope": "org:other-org:agent:bot2"})
        violation = authority.constraint_violation(action)
        assert violation is not None
        assert violation.startswith("MEMORY_SCOPE_VIOLATION:")

    def test_sibling_prefix_does_not_falsely_pass(self) -> None:
        """'org:acme2' must not be treated as a sub-scope of 'org:acme'
        -- startswith() alone (without the ':' separator check) would
        wrongly pass this."""
        authority = _authority(memory_scope="org:acme")
        action = _action(arguments={"memory_scope": "org:acme2:agent:bot1"})
        violation = authority.constraint_violation(action)
        assert violation is not None
        assert violation.startswith("MEMORY_SCOPE_VIOLATION:")

    def test_no_memory_scope_argument_is_not_applicable(self) -> None:
        authority = _authority(memory_scope="org:acme")
        action = _action(arguments={"note": "unrelated call"})
        assert authority.constraint_violation(action) is None

    def test_no_memory_scope_constraint_is_not_applicable(self) -> None:
        authority = _authority()
        action = _action(arguments={"memory_scope": "org:anything:at:all"})
        assert authority.constraint_violation(action) is None


class TestUnrecognizedConstraintKeyIgnored:
    def test_typo_key_does_not_block(self) -> None:
        authority = _authority(mx_value_usd=1)  # typo, not a recognized key
        action = _action(arguments={"amount_usd": 999999})
        assert authority.constraint_violation(action) is None


class TestConstraintOrderRelativeToOtherChecks:
    def test_constraint_denial_precedes_policy_and_content_scan(self) -> None:
        """A constraint violation is checked before Policy/content scan
        -- same "narrowest/cheapest check first" ordering the rest of
        evaluate() already follows."""
        gw = WhitePactRuntimeGateway()
        authority = _authority(max_value_usd=10)
        action = _action(arguments={"amount_usd": 999, "note": "contact me at a@b.com"})
        result = gw.evaluate(action, authority)
        assert result.decision == GovernanceDecision.DENY
        assert result.redacted_arguments is None
