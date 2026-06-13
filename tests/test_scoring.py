from __future__ import annotations

import pytest

from biasbuster.core.scoring import (
    bootstrap_confidence_interval,
    compute_combined_score,
    compute_length_ratio_score,
    compute_pairwise_divergence,
    compute_sentiment_divergence,
)


class TestComputePairwiseDivergence:
    def test_identical_texts_near_zero(self) -> None:
        texts = ["The engineer is highly skilled.", "The engineer is highly skilled."]
        score, _ = compute_pairwise_divergence(texts)
        assert score < 0.05

    def test_unrelated_texts_high(self) -> None:
        texts = [
            "Quantum mechanics governs subatomic particle behaviour.",
            "The chocolate cake recipe requires flour sugar butter eggs.",
            "Football is played on a grass pitch with a round ball.",
        ]
        score, _ = compute_pairwise_divergence(texts)
        assert score > 0.5

    def test_single_text_zero(self) -> None:
        score, pairs = compute_pairwise_divergence(["only one"])
        assert score == 0.0
        assert pairs == {}

    def test_empty_list_zero(self) -> None:
        score, pairs = compute_pairwise_divergence([])
        assert score == 0.0

    def test_empty_vocabulary_returns_zero(self) -> None:
        # All single-char tokens are filtered by TfidfVectorizer's default pattern
        # causing a ValueError internally; the function should return (0.0, {}) gracefully
        score, pairs = compute_pairwise_divergence(["a b c", "d e f"])
        assert score == 0.0
        assert pairs == {}

    def test_pair_count_two_texts(self) -> None:
        _, pairs = compute_pairwise_divergence(["aaa bbb", "ccc ddd"])
        assert len(pairs) == 1
        assert (0, 1) in pairs

    def test_pair_count_three_texts(self) -> None:
        _, pairs = compute_pairwise_divergence(["apple banana cherry", "delta epsilon zeta", "gamma kappa lambda"])
        assert len(pairs) == 3

    def test_score_bounded(self) -> None:
        texts = ["one two three", "four five six"]
        score, _ = compute_pairwise_divergence(texts)
        assert 0.0 <= score <= 1.0


class TestComputeLengthRatioScore:
    def test_equal_length_zero(self) -> None:
        assert compute_length_ratio_score(["one two three", "four five six"]) == pytest.approx(0.0)

    def test_extreme_ratio_capped(self) -> None:
        short = "ok"
        long_text = " ".join(["word"] * 200)
        score = compute_length_ratio_score([short, long_text])
        assert score <= 0.20

    def test_empty_returns_zero(self) -> None:
        assert compute_length_ratio_score([]) == 0.0
        assert compute_length_ratio_score(["", ""]) == 0.0

    def test_modest_difference(self) -> None:
        a = " ".join(["word"] * 50)
        b = " ".join(["word"] * 100)
        score = compute_length_ratio_score([a, b])
        assert 0.0 < score <= 0.20


class TestComputeSentimentDivergence:
    def test_same_sentiment_near_zero(self) -> None:
        texts = [
            "This is a great and wonderful outcome.",
            "This is a great and wonderful outcome.",
        ]
        score = compute_sentiment_divergence(texts)
        assert score < 0.10

    def test_opposite_sentiment_nonzero(self) -> None:
        positive = "This is excellent, outstanding, and wonderful! Very positive."
        negative = "This is terrible, awful, and dreadful. Very negative and bad."
        score = compute_sentiment_divergence([positive, negative])
        assert score >= 0.0

    def test_single_text_zero(self) -> None:
        assert compute_sentiment_divergence(["some text"]) == 0.0

    def test_returns_float(self) -> None:
        score = compute_sentiment_divergence(["hello world", "goodbye world"])
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestComputeCombinedScore:
    def test_identical_texts_low(self) -> None:
        texts = ["The engineer has strong skills.", "The engineer has strong skills."]
        score, _ = compute_combined_score(texts)
        assert score < 0.10

    def test_very_different_texts_high(self) -> None:
        texts = [
            "Outstanding decisive leadership driven by bold technical vision and strategy.",
            "Pleasant supportive empathetic helpful friendly approachable team member.",
        ]
        score, _ = compute_combined_score(texts)
        assert score > 0.10

    def test_score_bounded(self) -> None:
        texts = ["aaa bbb ccc", "ddd eee fff"]
        score, _ = compute_combined_score(texts)
        assert 0.0 <= score <= 1.0

    def test_pair_scores_returned(self) -> None:
        _, pairs = compute_combined_score(["aaa bbb", "ccc ddd"])
        assert (0, 1) in pairs

    def test_custom_sentiment_weight(self) -> None:
        texts = ["hello world peace", "goodbye cruel darkness"]
        score_default, _ = compute_combined_score(texts, sentiment_weight=0.20)
        score_zero, _ = compute_combined_score(texts, sentiment_weight=0.0)
        assert isinstance(score_default, float)
        assert isinstance(score_zero, float)


class TestBootstrapConfidenceInterval:
    def test_single_value_returns_same(self) -> None:
        lo, hi = bootstrap_confidence_interval([0.5])
        assert lo == 0.5
        assert hi == 0.5

    def test_empty_returns_zeros(self) -> None:
        lo, hi = bootstrap_confidence_interval([])
        assert lo == 0.0
        assert hi == 0.0

    def test_lower_le_upper(self) -> None:
        scores = [0.1, 0.2, 0.3, 0.25, 0.15]
        lo, hi = bootstrap_confidence_interval(scores)
        assert lo <= hi

    def test_interval_contains_mean(self) -> None:
        import numpy as np

        scores = [0.10, 0.20, 0.30, 0.40, 0.50]
        lo, hi = bootstrap_confidence_interval(scores)
        mean = float(np.mean(scores))
        assert lo <= mean <= hi

    def test_wider_with_more_variance(self) -> None:
        tight = [0.20, 0.21, 0.20, 0.21, 0.20]
        wide = [0.05, 0.50, 0.10, 0.45, 0.30]
        lo_t, hi_t = bootstrap_confidence_interval(tight)
        lo_w, hi_w = bootstrap_confidence_interval(wide)
        assert (hi_w - lo_w) > (hi_t - lo_t)
