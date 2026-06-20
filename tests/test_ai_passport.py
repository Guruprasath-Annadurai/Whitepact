from __future__ import annotations

import json

import pytest

from responsibleai.trust.passport import AIPassport, PassportGenerator
from responsibleai.trust.score import TrustScoreEngine


def _make_passport(score_kwargs: dict | None = None) -> AIPassport:
    engine = TrustScoreEngine()
    trust_score = engine.compute(**(score_kwargs or {}))
    generator = PassportGenerator()
    return generator.generate(
        model_name="gpt-4o",
        provider="openai",
        trust_score=trust_score,
    )


class TestPassportGeneration:
    def test_passport_has_uuid(self) -> None:
        passport = _make_passport()
        assert len(passport.passport_id) == 36  # UUID format
        assert "-" in passport.passport_id

    def test_passport_has_verification_hash(self) -> None:
        passport = _make_passport()
        assert len(passport.verification_hash) == 64  # SHA-256 hex

    def test_verification_hash_verifies(self) -> None:
        passport = _make_passport()
        assert passport.verify()

    def test_different_runs_produce_different_passport_ids(self) -> None:
        p1 = _make_passport()
        p2 = _make_passport()
        assert p1.passport_id != p2.passport_id

    def test_model_name_stored(self) -> None:
        passport = _make_passport()
        assert passport.model_name == "gpt-4o"

    def test_provider_stored(self) -> None:
        passport = _make_passport()
        assert passport.provider == "openai"

    def test_version_is_set(self) -> None:
        passport = _make_passport()
        assert passport.version == "1.0"

    def test_empty_summaries_default_to_empty_dicts(self) -> None:
        passport = _make_passport()
        assert passport.bias_summary == {}
        assert passport.hallucination_summary == {}
        assert passport.security_summary == {}
        assert passport.compliance_summary == {}
        assert passport.privacy_summary == {}


class TestPassportToDict:
    def test_to_dict_has_required_keys(self) -> None:
        d = _make_passport().to_dict()
        required = {
            "passport_id", "version", "model", "trust_score",
            "generated_at", "verification_hash",
        }
        assert required.issubset(d.keys())

    def test_model_sub_dict(self) -> None:
        d = _make_passport().to_dict()
        assert d["model"]["name"] == "gpt-4o"
        assert d["model"]["provider"] == "openai"

    def test_trust_score_in_dict(self) -> None:
        d = _make_passport().to_dict()
        assert "trust_score" in d["trust_score"]
        assert "grade" in d["trust_score"]

    def test_to_json_is_valid_json(self) -> None:
        passport = _make_passport()
        parsed = json.loads(passport.to_json())
        assert parsed["model"]["name"] == "gpt-4o"

    def test_json_indent_parameter(self) -> None:
        passport = _make_passport()
        compact = passport.to_json(indent=0)
        pretty = passport.to_json(indent=4)
        assert len(pretty) > len(compact)


class TestPassportToHtml:
    def test_html_contains_model_name(self) -> None:
        html = _make_passport().to_html()
        assert "gpt-4o" in html

    def test_html_contains_trust_score(self) -> None:
        engine = TrustScoreEngine()
        trust_score = engine.compute(
            fairness=1.0, privacy=1.0, security=1.0,
            robustness=1.0, compliance=1.0, authenticity=1.0,
        )
        html = PassportGenerator().generate("m", "p", trust_score).to_html()
        assert "100" in html

    def test_html_contains_verification_hash(self) -> None:
        passport = _make_passport()
        html = passport.to_html()
        assert passport.verification_hash in html

    def test_html_has_doctype(self) -> None:
        html = _make_passport().to_html()
        assert "<!DOCTYPE html>" in html


class TestPassportWithSummaries:
    def test_summaries_stored(self) -> None:
        engine = TrustScoreEngine()
        trust_score = engine.compute()
        generator = PassportGenerator()
        passport = generator.generate(
            model_name="claude-opus",
            provider="anthropic",
            trust_score=trust_score,
            bias_summary={"overall_score": 0.18, "probes_run": 3},
            compliance_summary={"status": "PARTIALLY_COMPLIANT", "violations": 2},
        )
        assert passport.bias_summary["overall_score"] == pytest.approx(0.18)
        assert passport.compliance_summary["violations"] == 2
