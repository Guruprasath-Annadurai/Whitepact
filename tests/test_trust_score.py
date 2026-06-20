from __future__ import annotations

import pytest

from responsibleai.trust.score import TrustScore, TrustScoreEngine, _DEFAULT_WEIGHTS


class TestTrustScoreEngineInit:
    def test_default_weights_sum_to_one(self) -> None:
        assert abs(sum(_DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9

    def test_default_engine_creates_successfully(self) -> None:
        engine = TrustScoreEngine()
        assert engine is not None

    def test_custom_weights_accepted(self) -> None:
        weights = {
            "fairness": 0.30,
            "privacy": 0.20,
            "security": 0.20,
            "robustness": 0.10,
            "compliance": 0.10,
            "authenticity": 0.10,
        }
        engine = TrustScoreEngine(weights=weights)
        assert engine is not None

    def test_weights_not_summing_to_one_raises(self) -> None:
        bad_weights = {k: 0.1 for k in _DEFAULT_WEIGHTS}  # sums to 0.6
        with pytest.raises(ValueError, match="sum to 1.0"):
            TrustScoreEngine(weights=bad_weights)

    def test_missing_dimension_in_weights_raises(self) -> None:
        weights = {k: v for k, v in _DEFAULT_WEIGHTS.items() if k != "authenticity"}
        # Adjust so remaining sum ≠ 1
        weights["fairness"] = 0.30  # total won't be 1 either
        with pytest.raises((ValueError, KeyError)):
            TrustScoreEngine(weights=weights)


class TestTrustScoreCompute:
    def setup_method(self) -> None:
        self.engine = TrustScoreEngine()

    def test_all_ones_gives_grade_a(self) -> None:
        score = self.engine.compute(
            fairness=1.0, privacy=1.0, security=1.0,
            robustness=1.0, compliance=1.0, authenticity=1.0,
        )
        assert score.overall == pytest.approx(100.0)
        assert score.grade == "A"
        assert score.risk_level == "LOW"

    def test_all_zeros_gives_grade_f(self) -> None:
        score = self.engine.compute(
            fairness=0.0, privacy=0.0, security=0.0,
            robustness=0.0, compliance=0.0, authenticity=0.0,
        )
        assert score.overall == pytest.approx(0.0)
        assert score.grade == "F"
        assert score.risk_level == "CRITICAL"

    def test_all_halves_gives_midrange(self) -> None:
        score = self.engine.compute()  # all default to 0.5
        assert score.overall == pytest.approx(50.0)

    def test_grade_boundaries(self) -> None:
        engine = self.engine
        assert engine.compute(fairness=0.9, privacy=0.9, security=0.9,
                              robustness=0.9, compliance=0.9, authenticity=0.9).grade == "A"
        assert engine.compute(fairness=0.8, privacy=0.8, security=0.8,
                              robustness=0.8, compliance=0.8, authenticity=0.8).grade == "B"
        assert engine.compute(fairness=0.7, privacy=0.7, security=0.7,
                              robustness=0.7, compliance=0.7, authenticity=0.7).grade == "C"
        assert engine.compute(fairness=0.6, privacy=0.6, security=0.6,
                              robustness=0.6, compliance=0.6, authenticity=0.6).grade == "D"
        assert engine.compute(fairness=0.5, privacy=0.5, security=0.5,
                              robustness=0.5, compliance=0.5, authenticity=0.5).grade == "F"

    def test_risk_level_low(self) -> None:
        score = self.engine.compute(
            fairness=0.9, privacy=0.9, security=0.9,
            robustness=0.9, compliance=0.9, authenticity=0.9,
        )
        assert score.risk_level == "LOW"

    def test_risk_level_critical(self) -> None:
        score = self.engine.compute(
            fairness=0.1, privacy=0.1, security=0.1,
            robustness=0.1, compliance=0.1, authenticity=0.1,
        )
        assert score.risk_level == "CRITICAL"

    def test_invalid_dimension_above_one_raises(self) -> None:
        with pytest.raises(ValueError, match="fairness"):
            self.engine.compute(fairness=1.1)

    def test_invalid_dimension_below_zero_raises(self) -> None:
        with pytest.raises(ValueError, match="privacy"):
            self.engine.compute(privacy=-0.1)

    def test_passed_at_70(self) -> None:
        score = self.engine.compute(
            fairness=0.7, privacy=0.7, security=0.7,
            robustness=0.7, compliance=0.7, authenticity=0.7,
        )
        assert score.passed

    def test_failed_below_70(self) -> None:
        score = self.engine.compute(
            fairness=0.5, privacy=0.5, security=0.5,
            robustness=0.5, compliance=0.5, authenticity=0.5,
        )
        assert not score.passed

    def test_to_dict_structure(self) -> None:
        score = self.engine.compute()
        d = score.to_dict()
        assert "trust_score" in d
        assert "grade" in d
        assert "risk" in d
        assert "dimensions" in d
        assert "timestamp" in d
        assert set(d["dimensions"].keys()) == {
            "fairness", "privacy", "security", "robustness", "compliance", "authenticity"
        }

    def test_trust_score_frozen(self) -> None:
        score = self.engine.compute()
        with pytest.raises(Exception):
            score.grade = "Z"  # type: ignore[misc]


class TestFromModuleResults:
    def setup_method(self) -> None:
        self.engine = TrustScoreEngine()

    def test_no_args_returns_midrange(self) -> None:
        score = self.engine.from_module_results()
        assert score.overall == pytest.approx(50.0)

    def test_zero_bias_means_full_fairness(self) -> None:
        score = self.engine.from_module_results(bias_divergence=0.0)
        assert score.fairness == pytest.approx(1.0)

    def test_high_bias_means_low_fairness(self) -> None:
        score = self.engine.from_module_results(bias_divergence=1.0)
        assert score.fairness == pytest.approx(0.0)

    def test_low_hallucination_means_high_robustness(self) -> None:
        score = self.engine.from_module_results(hallucination_risk=0.0)
        assert score.robustness == pytest.approx(1.0)

    def test_high_deepfake_probability_reduces_authenticity(self) -> None:
        score = self.engine.from_module_results(deepfake_fake_probability=1.0)
        assert score.authenticity == pytest.approx(0.0)

    def test_full_security_pass_rate(self) -> None:
        score = self.engine.from_module_results(security_pass_rate=1.0)
        assert score.security == pytest.approx(1.0)
