from __future__ import annotations

from dataclasses import dataclass


class PrivacyBudgetExhaustedError(Exception):
    """Raised when a DP operation would exceed the allocated privacy budget."""


@dataclass
class PrivacyBudget:
    """
    Tracks the (ε, δ)-differential privacy budget for a federated node.

    Each mechanism call consumes some epsilon and optionally some delta.
    Once the budget is exhausted, further operations should be refused.

    The Gaussian mechanism satisfies (ε, δ)-DP with δ > 0; the Laplace
    mechanism satisfies (ε, 0)-DP (pure DP, strictly stronger).

    Parameters
    ----------
    epsilon : float
        Maximum privacy loss per mechanism invocation.
    delta : float
        Failure probability for approximate DP. Use 0.0 for pure DP.
    """

    epsilon: float
    delta: float
    spent_epsilon: float = 0.0
    spent_delta: float = 0.0

    def __post_init__(self) -> None:
        if self.epsilon <= 0:
            raise ValueError(f"epsilon must be positive, got {self.epsilon}")
        if not 0.0 <= self.delta < 1.0:
            raise ValueError(f"delta must be in [0, 1), got {self.delta}")

    @property
    def remaining_epsilon(self) -> float:
        return max(0.0, self.epsilon - self.spent_epsilon)

    @property
    def remaining_delta(self) -> float:
        return max(0.0, self.delta - self.spent_delta)

    @property
    def is_exhausted(self) -> bool:
        return self.spent_epsilon >= self.epsilon

    def consume(self, epsilon_cost: float, delta_cost: float = 0.0) -> None:
        """
        Record consumption of epsilon_cost and delta_cost from the budget.

        Uses basic composition: ε-spent increases additively.
        For tighter bounds under advanced composition, replace with
        the moments accountant or Rényi DP accountant.

        Raises
        ------
        PrivacyBudgetExhaustedError
            If the requested cost would push spent_epsilon over the total.
        """
        if self.spent_epsilon + epsilon_cost > self.epsilon + 1e-10:
            raise PrivacyBudgetExhaustedError(
                f"Operation requires ε={epsilon_cost:.4f} but only "
                f"ε={self.remaining_epsilon:.4f} remains."
            )
        self.spent_epsilon += epsilon_cost
        self.spent_delta += delta_cost

    def to_dict(self) -> dict[str, float]:
        return {
            "epsilon": self.epsilon,
            "delta": self.delta,
            "spent_epsilon": round(self.spent_epsilon, 6),
            "spent_delta": round(self.spent_delta, 9),
            "remaining_epsilon": round(self.remaining_epsilon, 6),
            "remaining_delta": round(self.remaining_delta, 9),
        }
