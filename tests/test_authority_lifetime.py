"""Tests for Heart Phase H8 — Authority Lifetime
(`governance/authority_lifetime.py`).

Covers every `LifetimeStatus` branch of `check_lifetime()` plus
Hypothesis property tests for the two independent staleness
invariants: mutation always wins over age, and age alone follows a
strict boundary (age <= max_age is FRESH, age > max_age is
STALE_BY_AGE).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.authority_lifetime import (
    CONSENT_PROOF_LIFETIME_WINDOW,
    DELEGATION_LEGITIMACY_LIFETIME_WINDOW,
    PURPOSE_BINDING_LIFETIME_WINDOW,
    ROOT_AUTHORITY_LIFETIME_WINDOW,
    LifetimeStatus,
    LifetimeWindow,
    check_lifetime,
)


class TestFreshVerdicts:
    def test_just_evaluated_is_fresh(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        result = check_lifetime(now, window, now=now)
        assert result.status == LifetimeStatus.FRESH
        assert result.is_fresh
        assert result.age_seconds == 0.0

    def test_exact_boundary_age_is_still_fresh(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        evaluated_at = now - timedelta(seconds=300)
        result = check_lifetime(evaluated_at, window, now=now)
        assert result.status == LifetimeStatus.FRESH


class TestStaleByAge:
    def test_older_than_window_is_stale(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        evaluated_at = now - timedelta(seconds=301)
        result = check_lifetime(evaluated_at, window, now=now)
        assert result.status == LifetimeStatus.STALE_BY_AGE
        assert not result.is_fresh

    def test_just_over_boundary_is_stale(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        evaluated_at = now - timedelta(seconds=300.001)
        result = check_lifetime(evaluated_at, window, now=now)
        assert result.status == LifetimeStatus.STALE_BY_AGE

    def test_age_seconds_reported_accurately(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=60)
        evaluated_at = now - timedelta(seconds=125)
        result = check_lifetime(evaluated_at, window, now=now)
        assert result.age_seconds == 125.0
        assert result.max_age_seconds == 60


class TestStaleByMutation:
    def test_digest_mismatch_is_stale_by_mutation_even_when_fresh_by_age(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        result = check_lifetime(now, window, evaluated_digest="abc", current_digest="xyz", now=now)
        assert result.status == LifetimeStatus.STALE_BY_MUTATION
        assert not result.is_fresh

    def test_digest_match_is_not_stale_by_mutation(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        result = check_lifetime(now, window, evaluated_digest="abc", current_digest="abc", now=now)
        assert result.status == LifetimeStatus.FRESH

    def test_mutation_takes_priority_over_age(self) -> None:
        """When a verdict is both old AND its underlying object has
        mutated, mutation is reported, not age -- the more fundamental
        problem."""
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        old = now - timedelta(seconds=10_000)
        result = check_lifetime(old, window, evaluated_digest="abc", current_digest="xyz", now=now)
        assert result.status == LifetimeStatus.STALE_BY_MUTATION

    def test_only_evaluated_digest_supplied_skips_mutation_check(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        result = check_lifetime(now, window, evaluated_digest="abc", current_digest=None, now=now)
        assert result.status == LifetimeStatus.FRESH

    def test_only_current_digest_supplied_skips_mutation_check(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        result = check_lifetime(now, window, evaluated_digest=None, current_digest="xyz", now=now)
        assert result.status == LifetimeStatus.FRESH

    def test_neither_digest_supplied_skips_mutation_check(self) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=300)
        result = check_lifetime(now, window, now=now)
        assert result.status == LifetimeStatus.FRESH


class TestNamedLifetimeWindows:
    def test_delegation_window_is_shortest(self) -> None:
        assert (
            DELEGATION_LEGITIMACY_LIFETIME_WINDOW.max_age_seconds
            < PURPOSE_BINDING_LIFETIME_WINDOW.max_age_seconds
        )
        assert (
            PURPOSE_BINDING_LIFETIME_WINDOW.max_age_seconds
            < CONSENT_PROOF_LIFETIME_WINDOW.max_age_seconds
        )
        assert (
            CONSENT_PROOF_LIFETIME_WINDOW.max_age_seconds
            <= ROOT_AUTHORITY_LIFETIME_WINDOW.max_age_seconds
        )

    def test_all_named_windows_have_positive_max_age(self) -> None:
        for window in (
            ROOT_AUTHORITY_LIFETIME_WINDOW,
            CONSENT_PROOF_LIFETIME_WINDOW,
            PURPOSE_BINDING_LIFETIME_WINDOW,
            DELEGATION_LEGITIMACY_LIFETIME_WINDOW,
        ):
            assert window.max_age_seconds > 0


class TestAuthorityLifetimeProperties:
    """Hypothesis property tests for the two independent staleness invariants."""

    @given(
        max_age=st.floats(min_value=1, max_value=1_000_000, allow_nan=False),
        age=st.floats(min_value=0, max_value=2_000_000, allow_nan=False),
    )
    def test_age_boundary_is_strict(self, max_age: float, age: float) -> None:
        # timedelta() rounds to microsecond precision, so the age
        # check_lifetime() actually measures can differ from the
        # generated `age` by a sub-microsecond amount -- assert against
        # the *measured* age_seconds, not the input, to test the real
        # invariant (status matches age_seconds vs. max_age_seconds)
        # without chasing float-rounding noise at the exact boundary.
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=max_age)
        evaluated_at = now - timedelta(seconds=age)
        result = check_lifetime(evaluated_at, window, now=now)
        if result.age_seconds > max_age:
            assert result.status == LifetimeStatus.STALE_BY_AGE
        else:
            assert result.status == LifetimeStatus.FRESH

    @given(
        evaluated_digest=st.text(min_size=1, max_size=20),
        current_digest=st.text(min_size=1, max_size=20),
        age=st.floats(min_value=0, max_value=100, allow_nan=False),
    )
    def test_mismatched_digests_always_stale_by_mutation_regardless_of_age(
        self, evaluated_digest: str, current_digest: str, age: float
    ) -> None:
        if evaluated_digest == current_digest:
            return  # not the case under test
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=1_000_000)  # never stale by age
        evaluated_at = now - timedelta(seconds=age)
        result = check_lifetime(
            evaluated_at,
            window,
            evaluated_digest=evaluated_digest,
            current_digest=current_digest,
            now=now,
        )
        assert result.status == LifetimeStatus.STALE_BY_MUTATION

    @given(digest=st.text(min_size=1, max_size=20))
    def test_matching_digests_never_cause_mutation_staleness(self, digest: str) -> None:
        now = datetime.now(UTC)
        window = LifetimeWindow(max_age_seconds=1_000_000)
        result = check_lifetime(
            now, window, evaluated_digest=digest, current_digest=digest, now=now
        )
        assert result.status != LifetimeStatus.STALE_BY_MUTATION
