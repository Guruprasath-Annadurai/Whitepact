# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Property-based tests (Hypothesis) for the pure, invariant-heavy
governance functions -- a complement to, not a replacement for, the
hand-picked example tests in test_authority_attenuation.py,
test_authority_constraints.py, test_workflow_authority.py, and
test_memory_firewall.py. Those prove specific documented scenarios;
these prove the invariant holds across the input space, not just the
examples someone thought to write down.

**Deliberately scoped to pure, synchronous functions.** Hypothesis
shines on exactly that shape (arbitrary input in, deterministic
output, no I/O). Property-testing the async, DB-backed paths
(Evidence Bundle tamper detection, delegation-graph attenuation at
grant time) would mean generating examples through an async DB
fixture per Hypothesis example, a much heavier integration than the
pure-function properties below -- and that ground is already covered
by test_evidence_bundle.py's five explicit tamper scenarios. Not
attempted here; noted rather than silently skipped.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import assume, given
from hypothesis import strategies as st

from responsibleai.governance.memory_firewall import scan_memory_write
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
    validate_attenuation,
)
from responsibleai.governance.workflow import (
    TimestampedAction,
    WorkflowSequenceRule,
    check_composition_violation,
)

_action_type = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd")), min_size=1, max_size=12
)


def _agent() -> AgentContext:
    identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
    return AgentContext(identity=identity, framework="test")


def _authority(**kwargs) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"mcp_tool_call"}))
    return AuthorityContext(**kwargs)


class TestAttenuationProperties:
    @given(
        parent_types=st.sets(_action_type, min_size=0, max_size=8),
        subset_fraction=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_child_action_types_subset_of_parent_never_escalates(
        self, parent_types: set[str], subset_fraction: float
    ) -> None:
        parent = _authority(granted_action_types=frozenset(parent_types))
        # A genuine subset -- take however many elements subset_fraction implies.
        parent_list = sorted(parent_types)
        cut = round(len(parent_list) * subset_fraction)
        child_types = frozenset(parent_list[:cut])
        child = _authority(granted_action_types=child_types)
        assert validate_attenuation(parent, child) is None

    @given(
        parent_types=st.sets(_action_type, min_size=0, max_size=8),
        extra=_action_type,
    )
    def test_child_action_type_outside_parent_always_escalates(
        self, parent_types: set[str], extra: str
    ) -> None:
        assume(extra not in parent_types)
        parent = _authority(granted_action_types=frozenset(parent_types))
        child = _authority(granted_action_types=frozenset({*parent_types, extra}))
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert reason.startswith("DELEGATION_AUTHORITY_ESCALATION")

    @given(
        parent_limit=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
        child_limit=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
    )
    def test_max_value_usd_narrowing_or_equal_never_escalates(
        self, parent_limit: float, child_limit: float
    ) -> None:
        assume(child_limit <= parent_limit)
        shared_types = frozenset({"payment.execute"})
        parent = _authority(
            granted_action_types=shared_types, constraints={"max_value_usd": parent_limit}
        )
        child = _authority(
            granted_action_types=shared_types, constraints={"max_value_usd": child_limit}
        )
        assert validate_attenuation(parent, child) is None

    @given(
        parent_limit=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
        widening=st.floats(min_value=0.01, max_value=1_000_000.0, allow_nan=False),
    )
    def test_max_value_usd_widening_always_escalates(
        self, parent_limit: float, widening: float
    ) -> None:
        child_limit = parent_limit + widening
        shared_types = frozenset({"payment.execute"})
        parent = _authority(
            granted_action_types=shared_types, constraints={"max_value_usd": parent_limit}
        )
        child = _authority(
            granted_action_types=shared_types, constraints={"max_value_usd": child_limit}
        )
        reason = validate_attenuation(parent, child)
        assert reason is not None
        assert reason.startswith("DELEGATION_AUTHORITY_ESCALATION")


class TestConstraintViolationProperties:
    @given(
        limit=st.floats(min_value=0.0, max_value=1_000_000.0, allow_nan=False),
        amount=st.floats(min_value=0.0, max_value=2_000_000.0, allow_nan=False),
    )
    def test_value_limit_violation_iff_amount_exceeds_limit(
        self, limit: float, amount: float
    ) -> None:
        authority = _authority(constraints={"max_value_usd": limit})
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"amount_usd": amount},
        )
        violation = authority.constraint_violation(action)
        if amount > limit:
            assert violation is not None
            assert violation.startswith("VALUE_LIMIT_EXCEEDED")
        else:
            assert violation is None

    @given(
        arguments=st.dictionaries(
            st.text(max_size=20),
            st.one_of(
                st.text(max_size=50),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.none(),
            ),
        )
    )
    def test_never_crashes_on_arbitrary_arguments(self, arguments: dict) -> None:
        authority = _authority(constraints={"max_value_usd": 100.0})
        action = ActionRequest(
            agent=_agent(), action_type="mcp_tool_call", target="x", arguments=arguments
        )
        authority.constraint_violation(action)  # must not raise


class TestWorkflowCompositionProperties:
    @given(
        history=st.lists(
            st.tuples(_action_type, st.integers(min_value=0, max_value=120)), max_size=15
        ),
        new_action=_action_type,
    )
    def test_never_crashes_on_arbitrary_history(
        self, history: list[tuple[str, int]], new_action: str
    ) -> None:
        now = datetime(2026, 1, 1, tzinfo=UTC)
        actions = [
            TimestampedAction(action_type=t, at=now - timedelta(minutes=m)) for t, m in history
        ]
        rule = WorkflowSequenceRule(rule_id="r1", action_types=("a", "b"), window_minutes=60)
        check_composition_violation(actions, new_action, now, [rule])  # must not raise

    @given(
        prefix_noise=st.lists(_action_type, max_size=5),
        step_a=_action_type,
        step_b=_action_type,
    )
    def test_exact_two_step_sequence_always_caught_on_completion(
        self, prefix_noise: list[str], step_a: str, step_b: str
    ) -> None:
        assume(step_a != step_b)
        assume(step_a not in prefix_noise and step_b not in prefix_noise)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        rule = WorkflowSequenceRule(rule_id="r1", action_types=(step_a, step_b), window_minutes=60)
        history = [
            TimestampedAction(action_type=t, at=now - timedelta(minutes=10)) for t in prefix_noise
        ]
        history.append(TimestampedAction(action_type=step_a, at=now - timedelta(minutes=5)))
        reason = check_composition_violation(history, step_b, now, [rule])
        assert reason is not None
        assert reason.startswith("AUTHORITY_COMPOSITION_VIOLATION")

    @given(step_a=_action_type, step_b=_action_type)
    def test_first_step_alone_never_flags_two_step_rule(self, step_a: str, step_b: str) -> None:
        assume(step_a != step_b)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        rule = WorkflowSequenceRule(rule_id="r1", action_types=(step_a, step_b), window_minutes=60)
        reason = check_composition_violation([], step_a, now, [rule])
        assert reason is None


class TestMemoryFirewallProperties:
    @given(text=st.text(max_size=500))
    def test_never_crashes_on_arbitrary_text(self, text: str) -> None:
        result = scan_memory_write(text)  # must not raise
        assert result.is_blocked == bool(result.matched_patterns)

    @given(text=st.text(alphabet=st.characters(blacklist_categories=("Cc",)), max_size=200))
    def test_blocked_iff_patterns_matched(self, text: str) -> None:
        result = scan_memory_write(text)
        assert result.is_blocked == (len(result.matched_patterns) > 0)
