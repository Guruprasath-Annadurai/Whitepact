from __future__ import annotations

import pytest

from privacylabel.core.label import Label, LabelBatch


class TestLabel:
    def test_valid_label(self) -> None:
        lb = Label(
            label_id="l1",
            data_id="d1",
            label="positive",
            confidence=0.95,
            source="llm",
        )
        assert lb.label == "positive"
        assert lb.confidence == pytest.approx(0.95)

    def test_invalid_confidence_too_high(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            Label(label_id="l", data_id="d", label="x", confidence=1.1, source="llm")

    def test_invalid_confidence_negative(self) -> None:
        with pytest.raises(ValueError, match="confidence"):
            Label(label_id="l", data_id="d", label="x", confidence=-0.1, source="llm")

    def test_invalid_source(self) -> None:
        with pytest.raises(ValueError, match="source"):
            Label(label_id="l", data_id="d", label="x", confidence=0.9, source="robot")

    def test_valid_sources(self) -> None:
        for src in ("llm", "human", "ensemble", "federated"):
            lb = Label(label_id="l", data_id="d", label="x", confidence=0.9, source=src)
            assert lb.source == src

    def test_to_dict(self) -> None:
        lb = Label(label_id="l1", data_id="d1", label="neg", confidence=0.8, source="human")
        d = lb.to_dict()
        assert d["label"] == "neg"
        assert d["confidence"] == pytest.approx(0.8)
        assert "timestamp" in d

    def test_immutable(self) -> None:
        lb = Label(label_id="l", data_id="d", label="x", confidence=0.5, source="llm")
        with pytest.raises(AttributeError):
            lb.label = "y"  # type: ignore[misc]


class TestLabelBatch:
    def test_empty_batch(self) -> None:
        batch = LabelBatch()
        assert batch.count == 0
        assert batch.mean_confidence == 0.0

    def test_append_and_count(self) -> None:
        batch = LabelBatch()
        batch.append(Label("l1", "d1", "pos", 0.9, "llm"))
        batch.append(Label("l2", "d2", "neg", 0.8, "llm"))
        assert batch.count == 2

    def test_mean_confidence(self) -> None:
        batch = LabelBatch()
        batch.append(Label("l1", "d1", "pos", 0.6, "llm"))
        batch.append(Label("l2", "d2", "neg", 0.8, "llm"))
        assert batch.mean_confidence == pytest.approx(0.7)

    def test_to_dict(self) -> None:
        batch = LabelBatch(provider_name="openai", model_name="gpt-4o")
        batch.append(Label("l1", "d1", "pos", 0.9, "llm"))
        d = batch.to_dict()
        assert d["provider"] == "openai"
        assert d["count"] == 1
        assert "labels" in d
