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
