from __future__ import annotations

from responsibleai.compliance.engine import (
    ComplianceEngine,
    ComplianceStatus,
    EUAIActRiskTier,
    Framework,
)


class TestComplianceEngineInit:
    def test_default_init(self) -> None:
        engine = ComplianceEngine()
        assert engine is not None


class TestNISTEvaluation:
    def setup_method(self) -> None:
        self.engine = ComplianceEngine()

    def test_nist_evaluation_produces_findings(self) -> None:
        report = self.engine.evaluate(
            fairness_score=0.8,
            privacy_score=0.8,
            security_score=0.8,
            robustness_score=0.8,
            compliance_maturity=0.8,
            frameworks=[Framework.NIST_AI_RMF],
        )
        nist_findings = [f for f in report.findings if f.framework == "NIST_AI_RMF"]
        assert len(nist_findings) > 0

    def test_nist_high_scores_produce_compliant_status(self) -> None:
        report = self.engine.evaluate(
            fairness_score=0.9,
            privacy_score=0.9,
            security_score=0.9,
            robustness_score=0.9,
            compliance_maturity=0.9,
            frameworks=[Framework.NIST_AI_RMF],
        )
        assert report.overall_status == ComplianceStatus.COMPLIANT

    def test_nist_low_scores_produce_non_compliant_status(self) -> None:
        report = self.engine.evaluate(
            fairness_score=0.1,
            privacy_score=0.1,
            security_score=0.1,
            robustness_score=0.1,
            compliance_maturity=0.1,
            frameworks=[Framework.NIST_AI_RMF],
        )
        assert report.overall_status == ComplianceStatus.NON_COMPLIANT

    def test_nist_control_ids_present(self) -> None:
        report = self.engine.evaluate(frameworks=[Framework.NIST_AI_RMF])
        ctrl_ids = [f.control_id for f in report.findings]
        assert "GOVERN-1.1" in ctrl_ids
        assert "MEASURE-2.2" in ctrl_ids


class TestISOEvaluation:
    def setup_method(self) -> None:
        self.engine = ComplianceEngine()

    def test_iso_evaluation_produces_findings(self) -> None:
        report = self.engine.evaluate(frameworks=[Framework.ISO_42001])
        iso_findings = [f for f in report.findings if f.framework == "ISO_42001"]
        assert len(iso_findings) > 0

    def test_iso_control_ids_present(self) -> None:
        report = self.engine.evaluate(frameworks=[Framework.ISO_42001])
        ctrl_ids = [f.control_id for f in report.findings]
        assert "ISO42001-A.6.1" in ctrl_ids
        assert "ISO42001-A.8.4" in ctrl_ids


class TestEUAIActClassification:
    def setup_method(self) -> None:
        self.engine = ComplianceEngine()

    def test_medical_use_case_classified_high_risk(self) -> None:
        report = self.engine.evaluate(
            use_case="medical diagnosis assistant",
            frameworks=[Framework.EU_AI_ACT],
        )
        assert report.eu_ai_act_tier == EUAIActRiskTier.HIGH

    def test_chatbot_classified_limited_risk(self) -> None:
        report = self.engine.evaluate(
            use_case="customer service chatbot",
            frameworks=[Framework.EU_AI_ACT],
        )
        assert report.eu_ai_act_tier == EUAIActRiskTier.LIMITED

    def test_general_use_case_minimal_risk(self) -> None:
        report = self.engine.evaluate(
            use_case="general text summarizer",
            frameworks=[Framework.EU_AI_ACT],
        )
        assert report.eu_ai_act_tier == EUAIActRiskTier.MINIMAL

    def test_social_scoring_unacceptable_risk(self) -> None:
        report = self.engine.evaluate(
            use_case="social scoring system for citizens",
            frameworks=[Framework.EU_AI_ACT],
        )
        assert report.eu_ai_act_tier == EUAIActRiskTier.UNACCEPTABLE

    def test_employment_classified_high_risk(self) -> None:
        report = self.engine.evaluate(
            use_case="AI for employment screening and recruitment",
            frameworks=[Framework.EU_AI_ACT],
        )
        assert report.eu_ai_act_tier == EUAIActRiskTier.HIGH

    def test_unacceptable_tier_produces_non_compliant(self) -> None:
        report = self.engine.evaluate(
            use_case="real-time biometric surveillance system",
            frameworks=[Framework.EU_AI_ACT],
        )
        violations = report.violations
        assert any("Art.5" in v.control_id for v in violations)


class TestMultiFrameworkEvaluation:
    def setup_method(self) -> None:
        self.engine = ComplianceEngine()

    def test_all_frameworks_evaluated_by_default(self) -> None:
        report = self.engine.evaluate()
        frameworks_seen = {f.framework for f in report.findings}
        assert "NIST_AI_RMF" in frameworks_seen
        assert "ISO_42001" in frameworks_seen
        assert "EU_AI_ACT" in frameworks_seen

    def test_compliance_score_between_zero_and_one(self) -> None:
        report = self.engine.evaluate()
        assert 0.0 <= report.compliance_score <= 1.0

    def test_violations_list(self) -> None:
        report = self.engine.evaluate(
            fairness_score=0.1,
            privacy_score=0.1,
            security_score=0.1,
            robustness_score=0.1,
            compliance_maturity=0.1,
        )
        assert len(report.violations) > 0

    def test_warnings_list(self) -> None:
        report = self.engine.evaluate(
            fairness_score=0.6,
            privacy_score=0.6,
            security_score=0.6,
            robustness_score=0.6,
            compliance_maturity=0.6,
        )
        assert len(report.warnings) > 0

    def test_to_dict_structure(self) -> None:
        report = self.engine.evaluate()
        d = report.to_dict()
        required = {
            "compliance_score", "overall_status", "frameworks_evaluated",
            "total_controls", "violations", "warnings", "findings", "timestamp",
        }
        assert required.issubset(d.keys())

    def test_to_dict_findings_have_required_keys(self) -> None:
        report = self.engine.evaluate(frameworks=[Framework.NIST_AI_RMF])
        d = report.to_dict()
        finding = d["findings"][0]
        assert "framework" in finding
        assert "control_id" in finding
        assert "status" in finding
        assert "recommendation" in finding
