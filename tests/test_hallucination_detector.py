from __future__ import annotations

import pytest

from responsibleai.hallucination.detector import HallucinationDetector, HallucinationResult


class TestHallucinationDetectorInit:
    def test_default_init(self) -> None:
        detector = HallucinationDetector()
        assert detector is not None

    def test_weights_must_sum_to_one(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            HallucinationDetector(
                consistency_weight=0.5,
                hedging_weight=0.5,
                unsupported_weight=0.5,
            )

    def test_custom_weights_accepted(self) -> None:
        detector = HallucinationDetector(
            consistency_weight=0.50,
            hedging_weight=0.25,
            unsupported_weight=0.25,
        )
        assert detector is not None


class TestHedgingDetection:
    def setup_method(self) -> None:
        self.detector = HallucinationDetector()

    def test_confident_text_low_hedging(self) -> None:
        result = self.detector.analyze(
            "The Eiffel Tower is located in Paris, France."
        )
        assert result.hedging_score < 0.3

    def test_heavily_hedged_text_high_hedging(self) -> None:
        result = self.detector.analyze(
            "I think maybe possibly it might be the case that perhaps "
            "I believe this could be true, though I'm not sure or certain."
        )
        assert result.hedging_score > 0.3

    def test_moderate_hedging_medium_score(self) -> None:
        # Longer confident text with a single hedge at the end stays below maximum
        text = (
            "The capital of France is Paris. The Eiffel Tower was built in 1889. "
            "France is a republic. The Seine river flows through the city. "
            "The Louvre museum houses thousands of artworks. I believe the metro "
            "is one of the busiest in Europe."
        )
        result = self.detector.analyze(text)
        assert result.hedging_score < 0.9


class TestConsistencyScoring:
    def setup_method(self) -> None:
        self.detector = HallucinationDetector()

    def test_identical_candidates_high_consistency(self) -> None:
        text = "The capital of France is Paris."
        candidates = [
            "The capital of France is Paris.",
            "The capital of France is Paris.",
        ]
        result = self.detector.analyze(text, candidates=candidates)
        assert result.consistency_score > 0.8

    def test_very_different_candidates_lower_consistency(self) -> None:
        text = "Quantum mechanics describes subatomic behavior."
        candidates = [
            "Cooking pasta requires boiling water.",
            "The stock market closed higher today.",
        ]
        result = self.detector.analyze(text, candidates=candidates)
        # Very different topics → low consistency
        assert result.consistency_score < 0.5

    def test_no_candidates_defaults_to_half(self) -> None:
        result = self.detector.analyze("Some text about science.")
        assert result.consistency_score == pytest.approx(0.5)
        assert result.num_candidates == 0

    def test_candidates_count_recorded(self) -> None:
        result = self.detector.analyze(
            "Text.",
            candidates=["Candidate one.", "Candidate two."],
        )
        assert result.num_candidates == 2


class TestUnsupportedClaims:
    def setup_method(self) -> None:
        self.detector = HallucinationDetector()

    def test_text_with_statistics_without_citation_flagged(self) -> None:
        result = self.detector.analyze(
            "Studies show that 73 percent of users prefer mobile apps. "
            "In 2023, the market grew by 45 billion dollars."
        )
        assert len(result.unsupported_claims) > 0

    def test_text_with_attribution_not_flagged(self) -> None:
        result = self.detector.analyze(
            "According to the World Health Organization, vaccination coverage "
            "has improved (WHO, 2023)."
        )
        # Attribution present → should not be flagged
        assert len(result.unsupported_claims) == 0

    def test_plain_opinion_no_unsupported_claims(self) -> None:
        result = self.detector.analyze(
            "This approach seems reasonable and could work well in practice."
        )
        assert len(result.unsupported_claims) == 0


class TestHallucinationRisk:
    def setup_method(self) -> None:
        self.detector = HallucinationDetector()

    def test_risk_in_zero_to_one(self) -> None:
        result = self.detector.analyze("Some text here.")
        assert 0.0 <= result.hallucination_risk <= 1.0

    def test_risk_level_low_for_clean_text(self) -> None:
        text = "Paris is the capital city of France."
        result = self.detector.analyze(text, candidates=[text, text])
        assert result.risk_level in ("low", "medium")

    def test_risk_levels_valid(self) -> None:
        result = self.detector.analyze("Text.")
        assert result.risk_level in ("low", "medium", "high", "critical")

    def test_to_dict_structure(self) -> None:
        result = self.detector.analyze("Test text.")
        d = result.to_dict()
        expected_keys = {
            "hallucination_risk", "risk_level", "consistency_score",
            "hedging_score", "unsupported_claims_count",
            "unsupported_claims_sample", "num_candidates",
        }
        assert expected_keys.issubset(d.keys())

    def test_result_is_frozen(self) -> None:
        result = self.detector.analyze("Text.")
        with pytest.raises(Exception):
            result.risk_level = "none"  # type: ignore[misc]
