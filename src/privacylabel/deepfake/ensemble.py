"""
Ensemble voting logic for deepfake detection.

Multiple detection models each produce a fake-probability score.
The ensemble combines them using configurable voting strategies.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import numpy as np


class VotingStrategy(StrEnum):
    """How to combine individual model scores into an ensemble decision."""

    MEAN = "mean"            # Simple average
    MAX = "max"              # Most suspicious model wins (conservative)
    WEIGHTED = "weighted"    # Weighted by individual model AUC
    MAJORITY = "majority"    # Majority vote on binary hard predictions


@dataclass(frozen=True)
class ModelScore:
    """A single model's fake-probability score."""

    model_name: str
    fake_probability: float  # 0.0 = definitely real, 1.0 = definitely fake
    weight: float = 1.0      # For weighted ensemble


class EnsembleVoter:
    """
    Combines per-model fake-probability scores into a single ensemble decision.

    Parameters
    ----------
    strategy : VotingStrategy
        Aggregation strategy. Default MEAN (fast, good baseline).
    threshold : float
        Probability above which media is classified as fake. Default 0.5.
    """

    def __init__(
        self,
        strategy: VotingStrategy = VotingStrategy.MEAN,
        threshold: float = 0.5,
    ) -> None:
        self.strategy = strategy
        self.threshold = threshold

    def vote(self, scores: list[ModelScore]) -> tuple[bool, float]:
        """
        Aggregate model scores into a final (is_fake, confidence) decision.

        Parameters
        ----------
        scores : list[ModelScore]
            Individual model predictions.

        Returns
        -------
        (is_fake, ensemble_score)
            is_fake: True if the ensemble score exceeds the threshold.
            ensemble_score: Combined fake probability [0, 1].
        """
        if not scores:
            return False, 0.0

        probs = np.array([s.fake_probability for s in scores])
        weights = np.array([s.weight for s in scores])

        if self.strategy == VotingStrategy.MEAN:
            ensemble_score = float(np.mean(probs))
        elif self.strategy == VotingStrategy.MAX:
            ensemble_score = float(np.max(probs))
        elif self.strategy == VotingStrategy.WEIGHTED:
            total_w = np.sum(weights)
            ensemble_score = float(np.sum(probs * weights) / total_w) if total_w > 0 else 0.0
        elif self.strategy == VotingStrategy.MAJORITY:
            hard_votes = probs >= self.threshold
            ensemble_score = float(np.mean(hard_votes))
        else:
            ensemble_score = float(np.mean(probs))

        is_fake = ensemble_score >= self.threshold
        return is_fake, ensemble_score

    def confidence(self, ensemble_score: float) -> float:
        """
        Map ensemble score to a calibrated confidence value.

        Confidence is highest near 0.0 (clearly real) or 1.0 (clearly fake),
        and lowest near the threshold (uncertain region).
        """
        return float(abs(ensemble_score - self.threshold) / self.threshold)
