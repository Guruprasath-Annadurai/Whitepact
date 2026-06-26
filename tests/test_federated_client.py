from __future__ import annotations

import json
from pathlib import Path

import pytest

from privacylabel.core.privacy_budget import PrivacyBudgetExhaustedError
from privacylabel.federated.aggregator import FedAvgAggregator
from privacylabel.federated.client import FederatedClient, RoundSummary
from privacylabel.providers.base import BaseLabelProvider, LabelRequest, LabelResponse

# ------------------------------------------------------------------
# Mock provider
# ------------------------------------------------------------------

class _MockProvider(BaseLabelProvider):
    def __init__(self, label: str = "positive", confidence: float = 0.9) -> None:
        self._label = label
        self._confidence = confidence

    @property
    def name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-1.0"

    async def label(self, request: LabelRequest) -> LabelResponse:
        return LabelResponse(
            label=self._label,
            confidence=self._confidence,
            model=self.model_name,
            provider=self.name,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

class TestFederatedClientInit:
    def test_default_budget(self) -> None:
        client = FederatedClient("node-1", _MockProvider())
        assert client.budget.epsilon == 1.0
        assert client.budget.delta == 1e-6

    def test_custom_epsilon(self) -> None:
        client = FederatedClient("node-1", _MockProvider(), total_epsilon=1.0)
        assert client.budget.epsilon == 1.0

    def test_node_id_stored(self) -> None:
        client = FederatedClient("hospital-01", _MockProvider())
        assert client.node_id == "hospital-01"


class TestFederatedClientTrainRound:
    @pytest.mark.asyncio
    async def test_basic_round_returns_summary(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [
            {"id": "1", "text": "Patient report: normal."},
            {"id": "2", "text": "Patient report: elevated."},
        ])
        client = FederatedClient("node-1", _MockProvider())
        summary = await client.train_round(data)
        assert isinstance(summary, RoundSummary)
        assert summary.num_samples == 2
        assert summary.num_labels == 2

    @pytest.mark.asyncio
    async def test_round_increments_round_number(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Hello."}])
        # total_epsilon=2.0 with default epsilon_per_round=0.1 supports many rounds
        client = FederatedClient("node-1", _MockProvider(), total_epsilon=2.0)
        s1 = await client.train_round(data)
        assert s1.round_number == 1
        s2 = await client.train_round(data)
        assert s2.round_number == 2

    @pytest.mark.asyncio
    async def test_privacy_budget_consumed_per_round(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Test."}])
        client = FederatedClient("node-1", _MockProvider())
        assert client.budget.spent_epsilon == 0.0
        await client.train_round(data)
        assert client.budget.spent_epsilon > 0.0

    @pytest.mark.asyncio
    async def test_exhausted_budget_raises(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Test."}])
        # total_epsilon == epsilon_per_round so budget is exhausted after exactly one round
        client = FederatedClient("node-1", _MockProvider(), epsilon_per_round=0.1, total_epsilon=0.1)
        await client.train_round(data)  # spends 0.1, now exhausted
        with pytest.raises(PrivacyBudgetExhaustedError):
            await client.train_round(data)

    @pytest.mark.asyncio
    async def test_summary_has_gradient_norm(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Hello world."}])
        client = FederatedClient("node-1", _MockProvider())
        summary = await client.train_round(data)
        assert summary.gradient_norm >= 0.0

    @pytest.mark.asyncio
    async def test_summary_has_privacy_info(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Text."}])
        client = FederatedClient("node-1", _MockProvider())
        summary = await client.train_round(data)
        assert "spent_epsilon" in summary.privacy_spent

    @pytest.mark.asyncio
    async def test_node_id_in_summary(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Test."}])
        client = FederatedClient("bank-branch-5", _MockProvider())
        summary = await client.train_round(data)
        assert summary.node_id == "bank-branch-5"

    @pytest.mark.asyncio
    async def test_update_submitted_to_aggregator(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Test."}])
        aggregator = FedAvgAggregator()
        client = FederatedClient("node-1", _MockProvider(), aggregator=aggregator)
        assert aggregator.pending_count == 0
        await client.train_round(data)
        assert aggregator.pending_count == 1

    @pytest.mark.asyncio
    async def test_summary_to_dict(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        _write_jsonl(data, [{"id": "1", "text": "Hello."}])
        client = FederatedClient("node-1", _MockProvider())
        summary = await client.train_round(data)
        d = summary.to_dict()
        assert "node_id" in d
        assert "round_number" in d
        assert "num_samples" in d
        assert "timestamp" in d

    @pytest.mark.asyncio
    async def test_multiple_samples(self, tmp_path: Path) -> None:
        data = tmp_path / "data.jsonl"
        records = [{"id": str(i), "text": f"Sample text number {i}."} for i in range(20)]
        _write_jsonl(data, records)
        client = FederatedClient("node-1", _MockProvider())
        summary = await client.train_round(data)
        assert summary.num_samples == 20
        assert summary.num_labels == 20


class TestProviderBase:
    def test_base_provider_repr(self) -> None:
        p = _MockProvider()
        assert "mock" in repr(p).lower()

    @pytest.mark.asyncio
    async def test_batch_label_default_impl(self) -> None:
        p = _MockProvider(label="neutral", confidence=0.85)
        results = await p.batch_label(["text one", "text two"])
        assert len(results) == 2
        assert results[0]["label"] == "neutral"
        assert results[1]["confidence"] == pytest.approx(0.85)

    def test_label_request_defaults(self) -> None:
        req = LabelRequest(text="hello")
        assert req.temperature == 0.0
        assert req.max_tokens == 64

    def test_label_response_fields(self) -> None:
        resp = LabelResponse(label="pos", confidence=0.9, model="m", provider="p")
        assert resp.label == "pos"
        assert resp.input_tokens is None
