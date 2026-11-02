"""Tests for Heart Phase H9 — Revocation Kernel
(`governance/revocation_kernel.py`).

Covers every `RevocationEpochCheckStatus` branch of
`check_revocation_epoch()` plus Hypothesis property tests for the
core invariant: an epoch strictly ahead of the issuance epoch always
means REVOKED_SINCE_ISSUANCE, an equal or (via bump_epoch()'s
monotonic construction) never-regressing epoch always means CURRENT,
and any scope/org mismatch always means SCOPE_MISMATCH regardless of
the epoch values themselves.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.revocation_kernel import (
    RevocationEpoch,
    RevocationEpochCheckStatus,
    bump_epoch,
    check_revocation_epoch,
)


class TestRevocationEpoch:
    def test_default_epoch_is_zero(self) -> None:
        epoch = RevocationEpoch(organization_id="org1", scope="delegation")
        assert epoch.epoch == 0

    def test_bump_epoch_advances_by_exactly_one(self) -> None:
        epoch = RevocationEpoch(organization_id="org1", scope="delegation", epoch=5)
        bumped = bump_epoch(epoch)
        assert bumped.epoch == 6

    def test_bump_epoch_preserves_organization_and_scope(self) -> None:
        epoch = RevocationEpoch(organization_id="org1", scope="delegation")
        bumped = bump_epoch(epoch)
        assert bumped.organization_id == "org1"
        assert bumped.scope == "delegation"

    def test_repeated_bumps_are_monotonic(self) -> None:
        epoch = RevocationEpoch(organization_id="org1", scope="delegation")
        e1 = bump_epoch(epoch)
        e2 = bump_epoch(e1)
        e3 = bump_epoch(e2)
        assert (epoch.epoch, e1.epoch, e2.epoch, e3.epoch) == (0, 1, 2, 3)


class TestCheckRevocationEpochCurrent:
    def test_identical_epoch_is_current(self) -> None:
        epoch = RevocationEpoch(organization_id="org1", scope="delegation", epoch=3)
        result = check_revocation_epoch(epoch, epoch)
        assert result.status == RevocationEpochCheckStatus.CURRENT
        assert result.is_current

    def test_equal_but_distinct_objects_is_current(self) -> None:
        issued_at = RevocationEpoch(organization_id="org1", scope="delegation", epoch=3)
        current = RevocationEpoch(organization_id="org1", scope="delegation", epoch=3)
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.CURRENT


class TestCheckRevocationEpochRevoked:
    def test_advanced_epoch_is_revoked_since_issuance(self) -> None:
        issued_at = RevocationEpoch(organization_id="org1", scope="delegation", epoch=0)
        current = bump_epoch(issued_at)
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.REVOKED_SINCE_ISSUANCE
        assert not result.is_current

    def test_multiple_bumps_still_revoked_since_issuance(self) -> None:
        issued_at = RevocationEpoch(organization_id="org1", scope="delegation", epoch=0)
        current = bump_epoch(bump_epoch(bump_epoch(issued_at)))
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.REVOKED_SINCE_ISSUANCE

    def test_result_reports_both_epoch_values(self) -> None:
        issued_at = RevocationEpoch(organization_id="org1", scope="delegation", epoch=2)
        current = RevocationEpoch(organization_id="org1", scope="delegation", epoch=5)
        result = check_revocation_epoch(issued_at, current)
        assert result.issued_at_epoch == 2
        assert result.current_epoch == 5


class TestCheckRevocationEpochScopeMismatch:
    def test_different_scope_same_org_is_mismatch(self) -> None:
        issued_at = RevocationEpoch(organization_id="org1", scope="delegation")
        current = RevocationEpoch(organization_id="org1", scope="root_authority")
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.SCOPE_MISMATCH
        assert not result.is_current

    def test_different_org_same_scope_is_mismatch(self) -> None:
        issued_at = RevocationEpoch(organization_id="org1", scope="delegation")
        current = RevocationEpoch(organization_id="org2", scope="delegation")
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.SCOPE_MISMATCH

    def test_mismatch_takes_priority_even_when_epochs_are_equal(self) -> None:
        issued_at = RevocationEpoch(organization_id="org1", scope="delegation", epoch=7)
        current = RevocationEpoch(organization_id="org1", scope="root_authority", epoch=7)
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.SCOPE_MISMATCH


class TestRevocationEpochProperties:
    """Hypothesis property tests for the core invariant."""

    @given(
        organization_id=st.text(min_size=1, max_size=10),
        scope=st.text(min_size=1, max_size=10),
        bumps=st.integers(min_value=0, max_value=50),
    )
    def test_epoch_bumped_n_times_is_current_only_against_itself(
        self, organization_id: str, scope: str, bumps: int
    ) -> None:
        epoch = RevocationEpoch(organization_id=organization_id, scope=scope)
        for _ in range(bumps):
            epoch = bump_epoch(epoch)
        assert check_revocation_epoch(epoch, epoch).status == RevocationEpochCheckStatus.CURRENT

    @given(
        organization_id=st.text(min_size=1, max_size=10),
        scope=st.text(min_size=1, max_size=10),
        issued_bumps=st.integers(min_value=0, max_value=20),
        extra_bumps=st.integers(min_value=1, max_value=20),
    )
    def test_any_additional_bump_after_issuance_is_always_revoked(
        self, organization_id: str, scope: str, issued_bumps: int, extra_bumps: int
    ) -> None:
        epoch = RevocationEpoch(organization_id=organization_id, scope=scope)
        for _ in range(issued_bumps):
            epoch = bump_epoch(epoch)
        issued_at = epoch
        current = epoch
        for _ in range(extra_bumps):
            current = bump_epoch(current)
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.REVOKED_SINCE_ISSUANCE
        assert not result.is_current

    @given(
        org_a=st.text(min_size=1, max_size=8),
        org_b=st.text(min_size=1, max_size=8),
        scope_a=st.text(min_size=1, max_size=8),
        scope_b=st.text(min_size=1, max_size=8),
        epoch_value=st.integers(min_value=0, max_value=100),
    )
    def test_any_scope_or_org_difference_always_yields_mismatch(
        self, org_a: str, org_b: str, scope_a: str, scope_b: str, epoch_value: int
    ) -> None:
        if org_a == org_b and scope_a == scope_b:
            return  # not the case under test
        issued_at = RevocationEpoch(organization_id=org_a, scope=scope_a, epoch=epoch_value)
        current = RevocationEpoch(organization_id=org_b, scope=scope_b, epoch=epoch_value)
        result = check_revocation_epoch(issued_at, current)
        assert result.status == RevocationEpochCheckStatus.SCOPE_MISMATCH
