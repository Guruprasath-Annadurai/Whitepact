"""Tests for the WhitePact Authority Constitution (Heart Phase H1) --
`governance/constitution.py`'s `AuthorityConstitutionVersion`,
`compute_constitution_digest()`, and the ratified-version registry.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.constitution import (
    CONSTITUTION_V1,
    LAW_TEXT,
    AuthorityConstitutionVersion,
    ConstitutionalLawCode,
    build_constitution_version,
    compute_constitution_digest,
    current_constitution,
    explain_constitution,
    get_constitution_version,
)


class TestConstitutionV1Shape:
    def test_all_fifteen_laws_present(self) -> None:
        assert len(CONSTITUTION_V1.laws) == 15
        assert set(CONSTITUTION_V1.laws) == set(ConstitutionalLawCode)

    def test_every_law_has_text(self) -> None:
        for law in ConstitutionalLawCode:
            assert law in LAW_TEXT
            assert LAW_TEXT[law]  # non-empty

    def test_version_is_1(self) -> None:
        assert CONSTITUTION_V1.version == 1

    def test_digest_is_present_and_hex(self) -> None:
        assert len(CONSTITUTION_V1.canonical_digest) == 64
        int(CONSTITUTION_V1.canonical_digest, 16)  # raises if not valid hex

    def test_contains(self) -> None:
        assert CONSTITUTION_V1.contains(ConstitutionalLawCode.H1) is True

    def test_law_text_lookup(self) -> None:
        assert CONSTITUTION_V1.law_text(ConstitutionalLawCode.H2) == (
            "Machines cannot originate authority."
        )


class TestConstitutionRegistry:
    def test_get_version_1_returns_v1(self) -> None:
        assert get_constitution_version(1) is CONSTITUTION_V1

    def test_get_unratified_version_returns_none(self) -> None:
        assert get_constitution_version(999) is None

    def test_current_constitution_is_v1(self) -> None:
        assert current_constitution() is CONSTITUTION_V1

    def test_history_is_immutable(self) -> None:
        """A real, enforced guarantee (MappingProxyType), not just a
        comment -- attempting to mutate the registry must fail."""
        from responsibleai.governance import constitution as constitution_module

        with pytest.raises(TypeError):
            constitution_module._CONSTITUTION_HISTORY[2] = CONSTITUTION_V1  # type: ignore[index]


class TestExplainConstitution:
    def test_explain_v1_shape(self) -> None:
        explanation = explain_constitution(1)
        assert explanation is not None
        assert explanation["version"] == 1
        assert explanation["canonical_digest"] == CONSTITUTION_V1.canonical_digest
        assert len(explanation["laws"]) == 15
        assert explanation["laws"][0]["code"] == "H1"

    def test_explain_unratified_version_returns_none(self) -> None:
        assert explain_constitution(999) is None


class TestBuildConstitutionVersion:
    def test_digest_deterministic_for_identical_inputs(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        v1 = build_constitution_version(1, (ConstitutionalLawCode.H1,), ts, "test")
        v2 = build_constitution_version(1, (ConstitutionalLawCode.H1,), ts, "test")
        assert v1.canonical_digest == v2.canonical_digest

    def test_digest_changes_with_different_version_number(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        v1 = build_constitution_version(1, (ConstitutionalLawCode.H1,), ts, "test")
        v2 = build_constitution_version(2, (ConstitutionalLawCode.H1,), ts, "test")
        assert v1.canonical_digest != v2.canonical_digest

    def test_digest_changes_with_different_laws(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        v1 = build_constitution_version(1, (ConstitutionalLawCode.H1,), ts, "test")
        v2 = build_constitution_version(1, (ConstitutionalLawCode.H2,), ts, "test")
        assert v1.canonical_digest != v2.canonical_digest

    def test_digest_changes_with_different_description(self) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        v1 = build_constitution_version(1, (ConstitutionalLawCode.H1,), ts, "a")
        v2 = build_constitution_version(1, (ConstitutionalLawCode.H1,), ts, "b")
        assert v1.canonical_digest != v2.canonical_digest

    def test_digest_changes_with_different_ratified_at(self) -> None:
        v1 = build_constitution_version(
            1, (ConstitutionalLawCode.H1,), datetime(2026, 1, 1, tzinfo=UTC), "test"
        )
        v2 = build_constitution_version(
            1, (ConstitutionalLawCode.H1,), datetime(2026, 1, 2, tzinfo=UTC), "test"
        )
        assert v1.canonical_digest != v2.canonical_digest

    def test_law_order_is_significant(self) -> None:
        """Canonical digest covers laws as an ordered tuple, not a set
        -- two versions declaring the same laws in a different order
        are (deliberately) different digests, since `laws` is typed as
        `tuple`, not `frozenset`, throughout this module."""
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        v1 = build_constitution_version(
            1, (ConstitutionalLawCode.H1, ConstitutionalLawCode.H2), ts, "test"
        )
        v2 = build_constitution_version(
            1, (ConstitutionalLawCode.H2, ConstitutionalLawCode.H1), ts, "test"
        )
        assert v1.canonical_digest != v2.canonical_digest


_law_code = st.sampled_from(list(ConstitutionalLawCode))


class TestConstitutionDigestProperties:
    """Hypothesis property tests, matching the established pattern in
    tests/test_property_based.py -- pure, synchronous functions,
    no I/O, no DB fixture needed."""

    @given(
        version=st.integers(min_value=1, max_value=1000),
        laws=st.lists(_law_code, min_size=0, max_size=15, unique=True),
        description=st.text(max_size=200),
        days_offset=st.integers(min_value=0, max_value=3650),
    )
    def test_digest_is_pure_function_of_its_inputs(
        self, version: int, laws: list, description: str, days_offset: int
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=days_offset)
        d1 = compute_constitution_digest(version, tuple(laws), ts, description)
        d2 = compute_constitution_digest(version, tuple(laws), ts, description)
        assert d1 == d2
        assert len(d1) == 64

    @given(
        version=st.integers(min_value=1, max_value=1000),
        laws=st.lists(_law_code, min_size=1, max_size=15, unique=True),
        description=st.text(max_size=200),
    )
    def test_changing_version_number_changes_digest(
        self, version: int, laws: list, description: str
    ) -> None:
        ts = datetime(2026, 1, 1, tzinfo=UTC)
        d1 = compute_constitution_digest(version, tuple(laws), ts, description)
        d2 = compute_constitution_digest(version + 1, tuple(laws), ts, description)
        assert d1 != d2


class TestAuthorityConstitutionVersionIsFrozen:
    def test_cannot_mutate_version_field(self) -> None:
        with pytest.raises(Exception):  # noqa: B017 - dataclasses.FrozenInstanceError
            CONSTITUTION_V1.version = 999  # type: ignore[misc]

    def test_is_a_real_dataclass_instance(self) -> None:
        assert isinstance(CONSTITUTION_V1, AuthorityConstitutionVersion)
