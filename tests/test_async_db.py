"""Tests for the async database layer (CostRepository + TrustRepository).

Runs against an in-memory SQLite+aiosqlite engine — no external database needed.
The same repository code works against PostgreSQL in production (just swap the URL).
"""

from __future__ import annotations

import pytest

from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.db.engine import create_engine
from responsibleai.db.repositories import CostRepository, TrustRepository
from responsibleai.trust.score import TrustScoreEngine

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def cost_repo(db):
    policy = BudgetPolicy(monthly_limit_usd=1000.0)
    return CostRepository(db, policy=policy)


@pytest.fixture()
async def trust_repo(db):
    return TrustRepository(db, alert_threshold=5.0)


@pytest.fixture()
def usage() -> TokenUsage:
    return TokenUsage.create(
        provider="openai", model="gpt-4o",
        input_tokens=1000, output_tokens=500,
    )


@pytest.fixture()
def score():
    engine = TrustScoreEngine()
    return engine.compute(
        fairness=0.80, privacy=0.85, security=0.82,
        robustness=0.78, compliance=0.90, authenticity=0.88,
    )


# ── CostRepository ────────────────────────────────────────────────────────────

class TestCostRepository:
    async def test_record_returns_cost_record(self, cost_repo, usage):
        record = await cost_repo.record(usage)
        assert record.total_cost > 0
        assert record.input_cost > 0
        assert record.output_cost > 0

    async def test_record_idempotent(self, cost_repo, usage):
        await cost_repo.record(usage)
        await cost_repo.record(usage)  # same request_id — should be ignored
        count = await cost_repo.request_count()
        assert count == 1

    async def test_total_cost_empty(self, cost_repo):
        assert await cost_repo.total_cost() == 0.0

    async def test_total_cost_accumulates(self, cost_repo):
        u1 = TokenUsage.create(provider="openai", model="gpt-4o",
                               input_tokens=1000, output_tokens=500)
        u2 = TokenUsage.create(provider="openai", model="gpt-4o",
                               input_tokens=2000, output_tokens=1000)
        await cost_repo.record(u1)
        await cost_repo.record(u2)
        total = await cost_repo.total_cost()
        assert total > 0
        await cost_repo.record(u1)  # already recorded, gets ignored
        assert total > 0

    async def test_total_tokens_returns_dict(self, cost_repo, usage):
        await cost_repo.record(usage)
        tokens = await cost_repo.total_tokens()
        assert tokens["input"] == 1000
        assert tokens["output"] == 500
        assert tokens["total"] == 1500

    async def test_request_count_with_days(self, cost_repo, usage):
        await cost_repo.record(usage)
        assert await cost_repo.request_count(days=30) == 1

    async def test_request_count_no_days(self, cost_repo, usage):
        await cost_repo.record(usage)
        assert await cost_repo.request_count() == 1

    async def test_model_breakdown(self, cost_repo):
        u1 = TokenUsage.create(provider="openai",    model="gpt-4o",      input_tokens=1000, output_tokens=500)
        u2 = TokenUsage.create(provider="anthropic", model="claude-3-5-sonnet-20241022", input_tokens=500, output_tokens=200)
        await cost_repo.record(u1)
        await cost_repo.record(u2)
        breakdown = await cost_repo.get_model_breakdown()
        assert len(breakdown) == 2
        assert any("openai" in k for k in breakdown)
        assert any("anthropic" in k for k in breakdown)

    async def test_team_breakdown(self, cost_repo):
        u1 = TokenUsage.create(provider="openai", model="gpt-4o",
                               input_tokens=500, output_tokens=200, team="eng")
        u2 = TokenUsage.create(provider="openai", model="gpt-4o",
                               input_tokens=300, output_tokens=100, team="marketing")
        await cost_repo.record(u1)
        await cost_repo.record(u2)
        breakdown = await cost_repo.get_team_breakdown()
        assert "eng" in breakdown
        assert "marketing" in breakdown

    async def test_budget_not_exceeded(self, cost_repo, usage):
        await cost_repo.record(usage)
        status = await cost_repo.check_budget()
        assert not status.is_exceeded
        assert status.monthly_limit_usd == 1000.0

    async def test_daily_costs_empty(self, cost_repo):
        daily = await cost_repo.get_daily_costs(days=7)
        assert isinstance(daily, list)

    async def test_daily_costs_with_records(self, cost_repo, usage):
        await cost_repo.record(usage)
        daily = await cost_repo.get_daily_costs(days=30)
        assert len(daily) >= 1
        assert "date" in daily[0]
        assert "cost_usd" in daily[0]

    async def test_different_providers(self, cost_repo):
        providers = [("openai", "gpt-4o"), ("anthropic", "claude-3-5-sonnet-20241022"), ("google", "gemini-1.5-pro")]
        for provider, model in providers:
            u = TokenUsage.create(provider=provider, model=model,
                                  input_tokens=100, output_tokens=50)
            await cost_repo.record(u)
        count = await cost_repo.request_count()
        assert count == 3

    async def test_total_cost_with_days_filter(self, cost_repo, usage):
        await cost_repo.record(usage)
        cost_30 = await cost_repo.total_cost(days=30)
        cost_0 = await cost_repo.total_cost(days=0)
        assert cost_30 >= cost_0


# ── TrustRepository ───────────────────────────────────────────────────────────

class TestTrustRepository:
    async def test_record_no_alert_on_first(self, trust_repo, score):
        alert = await trust_repo.record("model-a", "openai", score)
        assert alert is None

    async def test_record_no_alert_small_drop(self, trust_repo):
        engine = TrustScoreEngine()
        s1 = engine.compute(fairness=0.9, privacy=0.9, security=0.9,
                            robustness=0.9, compliance=0.9, authenticity=0.9)
        s2 = engine.compute(fairness=0.88, privacy=0.88, security=0.88,
                            robustness=0.88, compliance=0.88, authenticity=0.88)
        await trust_repo.record("m", "p", s1)
        alert = await trust_repo.record("m", "p", s2)
        assert alert is None

    async def test_record_alert_on_large_drop(self, trust_repo):
        engine = TrustScoreEngine()
        s_high = engine.compute(fairness=0.95, privacy=0.95, security=0.95,
                                robustness=0.95, compliance=0.95, authenticity=0.95)
        s_low  = engine.compute(fairness=0.50, privacy=0.50, security=0.50,
                                robustness=0.50, compliance=0.50, authenticity=0.50)
        await trust_repo.record("drift-model", "acme", s_high)
        alert = await trust_repo.record("drift-model", "acme", s_low)
        assert alert is not None
        assert alert["delta"] > 0  # positive = score dropped
        assert alert["severity"] in ("MEDIUM", "HIGH")

    async def test_history_empty(self, trust_repo):
        history = await trust_repo.history("unknown", "unknown")
        assert history == []

    async def test_history_grows(self, trust_repo, score):
        await trust_repo.record("m", "p", score)
        await trust_repo.record("m", "p", score)
        history = await trust_repo.history("m", "p")
        assert len(history) == 2

    async def test_history_respects_limit(self, trust_repo, score):
        for _ in range(10):
            await trust_repo.record("lim-model", "p", score)
        history = await trust_repo.history("lim-model", "p", limit=3)
        assert len(history) == 3

    async def test_history_record_has_expected_fields(self, trust_repo, score):
        await trust_repo.record("m", "p", score)
        record = (await trust_repo.history("m", "p"))[0]
        for field in ("overall", "grade", "risk_level", "fairness", "privacy",
                      "security", "robustness", "compliance", "authenticity", "recorded_at"):
            assert field in record

    async def test_trend_insufficient_data(self, trust_repo, score):
        await trust_repo.record("solo", "p", score)
        trend = await trust_repo.trend("solo", "p")
        assert "error" in trend

    async def test_trend_improving(self, trust_repo):
        engine = TrustScoreEngine()
        for v in [0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]:
            s = engine.compute(fairness=v, privacy=v, security=v,
                               robustness=v, compliance=v, authenticity=v)
            await trust_repo.record("upward", "p", s)
        trend = await trust_repo.trend("upward", "p")
        assert trend["direction"] in ("improving", "stable")
        assert "7d_avg" in trend
        assert "30d_avg" in trend

    async def test_trend_degrading(self, trust_repo):
        engine = TrustScoreEngine()
        for v in [0.95, 0.88, 0.80, 0.70, 0.60, 0.50]:
            s = engine.compute(fairness=v, privacy=v, security=v,
                               robustness=v, compliance=v, authenticity=v)
            await trust_repo.record("downward", "p", s)
        trend = await trust_repo.trend("downward", "p")
        assert trend["direction"] in ("degrading", "stable")

    async def test_all_models_empty(self, trust_repo):
        models = await trust_repo.all_models()
        assert models == []

    async def test_all_models_distinct(self, trust_repo, score):
        await trust_repo.record("model-a", "openai", score)
        await trust_repo.record("model-b", "openai", score)
        await trust_repo.record("model-a", "openai", score)  # duplicate pair
        models = await trust_repo.all_models()
        assert len(models) == 2
        names = {m["model_name"] for m in models}
        assert names == {"model-a", "model-b"}

    async def test_model_isolation(self, trust_repo, score):
        engine = TrustScoreEngine()
        s_high = engine.compute(fairness=0.95, privacy=0.95, security=0.95,
                                robustness=0.95, compliance=0.95, authenticity=0.95)
        s_low  = engine.compute(fairness=0.50, privacy=0.50, security=0.50,
                                robustness=0.50, compliance=0.50, authenticity=0.50)
        await trust_repo.record("model-x", "p", s_high)
        await trust_repo.record("model-x", "p", s_low)
        hist_x = await trust_repo.history("model-x", "p")
        hist_y = await trust_repo.history("model-y", "p")
        assert len(hist_x) == 2
        assert len(hist_y) == 0


# ── Engine ────────────────────────────────────────────────────────────────────

class TestCreateEngine:
    async def test_memory_url(self):
        engine = create_engine(":memory:")
        await engine.init()
        await engine.close()

    def test_postgresql_url_format(self):
        pytest.importorskip("asyncpg", reason="asyncpg not installed")
        from responsibleai.db.engine import create_engine as ce
        engine = ce("postgresql://user:pass@localhost/db")
        url_str = str(engine.raw.url)
        assert "postgresql+asyncpg" in url_str

    async def test_sqlite_file_url_format(self, tmp_path):
        db_file = str(tmp_path / "test.db")
        engine = create_engine(db_file)
        await engine.init()
        assert (tmp_path / "test.db").exists()
        await engine.close()
