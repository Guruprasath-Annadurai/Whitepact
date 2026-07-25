"""Tests for PassportRepository — persistence behind the open Trust Index
standard's citability/verifiability guarantee (compliance/TRUST_INDEX_SPEC.md)."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.passport_repository import PassportRepository
from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScoreEngine


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return PassportRepository(db)


def _make_passport(**score_kwargs):
    engine = TrustScoreEngine()
    score = engine.compute(**score_kwargs)
    return PassportGenerator().generate("gpt-4o", "openai", score, bias_summary={"probes_run": 3})


class TestCreateAndGet:
    async def test_create_persists_and_round_trips(self, repo):
        passport = _make_passport(fairness=0.9, privacy=0.8)
        stored = await repo.create(passport, org_id=None, source="self_assessment")

        assert stored["passport_id"] == passport.passport_id
        assert stored["model"] == {"name": "gpt-4o", "provider": "openai"}
        assert stored["verification_hash"] == passport.verification_hash
        assert stored["certified"] is False
        assert stored["source"] == "self_assessment"
        assert stored["bias_summary"] == {"probes_run": 3}

    async def test_get_unknown_returns_none(self, repo):
        assert await repo.get("does-not-exist") is None

    async def test_create_records_org_id_when_present(self, repo):
        passport = _make_passport()
        stored = await repo.create(passport, org_id="org-123", source="evaluate")
        assert stored["org_id"] == "org-123"

    async def test_dimensions_round_trip_as_0_to_100_scale(self, repo):
        passport = _make_passport(fairness=1.0, privacy=0.0)
        stored = await repo.create(passport, org_id=None, source="self_assessment")
        assert stored["trust_score"]["dimensions"]["fairness"] == 100.0
        assert stored["trust_score"]["dimensions"]["privacy"] == 0.0


class TestCertification:
    async def test_certify_sets_fields(self, repo):
        passport = _make_passport()
        await repo.create(passport, org_id=None, source="self_assessment")

        certified = await repo.certify(passport.passport_id, certified_by="ResponsibleAI Certification Team")
        assert certified["certified"] is True
        assert certified["certified_by"] == "ResponsibleAI Certification Team"
        assert certified["certified_at"] is not None

    async def test_certify_unknown_passport_returns_none(self, repo):
        assert await repo.certify("does-not-exist", certified_by="x") is None

    async def test_uncertified_passport_reports_false(self, repo):
        passport = _make_passport()
        stored = await repo.create(passport, org_id=None, source="self_assessment")
        assert stored["certified"] is False
        assert stored["certified_by"] is None
        assert stored["certified_at"] is None

class TestGetLatestByModel:
    async def test_unknown_model_returns_none(self, repo):
        assert await repo.get_latest_by_model("nope", "nobody") is None

    async def test_returns_the_only_assessment(self, repo):
        passport = _make_passport(fairness=0.5)
        await repo.create(passport, org_id=None, source="self_assessment")
        found = await repo.get_latest_by_model("gpt-4o", "openai")
        assert found is not None
        assert found["passport_id"] == passport.passport_id

    async def test_exact_match_only(self, repo):
        await repo.create(_make_passport(), org_id=None, source="self_assessment")
        assert await repo.get_latest_by_model("GPT-4O", "openai") is None
        assert await repo.get_latest_by_model("gpt-4o", "OpenAI") is None

    async def test_certified_wins_over_more_recent_uncertified(self, repo):
        first = _make_passport(fairness=0.1)
        stored_first = await repo.create(first, org_id=None, source="self_assessment")
        await repo.certify(stored_first["passport_id"], certified_by="reviewer")

        second = _make_passport(fairness=0.9)
        await repo.create(second, org_id=None, source="self_assessment")

        found = await repo.get_latest_by_model("gpt-4o", "openai")
        assert found["passport_id"] == stored_first["passport_id"]
        assert found["certified"] is True

    async def test_different_model_names_are_isolated(self, repo):
        engine = TrustScoreEngine()
        score = engine.compute(fairness=0.5)
        other = PassportGenerator().generate("claude-3", "anthropic", score)
        await repo.create(other, org_id=None, source="self_assessment")

        assert await repo.get_latest_by_model("gpt-4o", "openai") is None
        found = await repo.get_latest_by_model("claude-3", "anthropic")
        assert found is not None


class TestListRecent:
    async def test_empty_by_default(self, repo):
        assert await repo.list_recent() == []

    async def test_includes_both_certified_and_self_assessed(self, repo):
        p1 = _make_passport()
        p2 = _make_passport()
        await repo.create(p1, org_id=None, source="self_assessment")
        stored2 = await repo.create(p2, org_id=None, source="self_assessment")
        await repo.certify(stored2["passport_id"], certified_by="reviewer")

        rows = await repo.list_recent()
        ids = {row["passport_id"] for row in rows}
        assert p1.passport_id in ids
        assert p2.passport_id in ids

    async def test_newest_first(self, repo):
        p1 = _make_passport()
        await repo.create(p1, org_id=None, source="self_assessment")
        p2 = _make_passport()
        await repo.create(p2, org_id=None, source="self_assessment")

        rows = await repo.list_recent()
        assert rows[0]["passport_id"] == p2.passport_id
        assert rows[1]["passport_id"] == p1.passport_id

    async def test_respects_limit_and_offset(self, repo):
        for _ in range(5):
            await repo.create(_make_passport(), org_id=None, source="self_assessment")

        page1 = await repo.list_recent(limit=2, offset=0)
        page2 = await repo.list_recent(limit=2, offset=2)
        assert len(page1) == 2
        assert len(page2) == 2
        assert {r["passport_id"] for r in page1}.isdisjoint({r["passport_id"] for r in page2})


class TestListCertified:
    async def test_list_certified_only_includes_certified(self, repo):
        p1 = _make_passport()
        p2 = _make_passport()
        await repo.create(p1, org_id=None, source="self_assessment")
        await repo.create(p2, org_id=None, source="self_assessment")
        await repo.certify(p1.passport_id, certified_by="x")

        listing = await repo.list_certified()
        ids = [row["passport_id"] for row in listing]
        assert p1.passport_id in ids
        assert p2.passport_id not in ids
