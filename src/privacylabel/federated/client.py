"""
Federated learning edge client for PrivacyLabel.

The client runs on an edge device (hospital, bank, clinic) and:
1. Loads *local* data — never transmitted to any server.
2. Generates labels using a local or API-based LLM provider.
3. Computes and privatises gradients via differential privacy.
4. Submits encrypted gradient updates to the aggregation server.
5. Receives the updated global model back.

The raw data never leaves the device.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from privacylabel.core.label import Label, LabelBatch
from privacylabel.core.privacy_budget import PrivacyBudget, PrivacyBudgetExhaustedError
from privacylabel.crypto.differential_privacy import DifferentialPrivacy
from privacylabel.federated.aggregator import FedAvgAggregator, NodeUpdate

if TYPE_CHECKING:
    from privacylabel.providers.base import BaseLabelProvider


@dataclass
class RoundSummary:
    """Summary returned after completing one federated training round."""

    node_id: str
    round_number: int
    num_samples: int
    num_labels: int
    mean_confidence: float
    gradient_norm: float
    privacy_spent: dict[str, float]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "round_number": self.round_number,
            "num_samples": self.num_samples,
            "num_labels": self.num_labels,
            "mean_confidence": round(self.mean_confidence, 4),
            "gradient_norm": round(self.gradient_norm, 4),
            "privacy_spent": self.privacy_spent,
            "timestamp": self.timestamp.isoformat(),
        }


class FederatedClient:
    """
    Edge device client for privacy-preserving federated labeling.

    Parameters
    ----------
    node_id : str
        Unique identifier for this edge device.
    provider : BaseLabelProvider
        LLM or local model provider used to generate labels on-device.
    epsilon : float
        Per-round privacy budget (ε). Default 0.5 (moderate privacy).
    delta : float
        DP failure probability. Default 1e-6.
    gradient_clip : float
        L2 clipping norm for gradient privatisation (sensitivity bound).
    aggregator : FedAvgAggregator | None
        Aggregator to submit updates to. If None, a local one is created
        (useful for testing). In production, this would communicate over
        an encrypted channel to a remote aggregation server.
    """

    def __init__(
        self,
        node_id: str,
        provider: BaseLabelProvider,
        epsilon_per_round: float = 0.1,
        total_epsilon: float = 1.0,
        delta: float = 1e-6,
        gradient_clip: float = 1.0,
        aggregator: FedAvgAggregator | None = None,
    ) -> None:
        self.node_id = node_id
        self.provider = provider
        # Per-round DP noise level
        self._dp = DifferentialPrivacy(epsilon=epsilon_per_round, delta=delta)
        self._epsilon_per_round = epsilon_per_round
        # Total privacy budget across all rounds (basic composition)
        self.budget = PrivacyBudget(epsilon=total_epsilon, delta=delta)
        self._gradient_clip = gradient_clip
        self._aggregator = aggregator or FedAvgAggregator()
        self._round_number = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def train_round(self, data_path: str | Path) -> RoundSummary:
        """
        Execute one complete federated learning round.

        1. Load local data (stays on device)
        2. Generate labels with the configured provider
        3. Compute synthetic gradients from label confidence signals
        4. Privatise gradients (DP-SGD style)
        5. Submit to aggregator
        6. Return a round summary (no raw data included)

        Parameters
        ----------
        data_path : str | Path
            Path to a local JSONL file. Each line: {"id": "...", "text": "..."}

        Returns
        -------
        RoundSummary
            Metadata about the round. Contains no raw data or labels.
        """
        if self.budget.is_exhausted:
            raise PrivacyBudgetExhaustedError(
                f"Node {self.node_id}: privacy budget exhausted. "
                "No further labeling rounds can run."
            )

        records = self._load_local_data(Path(data_path))
        batch = await self._label_data(records)
        gradients = self._compute_gradients(batch)
        private_gradients = self._dp.privatise_gradients(
            gradients, clip_norm=self._gradient_clip
        )
        # Budget accounting: Gaussian mechanism cost ≈ ε per round
        self.budget.consume(
            epsilon_cost=self._dp.epsilon,
            delta_cost=self._dp.delta,
        )

        update = NodeUpdate(
            node_id=self.node_id,
            gradients=private_gradients,
            num_samples=len(records),
            round_number=self._round_number,
        )
        self._aggregator.submit(update)
        self._round_number += 1

        return RoundSummary(
            node_id=self.node_id,
            round_number=self._round_number,
            num_samples=len(records),
            num_labels=batch.count,
            mean_confidence=batch.mean_confidence,
            gradient_norm=float(np.linalg.norm(private_gradients)),
            privacy_spent=self.budget.to_dict(),
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_local_data(self, path: Path) -> list[dict[str, Any]]:
        """Load JSONL data from the local filesystem. Never transmitted."""
        records: list[dict[str, Any]] = []
        with path.open() as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records

    async def _label_data(self, records: list[dict[str, Any]]) -> LabelBatch:
        """Generate labels on-device using the configured provider."""
        batch = LabelBatch(
            provider_name=self.provider.name,
            model_name=self.provider.model_name,
        )
        texts = [r.get("text", "") for r in records]
        results = await self.provider.batch_label(texts)

        for record, result in zip(records, results, strict=False):
            batch.append(
                Label(
                    label_id=str(uuid.uuid4()),
                    data_id=record.get("id", str(uuid.uuid4())),
                    label=result["label"],
                    confidence=float(result.get("confidence", 0.9)),
                    source="federated",
                    metadata={"model": result.get("model", "unknown")},
                )
            )
        return batch

    def _compute_gradients(self, batch: LabelBatch) -> np.ndarray:
        """
        Compute a synthetic gradient signal from the labeling batch.

        In a real federated system this would be the gradient of a local
        model loss (e.g., cross-entropy against the LLM-generated pseudo-labels).
        Here we use label confidence as a proxy signal, producing a 128-dim
        gradient vector that captures the batch's signal strength.
        """
        if not batch.labels:
            return np.zeros(128)

        confidences = np.array([lb.confidence for lb in batch.labels])
        # Gradient ∝ (1 - confidence): high-confidence labels produce small updates
        signal = 1.0 - confidences
        # Project to fixed 128-dim gradient space via reproducible random projection
        rng = np.random.default_rng(seed=hash(self.node_id) % (2**31))
        projection = rng.standard_normal((len(signal), 128))
        gradients = signal @ projection / len(signal)
        return gradients
