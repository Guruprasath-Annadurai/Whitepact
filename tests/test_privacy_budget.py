from __future__ import annotations

import pytest

from privacylabel.core.privacy_budget import PrivacyBudget, PrivacyBudgetExhaustedError


class TestPrivacyBudgetInit:
    def test_valid_params(self) -> None:
        b = PrivacyBudget(epsilon=1.0, delta=1e-6)
        assert b.epsilon == 1.0
        assert b.delta == 1e-6

    def test_invalid_epsilon_zero(self) -> None:
        with pytest.raises(ValueError, match="epsilon"):
            PrivacyBudget(epsilon=0.0, delta=1e-6)

    def test_invalid_epsilon_negative(self) -> None:
        with pytest.raises(ValueError, match="epsilon"):
            PrivacyBudget(epsilon=-1.0, delta=1e-6)

    def test_invalid_delta_negative(self) -> None:
        with pytest.raises(ValueError, match="delta"):
            PrivacyBudget(epsilon=1.0, delta=-0.1)

    def test_delta_one_invalid(self) -> None:
        with pytest.raises(ValueError, match="delta"):
            PrivacyBudget(epsilon=1.0, delta=1.0)

    def test_delta_zero_valid(self) -> None:
        b = PrivacyBudget(epsilon=1.0, delta=0.0)
        assert b.delta == 0.0


class TestPrivacyBudgetConsume:
    def test_remaining_decreases_after_consume(self) -> None:
        b = PrivacyBudget(epsilon=2.0, delta=1e-5)
        b.consume(0.5)
        assert b.remaining_epsilon == pytest.approx(1.5)

    def test_is_exhausted_false_initially(self) -> None:
        b = PrivacyBudget(epsilon=1.0, delta=1e-6)
        assert not b.is_exhausted

    def test_is_exhausted_after_full_spend(self) -> None:
        b = PrivacyBudget(epsilon=1.0, delta=1e-6)
        b.consume(1.0)
        assert b.is_exhausted

    def test_raises_on_over_spend(self) -> None:
        b = PrivacyBudget(epsilon=0.5, delta=1e-6)
        with pytest.raises(PrivacyBudgetExhaustedError):
            b.consume(0.6)

    def test_multiple_consumes_track_correctly(self) -> None:
        b = PrivacyBudget(epsilon=1.0, delta=1e-6)
        b.consume(0.3)
        b.consume(0.3)
        assert b.spent_epsilon == pytest.approx(0.6)
        assert b.remaining_epsilon == pytest.approx(0.4)

    def test_delta_spending_tracked(self) -> None:
        b = PrivacyBudget(epsilon=2.0, delta=1e-5)
        b.consume(0.5, delta_cost=1e-6)
        assert b.spent_delta == pytest.approx(1e-6)

    def test_remaining_never_negative(self) -> None:
        b = PrivacyBudget(epsilon=1.0, delta=1e-6)
        b.consume(1.0)
        assert b.remaining_epsilon == 0.0


class TestPrivacyBudgetToDict:
    def test_to_dict_keys(self) -> None:
        b = PrivacyBudget(epsilon=0.5, delta=1e-6)
        d = b.to_dict()
        for key in ("epsilon", "delta", "spent_epsilon", "spent_delta",
                    "remaining_epsilon", "remaining_delta"):
            assert key in d

    def test_to_dict_values(self) -> None:
        b = PrivacyBudget(epsilon=1.0, delta=1e-5)
        b.consume(0.4)
        d = b.to_dict()
        assert d["epsilon"] == 1.0
        assert d["spent_epsilon"] == pytest.approx(0.4)
        assert d["remaining_epsilon"] == pytest.approx(0.6)
