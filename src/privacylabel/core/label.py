from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Label:
    """A single labeling result produced by a model or human annotator."""

    label_id: str
    data_id: str
    label: str
    confidence: float
    source: str  # "llm", "human", "ensemble"
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"confidence must be in [0, 1], got {self.confidence}")
        if self.source not in ("llm", "human", "ensemble", "federated"):
            raise ValueError(f"Unknown source {self.source!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "label_id": self.label_id,
            "data_id": self.data_id,
            "label": self.label,
            "confidence": round(self.confidence, 4),
            "source": self.source,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class LabelBatch:
    """A collection of labels produced in one labeling pass."""

    labels: list[Label] = field(default_factory=list)
    provider_name: str = "unknown"
    model_name: str = "unknown"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def append(self, label: Label) -> None:
        self.labels.append(label)

    @property
    def count(self) -> int:
        return len(self.labels)

    @property
    def mean_confidence(self) -> float:
        if not self.labels:
            return 0.0
        return sum(lb.confidence for lb in self.labels) / len(self.labels)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "count": self.count,
            "mean_confidence": round(self.mean_confidence, 4),
            "timestamp": self.timestamp.isoformat(),
            "labels": [lb.to_dict() for lb in self.labels],
        }
