"""Tests for `validate_attenuation()` — the authority-attenuation
invariant: a delegated `AuthorityContext` must never grant more than
the `AuthorityContext` that delegated it held. See `governance/models.py`
for exactly what is and is not checked.
"""

from __future__ import annotations

from responsibleai.governance import AuthorityContext, ReasonCode, validate_attenuation


def _authority(
    action_types: frozenset[str] = frozenset({"payment.execute"}),
    require_approval_for: frozenset[str] = frozenset(),
    **constraints: object,
) -> AuthorityContext:
    return AuthorityContext(
        delegated_by="org-1",
        granted_action_types=action_types,
        constraints=constraints,
        require_approval_for=require_approval_for,
    )


class TestNarrowerOrEqualPasses:
    def test_identical_authority_passes(self) -> None:
        parent = _authority(max_value_usd=500_000)
        child = _authority(max_value_usd=500_000)
        assert validate_attenuation(parent, child) is None

    def test_narrower_value_limit_passes(self) -> None:
        parent = _authority(max_value_usd=500_000)
        child = _authority(max_value_usd=100_000)
        assert validate_attenuation(parent, child) is None

    def test_narrower_action_types_passes(self) -> None:
        parent = _authority(action_types=frozenset({"payment.execute", "beneficiary.create"}))
        child = _authority(action_types=frozenset({"payment.execute"}))
        assert validate_attenuation(parent, child) is None

    def test_parent_unconstrained_child_constrained_passes(self) -> None:
        parent = _authority()
        child = _authority(max_value_usd=100_000)
        assert validate_attenuation(parent, child) is None

    def test_added_denied_target_passes(self) -> None:
        parent = _authority(denied_targets=["vendor_xyz"])
        child = _authority(denied_targets=["vendor_xyz", "vendor_abc"])
        assert validate_attenuation(parent, child) is None


class TestActionTypeEscalation:
    def test_expanded_action_types_denied(self) -> None:
        parent = _authority(action_types=frozenset({"payment.execute"}))
        child = _authority(action_types=frozenset({"payment.execute", "beneficiary.create"}))
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert reason.startswith(ReasonCode.DELEGATION_AUTHORITY_ESCALATION.value)
        assert "granted_action_types" in reason
        assert "beneficiary.create" in reason


class TestValueLimitEscalation:
    def test_flagship_demo_scenario(self) -> None:
        """Human gives Agent A Rs 500,000 authority. Agent A delegates
        Rs 100,000 to Agent B. Agent B's authority requests Rs 1,000,000
        — denied, escalation."""
        agent_a = _authority(max_value_usd=500_000)
        agent_b_delegated = _authority(max_value_usd=100_000)
        agent_b_requested = _authority(max_value_usd=1_000_000)

        assert validate_attenuation(agent_a, agent_b_delegated) is None
        reason = validate_attenuation(agent_a, agent_b_requested)
        assert reason is not None
        assert "max_value_usd" in reason
        assert "parent_limit=500000" in reason
        assert "child_limit=1000000" in reason

    def test_child_unset_where_parent_limited_denied(self) -> None:
        parent = _authority(max_value_usd=500_000)
        child = _authority()  # no limit at all -- broader than parent
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "max_value_usd" in reason


class TestDeniedTargetsEscalation:
    def test_lifted_denial_denied(self) -> None:
        parent = _authority(denied_targets=["vendor_xyz"])
        child = _authority(denied_targets=[])
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "denied_targets" in reason
        assert "vendor_xyz" in reason


class TestAllowedTargetsEscalation:
    def test_child_unset_where_parent_restricted_denied(self) -> None:
        parent = _authority(allowed_targets=["payment_*"])
        child = _authority()
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "allowed_targets" in reason

    def test_child_pattern_not_in_parent_list_denied(self) -> None:
        parent = _authority(allowed_targets=["payment_domestic"])
        child = _authority(allowed_targets=["payment_domestic", "payment_international"])
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "allowed_targets" in reason

    def test_child_subset_of_parent_list_passes(self) -> None:
        parent = _authority(allowed_targets=["payment_domestic", "payment_international"])
        child = _authority(allowed_targets=["payment_domestic"])
        assert validate_attenuation(parent, child) is None


class TestMaxDelegationDepthEscalation:
    def test_child_unset_where_parent_set_denied(self) -> None:
        parent = _authority(max_delegation_depth=2)
        child = _authority()
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "max_delegation_depth" in reason

    def test_child_deeper_than_parent_denied(self) -> None:
        parent = _authority(max_delegation_depth=2)
        child = _authority(max_delegation_depth=3)
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "max_delegation_depth" in reason

    def test_child_shallower_passes(self) -> None:
        parent = _authority(max_delegation_depth=3)
        child = _authority(max_delegation_depth=1)
        assert validate_attenuation(parent, child) is None


class TestApprovalRequirementEscalation:
    def test_dropped_approval_requirement_denied(self) -> None:
        parent = _authority(
            action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset({"payment.execute"}),
        )
        child = _authority(
            action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset(),
        )
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "require_approval_for" in reason
        assert "payment.execute" in reason

    def test_kept_approval_requirement_passes(self) -> None:
        parent = _authority(
            action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset({"payment.execute"}),
        )
        child = _authority(
            action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset({"payment.execute"}),
        )
        assert validate_attenuation(parent, child) is None

    def test_approval_requirement_for_action_child_lacks_is_irrelevant(self) -> None:
        """Parent required approval for beneficiary.create, but the child
        was never granted that action type at all -- nothing to drop."""
        parent = _authority(
            action_types=frozenset({"payment.execute", "beneficiary.create"}),
            require_approval_for=frozenset({"beneficiary.create"}),
        )
        child = _authority(
            action_types=frozenset({"payment.execute"}),
            require_approval_for=frozenset(),
        )
        assert validate_attenuation(parent, child) is None


class TestAllowedHoursUtcEscalation:
    """Heart Phase H2: closes a documented gap this function's own
    docstring used to name -- `allowed_hours_utc` was never
    attenuation-checked before. See `governance/authority_lattice.py`
    for the general-purpose lattice this same logic also backs."""

    def test_narrower_window_passes(self) -> None:
        parent = _authority(allowed_hours_utc=(22, 6))
        child = _authority(allowed_hours_utc=(23, 5))
        assert validate_attenuation(parent, child) is None

    def test_identical_window_passes(self) -> None:
        parent = _authority(allowed_hours_utc=(9, 17))
        child = _authority(allowed_hours_utc=(9, 17))
        assert validate_attenuation(parent, child) is None

    def test_wider_wraparound_window_denied(self) -> None:
        """The exact real-world scenario this gap allowed: a parent
        restricted to 22:00-06:00 delegating a child that claims
        20:00-06:00 -- two extra hours (20, 21) the parent never held."""
        parent = _authority(allowed_hours_utc=(22, 6))
        child = _authority(allowed_hours_utc=(20, 6))
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert reason.startswith("DELEGATION_AUTHORITY_ESCALATION")
        assert "allowed_hours_utc" in reason

    def test_unset_child_window_denied_when_parent_constrains(self) -> None:
        parent = _authority(allowed_hours_utc=(9, 17))
        child = _authority()
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert "allowed_hours_utc" in reason

    def test_unconstrained_parent_lets_child_set_anything(self) -> None:
        parent = _authority()
        child = _authority(allowed_hours_utc=(0, 23))
        assert validate_attenuation(parent, child) is None


class TestMethodWrapper:
    def test_validate_delegation_to_matches_function(self) -> None:
        parent = _authority(max_value_usd=500_000)
        child = _authority(max_value_usd=1_000_000)
        assert parent.validate_delegation_to(child) == validate_attenuation(parent, child)
