"""Tests for EvalRepository -- previously entirely untested (0% branch
coverage). Real DB-backed behavior against a fresh in-memory engine per
test, covering both branches of every conditional in the module."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.eval_repository import EvalRepository


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def repo(engine):
    return EvalRepository(engine)


class TestSaveAndGetRun:
    async def test_save_run_generates_id_when_absent(self, repo):
        run_id = await repo.save_run("compare", "gpt-4", {"score": 0.9})
        assert run_id

    async def test_save_run_uses_payload_id_when_present(self, repo):
        run_id = await repo.save_run("compare", "gpt-4", {"id": "custom-id", "score": 0.9})
        assert run_id == "custom-id"

    async def test_save_run_uses_payload_created_at_when_present(self, repo):
        run_id = await repo.save_run(
            "compare", "gpt-4", {"created_at": "2020-01-01T00:00:00+00:00"}
        )
        run = await repo.get_run(run_id)
        assert run["created_at"] == "2020-01-01T00:00:00+00:00"

    async def test_save_run_generates_created_at_when_absent(self, repo):
        run_id = await repo.save_run("compare", "gpt-4", {})
        run = await repo.get_run(run_id)
        assert run["created_at"]

    async def test_get_run_returns_full_payload(self, repo):
        run_id = await repo.save_run(
            "benchmark", "claude-3", {"score": 0.8, "notes": "x"}, provider="anthropic", suite="truthfulqa"
        )
        run = await repo.get_run(run_id)
        assert run["run_type"] == "benchmark"
        assert run["model"] == "claude-3"
        assert run["provider"] == "anthropic"
        assert run["suite"] == "truthfulqa"
        assert run["payload"] == {"score": 0.8, "notes": "x"}

    async def test_get_run_missing_returns_none(self, repo):
        assert await repo.get_run("nonexistent") is None


class TestListRuns:
    async def test_list_runs_no_filters(self, repo):
        await repo.save_run("compare", "model-a", {})
        await repo.save_run("compare", "model-b", {})
        runs = await repo.list_runs()
        assert len(runs) == 2

    async def test_list_runs_filtered_by_run_type(self, repo):
        await repo.save_run("compare", "model-a", {})
        await repo.save_run("benchmark", "model-a", {})
        runs = await repo.list_runs(run_type="benchmark")
        assert len(runs) == 1
        assert runs[0]["run_type"] == "benchmark"

    async def test_list_runs_filtered_by_model(self, repo):
        await repo.save_run("compare", "model-a", {})
        await repo.save_run("compare", "model-b", {})
        runs = await repo.list_runs(model="model-a")
        assert len(runs) == 1
        assert runs[0]["model"] == "model-a"

    async def test_list_runs_filtered_by_org_id(self, repo):
        await repo.save_run("compare", "model-a", {}, org_id="org-1")
        await repo.save_run("compare", "model-a", {}, org_id="org-2")
        runs = await repo.list_runs(org_id="org-1")
        assert len(runs) == 1
        assert runs[0]["org_id"] == "org-1"

    async def test_list_runs_respects_limit_and_offset(self, repo):
        for _ in range(5):
            await repo.save_run("compare", "model-a", {})
        page = await repo.list_runs(limit=2, offset=1)
        assert len(page) == 2


class TestDeleteRun:
    async def test_delete_run_returns_true_when_found(self, repo):
        run_id = await repo.save_run("compare", "model-a", {})
        assert await repo.delete_run(run_id) is True
        assert await repo.get_run(run_id) is None

    async def test_delete_run_returns_false_when_missing(self, repo):
        assert await repo.delete_run("nonexistent") is False


class TestBaselines:
    async def test_set_baseline_inserts_when_absent(self, repo):
        await repo.set_baseline("gpt-4", "truthfulqa", "accuracy", 0.85)
        baselines = await repo.get_baselines("gpt-4")
        assert baselines == {"truthfulqa:accuracy": 0.85}

    async def test_set_baseline_updates_when_present(self, repo):
        await repo.set_baseline("gpt-4", "truthfulqa", "accuracy", 0.85, org_id="org-1")
        await repo.set_baseline("gpt-4", "truthfulqa", "accuracy", 0.90, org_id="org-1")
        baselines = await repo.get_baselines("gpt-4")
        assert baselines == {"truthfulqa:accuracy": 0.90}

    async def test_get_baselines_multiple_metrics(self, repo):
        await repo.set_baseline("gpt-4", "truthfulqa", "accuracy", 0.85)
        await repo.set_baseline("gpt-4", "bbq", "bias_score", 0.1)
        baselines = await repo.get_baselines("gpt-4")
        assert baselines == {"truthfulqa:accuracy": 0.85, "bbq:bias_score": 0.1}

    async def test_get_baselines_empty_for_unknown_model(self, repo):
        assert await repo.get_baselines("no-such-model") == {}

    async def test_delete_baselines_returns_count(self, repo):
        await repo.set_baseline("gpt-4", "truthfulqa", "accuracy", 0.85)
        await repo.set_baseline("gpt-4", "bbq", "bias_score", 0.1)
        deleted = await repo.delete_baselines("gpt-4")
        assert deleted == 2
        assert await repo.get_baselines("gpt-4") == {}

    async def test_delete_baselines_zero_for_unknown_model(self, repo):
        assert await repo.delete_baselines("no-such-model") == 0
