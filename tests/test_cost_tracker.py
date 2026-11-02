"""Tests for CostTracker."""

from __future__ import annotations

import pytest

from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.cost.tracker import CostTracker


@pytest.fixture()
def tracker() -> CostTracker:
    return CostTracker()  # in-memory


@pytest.fixture()
def usage() -> TokenUsage:
    return TokenUsage.create(
        provider="openai",
        model="gpt-4o",
        input_tokens=1000,
        output_tokens=500,
    )


class TestRecord:
    def test_record_returns_cost_record(self, tracker, usage):
        record = tracker.record(usage)
        assert record.total_cost > 0
        assert record.input_cost > 0
        assert record.output_cost > 0

    def test_cost_calculation_openai_gpt4o(self, tracker):
        usage = TokenUsage.create("openai", "gpt-4o", input_tokens=1_000_000, output_tokens=0)
        record = tracker.record(usage)
        assert abs(record.input_cost - 2.50) < 0.001  # $2.50 per 1M input

    def test_cost_calculation_output_tokens(self, tracker):
        usage = TokenUsage.create("openai", "gpt-4o", input_tokens=0, output_tokens=1_000_000)
        record = tracker.record(usage)
        assert abs(record.output_cost - 10.0) < 0.001  # $10 per 1M output

    def test_local_model_zero_cost(self, tracker):
        usage = TokenUsage.create("ollama", "llama3.2", input_tokens=10_000, output_tokens=5_000)
        record = tracker.record(usage)
        assert record.total_cost == 0.0

    def test_duplicate_request_id_ignored(self, tracker, usage):
        tracker.record(usage)
        tracker.record(usage)  # same request_id → INSERT OR IGNORE
        assert tracker.request_count() == 1

    def test_record_to_dict(self, tracker, usage):
        record = tracker.record(usage)
        d = record.to_dict()
        assert "request_id" in d
        assert "total_cost_usd" in d
        assert d["provider"] == "openai"


class TestTotals:
    def test_total_cost_increases_with_records(self, tracker):
        for _ in range(5):
            tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500))
        assert tracker.total_cost() > 0

    def test_total_tokens(self, tracker):
        tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500))
        tokens = tracker.total_tokens()
        assert tokens["input"] == 1000
        assert tokens["output"] == 500
        assert tokens["total"] == 1500

    def test_request_count(self, tracker):
        for _ in range(3):
            tracker.record(TokenUsage.create("openai", "gpt-4o", 100, 50))
        assert tracker.request_count() == 3

    def test_model_breakdown(self, tracker):
        tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500))
        tracker.record(TokenUsage.create("anthropic", "claude-haiku-4", 1000, 500))
        bd = tracker.get_model_breakdown()
        assert "openai/gpt-4o" in bd
        assert "anthropic/claude-haiku-4" in bd

    def test_team_breakdown(self, tracker):
        tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500, team="ml-team"))
        tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500, team="data-team"))
        bd = tracker.get_team_breakdown()
        assert "ml-team" in bd
        assert "data-team" in bd


class TestBudget:
    def test_budget_not_exceeded(self):
        policy = BudgetPolicy(monthly_limit_usd=1000.0)
        tracker = CostTracker(policy=policy)
        tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500))
        status = tracker.check_budget()
        assert not status.is_exceeded
        assert status.total_spent_usd < 1000.0

    def test_budget_exceeded(self):
        policy = BudgetPolicy(monthly_limit_usd=0.001)
        tracker = CostTracker(policy=policy)
        tracker.record(TokenUsage.create("openai", "gpt-4o", 10_000, 5_000))
        status = tracker.check_budget()
        assert status.is_exceeded

    def test_budget_status_to_dict(self):
        tracker = CostTracker()
        status = tracker.check_budget()
        d = status.to_dict()
        assert "total_spent_usd" in d
        assert "percentage_used" in d
        assert "is_exceeded" in d

    def test_monthly_summary(self, tracker):
        tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500))
        summary = tracker.monthly_summary()
        assert "total_cost_usd" in summary
        assert "total_requests" in summary
        assert summary["total_requests"] >= 0


class TestDailyCosts:
    def test_daily_costs_returns_list(self, tracker):
        tracker.record(TokenUsage.create("openai", "gpt-4o", 1000, 500))
        daily = tracker.get_daily_costs(days=30)
        assert isinstance(daily, list)
        if daily:
            assert "date" in daily[0]
            assert "cost_usd" in daily[0]
