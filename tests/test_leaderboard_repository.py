"""Tests for LeaderboardRepository (db/leaderboard_repository.py)."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.leaderboard_repository import LeaderboardRepository
from responsibleai.leaderboard.providers import MockAdapter
from responsibleai.leaderboard.runner import LeaderboardRunner


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return LeaderboardRepository(db)


class TestModelRegistry:
    async def test_register_and_get_model(self, repo):
        stored = await repo.register_model("gpt-4o", "openai", "GPT-4o", adapter="openai")
        assert stored["model"] == "gpt-4o"
        assert stored["provider"] == "openai"
        assert stored["display_name"] == "GPT-4o"
        assert stored["active"] is True

        fetched = await repo.get_model("gpt-4o", "openai")
        assert fetched is not None
        assert fetched["id"] == stored["id"]

    async def test_register_is_idempotent_by_model_provider(self, repo):
        first = await repo.register_model("gpt-4o", "openai", "GPT-4o")
        second = await repo.register_model("gpt-4o", "openai", "GPT-4o Turbo", active=False)
        assert first["id"] == second["id"]
        assert second["display_name"] == "GPT-4o Turbo"
        assert second["active"] is False

    async def test_get_unknown_model_returns_none(self, repo):
        assert await repo.get_model("nope", "nowhere") is None

    async def test_list_models_active_only_filter(self, repo):
        await repo.register_model("a", "mock", active=True)
        await repo.register_model("b", "mock", active=False)

        all_models = await repo.list_models(active_only=False)
        active_models = await repo.list_models(active_only=True)
        assert len(all_models) == 2
        assert len(active_models) == 1
        assert active_models[0]["model"] == "a"

    async def test_set_model_active_toggles(self, repo):
        await repo.register_model("a", "mock", active=True)
        result = await repo.set_model_active("a", "mock", False)
        assert result is True
        fetched = await repo.get_model("a", "mock")
        assert fetched["active"] is False

    async def test_set_model_active_unknown_returns_false(self, repo):
        assert await repo.set_model_active("nope", "nowhere", True) is False


class TestRuns:
    async def _seed_run(self, repo, model="a", provider="mock"):
        runner = LeaderboardRunner()
        result = await runner.run_model(model, provider, MockAdapter(model=model))
        return await repo.create_run(result)

    async def test_create_and_get_run(self, repo):
        stored = await self._seed_run(repo)
        fetched = await repo.get_run(stored["id"])
        assert fetched is not None
        assert fetched["model"] == "a"
        assert fetched["overall_score"] == stored["overall_score"]
        assert "findings" in fetched

    async def test_get_unknown_run_returns_none(self, repo):
        assert await repo.get_run("does-not-exist") is None

    async def test_latest_run_returns_most_recent(self, repo):
        await self._seed_run(repo, model="a")
        second = await self._seed_run(repo, model="a")
        latest = await repo.latest_run("a", "mock")
        assert latest["id"] == second["id"]

    async def test_history_orders_newest_first(self, repo):
        first = await self._seed_run(repo, model="a")
        second = await self._seed_run(repo, model="a")
        history = await repo.history("a", "mock")
        assert [h["id"] for h in history] == [second["id"], first["id"]]

    async def test_ranked_leaderboard_only_includes_active_models_with_runs(self, repo):
        await repo.register_model("a", "mock", "Model A", active=True)
        await repo.register_model("b", "mock", "Model B", active=False)
        await repo.register_model("c", "mock", "Model C", active=True)  # no run yet

        await self._seed_run(repo, model="a")

        ranked = await repo.ranked_leaderboard()
        models_ranked = [r["model"] for r in ranked]
        assert "a" in models_ranked
        assert "b" not in models_ranked  # inactive
        assert "c" not in models_ranked  # active but never run
        assert ranked[0]["rank"] == 1

    async def test_ranked_leaderboard_sorted_by_score_desc(self, repo):
        await repo.register_model("a", "mock", active=True)
        await repo.register_model("b", "mock", active=True)
        await self._seed_run(repo, model="a")
        await self._seed_run(repo, model="b")

        ranked = await repo.ranked_leaderboard()
        scores = [r["overall_score"] for r in ranked]
        assert scores == sorted(scores, reverse=True)
