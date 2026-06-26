"""
Federated averaging (FedAvg) and Byzantine-robust aggregation.

FedAvg reference:
    McMahan et al. (2017). Communication-Efficient Learning of Deep Networks
    from Decentralized Data. AISTATS 2017.

Geometric median (Weiszfeld algorithm) for Byzantine robustness:
    Pillutla et al. (2022). Robust Aggregation for Federated Learning.
    IEEE Trans. Signal Processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np


@dataclass
class NodeUpdate:
    """A single encrypted gradient submission from one federated node."""

    node_id: str
    gradients: np.ndarray
    num_samples: int  # local dataset size, used for weighted FedAvg
    round_number: int = 0


@dataclass
class AggregationResult:
    """Result of one aggregation round."""

    round_number: int
    global_gradients: np.ndarray
    participating_nodes: list[str] = field(default_factory=list)
    aggregation_method: str = "fedavg"
    outliers_removed: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "round_number": self.round_number,
            "participating_nodes": self.participating_nodes,
            "aggregation_method": self.aggregation_method,
            "outliers_removed": self.outliers_removed,
            "gradient_norm": float(np.linalg.norm(self.global_gradients)),
        }


class FedAvgAggregator:
    """
    Implements FedAvg and optional Byzantine-robust aggregation.

    FedAvg computes the weighted average of gradients, where each node's
    weight is proportional to its local dataset size.

    For environments where adversarial nodes might submit corrupted gradients,
    the ``geometric_median`` method provides provable Byzantine fault tolerance:
    it converges to the correct result even when up to (n-1)/2 nodes are
    Byzantine (Pillutla et al. 2022).

    Parameters
    ----------
    min_nodes : int
        Minimum number of node updates required before aggregating.
    byzantine_robust : bool
        If True, use geometric median instead of FedAvg.
    weiszfeld_iterations : int
        Number of Weiszfeld iterations for geometric median approximation.
    """

    def __init__(
        self,
        min_nodes: int = 1,
        byzantine_robust: bool = False,
        weiszfeld_iterations: int = 50,
    ) -> None:
        self.min_nodes = min_nodes
        self.byzantine_robust = byzantine_robust
        self.weiszfeld_iterations = weiszfeld_iterations
        self._current_round = 0
        self._pending: list[NodeUpdate] = []

    def submit(self, update: NodeUpdate) -> None:
        """Accept a gradient update from a federated node."""
        self._pending.append(update)

    def can_aggregate(self) -> bool:
        """True when enough nodes have submitted for this round."""
        return len(self._pending) >= self.min_nodes

    def aggregate(self) -> AggregationResult:
        """
        Aggregate all pending updates and reset the queue.

        Returns
        -------
        AggregationResult
            The computed global gradients and round metadata.

        Raises
        ------
        ValueError
            If fewer than min_nodes updates have been submitted.
        """
        if len(self._pending) < self.min_nodes:
            raise ValueError(
                f"Need at least {self.min_nodes} updates, have {len(self._pending)}."
            )

        updates = list(self._pending)
        self._pending.clear()
        self._current_round += 1

        if self.byzantine_robust:
            global_grads = self._geometric_median(
                [u.gradients for u in updates]
            )
            method = "geometric_median"
            outliers = 0
        else:
            global_grads, outliers = self._fedavg(updates)
            method = "fedavg"

        return AggregationResult(
            round_number=self._current_round,
            global_gradients=global_grads,
            participating_nodes=[u.node_id for u in updates],
            aggregation_method=method,
            outliers_removed=outliers,
        )

    # ------------------------------------------------------------------
    # Core aggregation algorithms
    # ------------------------------------------------------------------

    def _fedavg(self, updates: list[NodeUpdate]) -> tuple[np.ndarray, int]:
        """
        Weighted average: Σ(n_k / n_total) · g_k

        Weights proportional to local dataset size so nodes with more
        training data have greater influence on the global update.
        """
        total_samples = sum(u.num_samples for u in updates)
        if total_samples == 0:
            total_samples = len(updates)  # fallback: uniform weights
            weights = [1.0 / total_samples for _ in updates]
        else:
            weights = [u.num_samples / total_samples for u in updates]

        global_grads = sum(
            w * u.gradients for w, u in zip(weights, updates, strict=False)  # type: ignore[misc]
        )
        return np.asarray(global_grads), 0

    def _geometric_median(
        self, vectors: list[np.ndarray], tolerance: float = 1e-5
    ) -> np.ndarray:
        """
        Approximate geometric median via the Weiszfeld algorithm.

        Initialise at the arithmetic mean, then iteratively re-weight
        each vector by the inverse of its distance to the current estimate.

        Converges to the geometric median which is robust to up to
        ⌊(n-1)/2⌋ Byzantine updates (Pillutla et al. 2022).
        """
        stacked = np.stack(vectors)
        estimate = np.mean(stacked, axis=0)

        for _ in range(self.weiszfeld_iterations):
            dists = np.array([
                np.linalg.norm(estimate - v) for v in stacked
            ])
            # Avoid division by zero: mask near-zero distances
            nonzero = dists > 1e-10
            if not np.any(nonzero):
                break
            weights = np.where(nonzero, 1.0 / dists, 0.0)
            new_estimate = np.sum(
                stacked * weights[:, np.newaxis], axis=0
            ) / np.sum(weights)
            if np.linalg.norm(new_estimate - estimate) < tolerance:
                break
            estimate = new_estimate

        return estimate

    @property
    def current_round(self) -> int:
        return self._current_round

    @property
    def pending_count(self) -> int:
        return len(self._pending)
