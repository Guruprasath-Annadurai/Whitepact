from __future__ import annotations

import math

import numpy as np
import pytest

from privacylabel.crypto.differential_privacy import DifferentialPrivacy


class TestInit:
    def test_valid_params(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        assert dp.epsilon == 1.0
        assert dp.delta == 1e-6

    def test_invalid_epsilon_zero(self) -> None:
        with pytest.raises(ValueError, match="epsilon"):
            DifferentialPrivacy(epsilon=0.0)

    def test_invalid_epsilon_negative(self) -> None:
        with pytest.raises(ValueError, match="epsilon"):
            DifferentialPrivacy(epsilon=-0.5)

    def test_invalid_delta_negative(self) -> None:
        with pytest.raises(ValueError, match="delta"):
            DifferentialPrivacy(epsilon=1.0, delta=-0.1)

    def test_invalid_delta_one(self) -> None:
        with pytest.raises(ValueError, match="delta"):
            DifferentialPrivacy(epsilon=1.0, delta=1.0)

    def test_pure_dp_delta_zero(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=0.0)
        assert dp.delta == 0.0


class TestLaplaceMechanism:
    def test_output_shape_preserved(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        x = np.array([1.0, 2.0, 3.0])
        out = dp.laplace_mechanism(x)
        assert out.shape == x.shape

    def test_scalar_input(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        out = dp.laplace_mechanism(np.array(5.0))
        assert out.shape == ()

    def test_noise_is_nonzero_on_average(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        x = np.zeros(1000)
        out = dp.laplace_mechanism(x)
        # Probability that ALL 1000 noise samples are exactly 0 is negligible
        assert not np.all(out == 0.0)

    def test_noise_scale_increases_with_smaller_epsilon(self) -> None:
        # Smaller epsilon → more noise → larger std deviation of output
        np.random.seed(42)
        x = np.zeros(10000)
        dp_high_priv = DifferentialPrivacy(epsilon=0.1)
        dp_low_priv = DifferentialPrivacy(epsilon=10.0)
        std_high = float(np.std(dp_high_priv.laplace_mechanism(x)))
        std_low = float(np.std(dp_low_priv.laplace_mechanism(x)))
        assert std_high > std_low

    def test_invalid_sensitivity(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        with pytest.raises(ValueError, match="sensitivity"):
            dp.laplace_mechanism(np.array([1.0]), sensitivity=0.0)

    def test_noise_mean_near_zero(self) -> None:
        np.random.seed(0)
        dp = DifferentialPrivacy(epsilon=1.0)
        x = np.zeros(100000)
        out = dp.laplace_mechanism(x)
        assert abs(float(np.mean(out))) < 0.1  # Laplace is zero-mean

    def test_noise_scale_matches_formula(self) -> None:
        # Scale b = sensitivity / epsilon → std = b * sqrt(2)
        np.random.seed(1)
        dp = DifferentialPrivacy(epsilon=2.0)
        x = np.zeros(50000)
        out = dp.laplace_mechanism(x, sensitivity=1.0)
        expected_b = 1.0 / 2.0
        # Std of Laplace(b) is b * sqrt(2)
        expected_std = expected_b * math.sqrt(2)
        actual_std = float(np.std(out))
        assert abs(actual_std - expected_std) < 0.05  # 5% tolerance


class TestGaussianMechanism:
    def test_output_shape_preserved(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        x = np.ones(5)
        out = dp.gaussian_mechanism(x)
        assert out.shape == (5,)

    def test_requires_positive_delta(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=0.0)
        with pytest.raises(ValueError, match="delta"):
            dp.gaussian_mechanism(np.array([1.0]))

    def test_noise_mean_near_zero(self) -> None:
        np.random.seed(2)
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        x = np.zeros(50000)
        out = dp.gaussian_mechanism(x)
        assert abs(float(np.mean(out))) < 0.05

    def test_sigma_formula(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        sigma = dp.gaussian_sigma(sensitivity=1.0)
        expected = math.sqrt(2.0 * math.log(1.25 / 1e-6)) * 1.0 / 1.0
        assert abs(sigma - expected) < 1e-10

    def test_invalid_sensitivity(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        with pytest.raises(ValueError, match="sensitivity"):
            dp.gaussian_mechanism(np.array([1.0]), sensitivity=-1.0)


class TestExponentialMechanism:
    def test_returns_valid_index(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        scores = np.array([0.1, 0.5, 0.9])
        idx = dp.exponential_mechanism(scores)
        assert 0 <= idx < 3

    def test_high_score_selected_most_often(self) -> None:
        np.random.seed(3)
        dp = DifferentialPrivacy(epsilon=5.0)  # large ε → near-deterministic
        scores = np.array([0.0, 0.0, 1.0])
        counts = [0, 0, 0]
        for _ in range(200):
            idx = dp.exponential_mechanism(scores)
            counts[idx] += 1
        # Index 2 (score=1.0) should be selected most often with large ε
        assert counts[2] > counts[0] + counts[1]

    def test_invalid_sensitivity(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        with pytest.raises(ValueError, match="sensitivity"):
            dp.exponential_mechanism(np.array([1.0, 2.0]), sensitivity=0.0)


class TestReportNoisyMax:
    def test_returns_valid_index(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        scores = np.array([0.1, 0.2, 0.8])
        idx = dp.report_noisy_max(scores)
        assert 0 <= idx < 3

    def test_highest_score_wins_on_average(self) -> None:
        np.random.seed(4)
        dp = DifferentialPrivacy(epsilon=10.0)  # large ε → low noise
        scores = np.array([0.0, 0.0, 1.0])
        results = [dp.report_noisy_max(scores) for _ in range(100)]
        assert results.count(2) > 80  # Should win most of the time

    def test_invalid_sensitivity(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0)
        with pytest.raises(ValueError, match="sensitivity"):
            dp.report_noisy_max(np.array([1.0]), sensitivity=0.0)


class TestPrivatiseGradients:
    def test_output_shape_preserved(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        g = np.random.randn(128)
        out = dp.privatise_gradients(g)
        assert out.shape == (128,)

    def test_gradient_clipping_applied(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        # Very large gradient should be clipped before noise
        g = np.ones(10) * 1000.0
        # After clipping, norm should be ≈ clip_norm (before noise)
        # We can verify by setting a very tight clip and checking output norm is bounded
        out = dp.privatise_gradients(g, clip_norm=1.0)
        # Output norm bounded by clip_norm + noise magnitude; with high probability < 50
        assert np.linalg.norm(out) < 50.0  # generous bound for noisy gradient

    def test_invalid_clip_norm(self) -> None:
        dp = DifferentialPrivacy(epsilon=1.0, delta=1e-6)
        with pytest.raises(ValueError, match="clip_norm"):
            dp.privatise_gradients(np.array([1.0]), clip_norm=0.0)

    def test_small_gradient_not_clipped(self) -> None:
        dp = DifferentialPrivacy(epsilon=100.0, delta=1e-6)  # huge ε → tiny noise
        g = np.ones(4) * 0.1  # norm ≈ 0.2, well below clip_norm=1.0
        out = dp.privatise_gradients(g, clip_norm=1.0)
        # With large ε, noise is tiny; output should be close to input
        assert np.linalg.norm(out - g) < 1.0
