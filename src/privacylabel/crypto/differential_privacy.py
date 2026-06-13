"""
Differential privacy mechanisms for PrivacyLabel.

All mechanisms satisfy (ε, δ)-differential privacy as defined in:
    Dwork et al. (2006). Calibrating Noise to Sensitivity in Private Data Analysis.
    Dwork & Roth (2014). The Algorithmic Foundations of Differential Privacy.

Correctness properties:
    - Laplace mechanism: (ε, 0)-DP, noise scale b = Δf / ε
    - Gaussian mechanism: (ε, δ)-DP, σ ≥ √(2 ln(1.25/δ)) · Δf / ε
    - Exponential mechanism: (ε, 0)-DP, P(output=o) ∝ exp(ε·u(o) / 2Δu)
"""

from __future__ import annotations

import math

import numpy as np


class DifferentialPrivacy:
    """
    Collection of standard differential privacy mechanisms.

    Parameters
    ----------
    epsilon : float
        Privacy loss parameter (lower = more private, higher = more accurate).
        Typical values: 0.1 (strong), 0.5 (moderate), 1.0 (weak).
    delta : float
        Failure probability for approximate DP (δ = 0 for pure DP).
        Typical values: 1e-5 to 1e-8. Must be > 0 for Gaussian mechanism.
    """

    def __init__(self, epsilon: float = 1.0, delta: float = 1e-6) -> None:
        if epsilon <= 0:
            raise ValueError(f"epsilon must be positive, got {epsilon}")
        if not 0.0 <= delta < 1.0:
            raise ValueError(f"delta must be in [0, 1), got {delta}")
        self.epsilon = epsilon
        self.delta = delta

    # ------------------------------------------------------------------
    # Laplace mechanism  (ε, 0)-DP
    # ------------------------------------------------------------------

    def laplace_mechanism(
        self, value: np.ndarray, sensitivity: float = 1.0
    ) -> np.ndarray:
        """
        Add calibrated Laplace noise to achieve (ε, 0)-DP.

        Noise drawn from Lap(0, sensitivity / ε).
        Provides pure differential privacy (δ = 0).

        Parameters
        ----------
        value : np.ndarray
            True value(s) to be privatised.
        sensitivity : float
            L1 sensitivity of the query: max over adjacent inputs of |q(D) - q(D')|.

        Returns
        -------
        np.ndarray
            Privatised value with calibrated Laplace noise added.
        """
        if sensitivity <= 0:
            raise ValueError(f"sensitivity must be positive, got {sensitivity}")
        noise_scale = sensitivity / self.epsilon
        noise = np.random.laplace(loc=0.0, scale=noise_scale, size=np.asarray(value).shape)
        return np.asarray(value) + noise

    # ------------------------------------------------------------------
    # Gaussian mechanism  (ε, δ)-DP  with δ > 0
    # ------------------------------------------------------------------

    def gaussian_mechanism(
        self, value: np.ndarray, sensitivity: float = 1.0
    ) -> np.ndarray:
        """
        Add calibrated Gaussian noise to achieve (ε, δ)-DP.

        σ = √(2 · ln(1.25 / δ)) · sensitivity / ε
        This satisfies (ε, δ)-DP per Dwork & Roth (2014) Proposition 3.3.

        Parameters
        ----------
        value : np.ndarray
            True value(s) to be privatised.
        sensitivity : float
            L2 sensitivity of the query.

        Returns
        -------
        np.ndarray
            Privatised value with calibrated Gaussian noise added.
        """
        if self.delta <= 0:
            raise ValueError("Gaussian mechanism requires delta > 0.")
        if sensitivity <= 0:
            raise ValueError(f"sensitivity must be positive, got {sensitivity}")
        sigma = math.sqrt(2.0 * math.log(1.25 / self.delta)) * sensitivity / self.epsilon
        noise = np.random.normal(loc=0.0, scale=sigma, size=np.asarray(value).shape)
        return np.asarray(value) + noise

    # ------------------------------------------------------------------
    # Exponential mechanism  (ε, 0)-DP
    # ------------------------------------------------------------------

    def exponential_mechanism(
        self, scores: np.ndarray, sensitivity: float = 1.0
    ) -> int:
        """
        Privately select an element by score using the exponential mechanism.

        P(output = i) ∝ exp(ε · scores[i] / (2 · sensitivity))

        Satisfies (ε, 0)-DP regardless of score range.

        Parameters
        ----------
        scores : np.ndarray
            Quality/utility scores for each candidate element.
        sensitivity : float
            L∞ sensitivity of the score function (max score range per neighbour swap).

        Returns
        -------
        int
            Index of the privately-selected element.
        """
        if sensitivity <= 0:
            raise ValueError(f"sensitivity must be positive, got {sensitivity}")
        scaled = (self.epsilon / (2.0 * sensitivity)) * np.asarray(scores, dtype=float)
        # Numerically stable: subtract max before exp
        shifted = scaled - np.max(scaled)
        exp_scores = np.exp(shifted)
        probabilities = exp_scores / np.sum(exp_scores)
        return int(np.random.choice(len(scores), p=probabilities))

    # ------------------------------------------------------------------
    # Report-Noisy-Max  (ε, 0)-DP
    # ------------------------------------------------------------------

    def report_noisy_max(self, scores: np.ndarray, sensitivity: float = 1.0) -> int:
        """
        Privately return the index of the maximum score.

        Adds Laplace(0, 2·sensitivity/ε) to each score and returns argmax.
        Satisfies (ε, 0)-DP.

        This is equivalent to the exponential mechanism when only the argmax
        is released (not the noisy score itself).
        """
        if sensitivity <= 0:
            raise ValueError(f"sensitivity must be positive, got {sensitivity}")
        noise_scale = 2.0 * sensitivity / self.epsilon
        scores_arr = np.asarray(scores, dtype=float)
        noisy = scores_arr + np.random.laplace(loc=0.0, scale=noise_scale, size=scores_arr.shape)
        return int(np.argmax(noisy))

    # ------------------------------------------------------------------
    # Gradient privatisation  (for federated learning)
    # ------------------------------------------------------------------

    def privatise_gradients(
        self, gradients: np.ndarray, clip_norm: float = 1.0
    ) -> np.ndarray:
        """
        Apply DP-SGD gradient privatisation.

        Steps:
            1. Clip gradient by L2 norm to bound sensitivity.
            2. Add calibrated Gaussian noise (Gaussian mechanism).

        This is the mechanism used in Abadi et al. (2016) "Deep Learning
        with Differential Privacy" (NeurIPS 2016).

        Parameters
        ----------
        gradients : np.ndarray
            Raw model gradients from local training.
        clip_norm : float
            L2 clipping threshold (sets the sensitivity).

        Returns
        -------
        np.ndarray
            Clipped and noised gradients ready for upload to the aggregator.
        """
        if clip_norm <= 0:
            raise ValueError(f"clip_norm must be positive, got {clip_norm}")
        g = np.asarray(gradients, dtype=float)
        l2 = np.linalg.norm(g)
        # Clip: scale down if norm exceeds clip_norm
        if l2 > clip_norm:
            g = g * (clip_norm / l2)
        # Add Gaussian noise calibrated to clip_norm as the L2 sensitivity
        private_g = self.gaussian_mechanism(g, sensitivity=clip_norm)
        return private_g

    def gaussian_sigma(self, sensitivity: float = 1.0) -> float:
        """Return the σ used by the Gaussian mechanism for the current (ε, δ)."""
        if self.delta <= 0:
            raise ValueError("Gaussian mechanism requires delta > 0.")
        return math.sqrt(2.0 * math.log(1.25 / self.delta)) * sensitivity / self.epsilon
