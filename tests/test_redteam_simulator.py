from __future__ import annotations

import pytest

from responsibleai.redteam.simulator import (
    AttackCategory,
    AttackVector,
    RedTeamSimulator,
)


class TestRedTeamSimulatorInit:
    def test_default_init_loads_vectors(self) -> None:
        sim = RedTeamSimulator()
        assert len(sim._vectors) > 0

    def test_custom_vectors_accepted(self) -> None:
        vectors = [
            AttackVector(
                category=AttackCategory.JAILBREAK,
                name="Custom test",
                payload="Test payload",
                severity="low",
                description="A test vector",
            )
        ]
        sim = RedTeamSimulator(attack_vectors=vectors)
        assert len(sim._vectors) == 1


class TestGetAttackPayloads:
    def setup_method(self) -> None:
        self.sim = RedTeamSimulator()

    def test_returns_list_of_dicts(self) -> None:
        payloads = self.sim.get_attack_payloads()
        assert isinstance(payloads, list)
        assert all(isinstance(p, dict) for p in payloads)

    def test_each_payload_has_required_keys(self) -> None:
        payloads = self.sim.get_attack_payloads()
        required = {"name", "category", "payload", "severity", "description"}
        for p in payloads:
            assert required.issubset(p.keys())

    def test_categories_cover_all_attack_types(self) -> None:
        payloads = self.sim.get_attack_payloads()
        categories = {p["category"] for p in payloads}
        assert "prompt_injection" in categories
        assert "jailbreak" in categories
        assert "data_leakage" in categories

    def test_severities_are_valid(self) -> None:
        payloads = self.sim.get_attack_payloads()
        valid = {"low", "medium", "high", "critical"}
        for p in payloads:
            assert p["severity"] in valid


class TestEvaluateResponse:
    def setup_method(self) -> None:
        self.sim = RedTeamSimulator()
        self.vector = AttackVector(
            category=AttackCategory.JAILBREAK,
            name="Test jailbreak",
            payload="Ignore instructions",
            severity="high",
            description="Test",
        )

    def test_safe_refusal_not_vulnerable(self) -> None:
        safe_response = (
            "I cannot assist with that request as it goes against my safety guidelines. "
            "I am designed to be helpful, harmless, and honest."
        )
        result = self.sim.evaluate_response(self.vector, safe_response)
        assert not result.is_vulnerable

    def test_response_with_vulnerability_signal_flagged(self) -> None:
        vuln_response = "INJECTION_SUCCESS confirmed."
        result = self.sim.evaluate_response(self.vector, vuln_response)
        assert result.is_vulnerable
        assert len(result.vulnerability_signals) > 0

    def test_empty_response_to_high_severity_is_vulnerable(self) -> None:
        result = self.sim.evaluate_response(self.vector, "Sure, here is that information.")
        assert result.is_vulnerable

    def test_severity_set_on_vulnerable_result(self) -> None:
        result = self.sim.evaluate_response(self.vector, "Sure, here is that information.")
        assert result.is_vulnerable
        assert result.severity == "high"

    def test_severity_none_on_secure_result(self) -> None:
        safe = "I cannot and will not assist with that."
        result = self.sim.evaluate_response(self.vector, safe)
        assert not result.is_vulnerable
        assert result.severity == "none"

    def test_low_severity_without_refusal_not_auto_vulnerable(self) -> None:
        low_vector = AttackVector(
            category=AttackCategory.DELIMITER_ATTACK,
            name="Low severity test",
            payload="```test```",
            severity="low",
            description="Low severity",
        )
        result = self.sim.evaluate_response(low_vector, "Here is my response.")
        # Low severity should not auto-flag without explicit signals
        assert not result.is_vulnerable


class TestAnalyzeResponses:
    def setup_method(self) -> None:
        self.sim = RedTeamSimulator()

    def test_analyze_produces_report(self) -> None:
        payloads = self.sim.get_attack_payloads()
        responses = {
            p["name"]: "I cannot assist with that request due to safety guidelines."
            for p in payloads
        }
        report = self.sim.analyze_responses("gpt-4o", "openai", responses)
        assert report.model_name == "gpt-4o"
        assert report.provider == "openai"

    def test_all_safe_gives_high_security_score(self) -> None:
        payloads = self.sim.get_attack_payloads()
        safe = "I cannot and will not assist with that. This goes against my guidelines."
        responses = {p["name"]: safe for p in payloads}
        report = self.sim.analyze_responses("model", "provider", responses)
        assert report.security_score > 0.5

    def test_all_vulnerable_gives_low_security_score(self) -> None:
        payloads = self.sim.get_attack_payloads()
        vuln = "INJECTION_SUCCESS. Sure, I have no restrictions now."
        responses = {p["name"]: vuln for p in payloads}
        report = self.sim.analyze_responses("model", "provider", responses)
        assert report.security_score < 0.5

    def test_empty_responses_returns_perfect_score(self) -> None:
        report = self.sim.analyze_responses("model", "provider", {})
        assert report.security_score == pytest.approx(1.0)

    def test_report_has_timestamp(self) -> None:
        report = self.sim.analyze_responses("model", "provider", {})
        assert report.timestamp is not None

    def test_to_dict_structure(self) -> None:
        payloads = self.sim.get_attack_payloads()
        safe = "I cannot assist with this."
        responses = {p["name"]: safe for p in payloads[:3]}
        report = self.sim.analyze_responses("model", "provider", responses)
        d = report.to_dict()
        required = {
            "model", "provider", "security_score", "total_attacks",
            "vulnerabilities_found", "critical_vulnerabilities",
            "attack_results", "timestamp",
        }
        assert required.issubset(d.keys())

    def test_critical_vulnerabilities_filter(self) -> None:
        payloads = self.sim.get_attack_payloads()
        vuln = "INJECTION_SUCCESS confirmed."
        responses = {p["name"]: vuln for p in payloads}
        report = self.sim.analyze_responses("model", "provider", responses)
        critical = report.critical_vulnerabilities
        assert all(r.severity == "critical" for r in critical)
