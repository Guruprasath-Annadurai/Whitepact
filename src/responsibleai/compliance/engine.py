"""
Compliance Engine — evaluate AI systems against major governance frameworks.

Frameworks:
- NIST AI RMF (GOVERN, MAP, MEASURE, MANAGE)
- EU AI Act (Annex III risk tier classification + Article controls)
- ISO 42001 (AI management system controls)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class Framework(StrEnum):
    NIST_AI_RMF = "NIST_AI_RMF"
    EU_AI_ACT = "EU_AI_ACT"
    ISO_42001 = "ISO_42001"


class EUAIActRiskTier(StrEnum):
    UNACCEPTABLE = "UNACCEPTABLE"
    HIGH = "HIGH"
    LIMITED = "LIMITED"
    MINIMAL = "MINIMAL"


class ComplianceStatus(StrEnum):
    COMPLIANT = "COMPLIANT"
    PARTIALLY_COMPLIANT = "PARTIALLY_COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    NOT_ASSESSED = "NOT_ASSESSED"


@dataclass(frozen=True)
class ComplianceFinding:
    framework: str
    control_id: str
    control_name: str
    status: ComplianceStatus
    score: float
    evidence: str
    recommendation: str


@dataclass
class ComplianceReport:
    """Results of a multi-framework compliance evaluation."""

    frameworks: list[Framework]
    findings: list[ComplianceFinding]
    overall_status: ComplianceStatus
    compliance_score: float
    eu_ai_act_tier: EUAIActRiskTier | None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def violations(self) -> list[ComplianceFinding]:
        return [f for f in self.findings if f.status == ComplianceStatus.NON_COMPLIANT]

    @property
    def warnings(self) -> list[ComplianceFinding]:
        return [
            f for f in self.findings if f.status == ComplianceStatus.PARTIALLY_COMPLIANT
        ]

    def to_dict(self) -> dict[str, Any]:
        return {
            "compliance_score": round(self.compliance_score * 100, 2),
            "overall_status": self.overall_status.value,
            "eu_ai_act_tier": self.eu_ai_act_tier.value if self.eu_ai_act_tier else None,
            "frameworks_evaluated": [f.value for f in self.frameworks],
            "total_controls": len(self.findings),
            "violations": len(self.violations),
            "warnings": len(self.warnings),
            "findings": [
                {
                    "framework": f.framework,
                    "control_id": f.control_id,
                    "control_name": f.control_name,
                    "status": f.status.value,
                    "score": round(f.score * 100, 1),
                    "recommendation": f.recommendation,
                }
                for f in self.findings
            ],
            "timestamp": self.timestamp.isoformat(),
        }


# (control_id, control_name, dimension_key)
_NIST_CONTROLS: list[tuple[str, str, str]] = [
    ("GOVERN-1.1", "AI risk management policies and procedures", "compliance"),
    ("GOVERN-1.2", "Accountability and transparency structures", "compliance"),
    ("GOVERN-6.1", "Policies for responsible AI deployment", "compliance"),
    ("MAP-1.1", "AI system context and use case categorisation", "fairness"),
    ("MAP-2.1", "Bias and fairness risks identified", "fairness"),
    ("MAP-5.1", "Privacy risks identified and documented", "privacy"),
    ("MEASURE-1.1", "AI risk measurement and quantification", "compliance"),
    ("MEASURE-2.2", "Bias and fairness evaluation conducted", "fairness"),
    ("MEASURE-2.5", "Privacy-preserving methods evaluated", "privacy"),
    ("MEASURE-2.6", "Security testing against adversarial inputs", "security"),
    ("MEASURE-2.7", "Robustness and reliability testing", "robustness"),
    ("MANAGE-1.1", "Risk treatments applied and documented", "compliance"),
    ("MANAGE-2.2", "Bias mitigation measures implemented", "fairness"),
    ("MANAGE-4.1", "Monitoring and drift detection in place", "robustness"),
]

_ISO_CONTROLS: list[tuple[str, str, str]] = [
    ("ISO42001-A.6.1", "Risk assessment process for AI systems", "compliance"),
    ("ISO42001-A.6.2", "AI system impact assessment", "fairness"),
    ("ISO42001-A.6.3", "Data management, quality, and governance", "privacy"),
    ("ISO42001-A.7.2", "Competence and awareness for AI risks", "compliance"),
    ("ISO42001-A.8.1", "Transparency of AI system operations", "compliance"),
    ("ISO42001-A.8.4", "Bias evaluation and fairness assessment", "fairness"),
    ("ISO42001-A.9.1", "Incident management and corrective actions", "security"),
    ("ISO42001-A.10.1", "Continual improvement of AI governance", "robustness"),
]

_EU_HIGH_RISK_KEYWORDS = [
    "biometric", "critical infrastructure", "education", "employment",
    "essential services", "credit scoring", "law enforcement", "border control",
    "administration of justice", "medical", "healthcare", "recruitment",
    "worker management", "public safety",
]
_EU_UNACCEPTABLE_KEYWORDS = [
    "social scoring", "real-time biometric surveillance",
    "subliminal manipulation", "exploit vulnerabilities of persons",
    "emotion recognition in workplace",
]
_EU_LIMITED_KEYWORDS = [
    "chatbot", "customer service bot", "virtual assistant",
    "support bot", "conversational ai",
]


class ComplianceEngine:
    """
    Evaluate an AI system against NIST AI RMF, EU AI Act, and ISO 42001.

    All dimension scores are in [0, 1] where 1 = fully compliant / trustworthy.
    """

    def evaluate(
        self,
        *,
        fairness_score: float = 0.5,
        privacy_score: float = 0.5,
        security_score: float = 0.5,
        robustness_score: float = 0.5,
        compliance_maturity: float = 0.5,
        use_case: str = "general",
        frameworks: list[Framework] | None = None,
    ) -> ComplianceReport:
        """
        Parameters
        ----------
        fairness_score : float
            1 = no detected bias.
        privacy_score : float
            1 = strong privacy protections in place.
        security_score : float
            1 = fully secure against adversarial probing.
        robustness_score : float
            1 = highly reliable, no hallucination.
        compliance_maturity : float
            0-1 representing governance process maturity.
        use_case : str
            Natural-language description used for EU AI Act tier classification.
        frameworks : list[Framework] | None
            Subset of frameworks to evaluate (default: all three).
        """
        requested = frameworks or list(Framework)
        scores = {
            "fairness": fairness_score,
            "privacy": privacy_score,
            "security": security_score,
            "robustness": robustness_score,
            "compliance": compliance_maturity,
        }

        findings: list[ComplianceFinding] = []

        if Framework.NIST_AI_RMF in requested:
            findings.extend(self._nist_findings(scores))

        if Framework.ISO_42001 in requested:
            findings.extend(self._iso_findings(scores))

        eu_tier: EUAIActRiskTier | None = None
        if Framework.EU_AI_ACT in requested:
            eu_tier = self._classify_eu_tier(use_case)
            findings.extend(self._eu_findings(eu_tier, scores))

        if findings:
            passing = sum(1 for f in findings if f.status == ComplianceStatus.COMPLIANT)
            compliance_score = passing / len(findings)
        else:
            compliance_score = 0.0

        if compliance_score >= 0.80:
            overall = ComplianceStatus.COMPLIANT
        elif compliance_score >= 0.50:
            overall = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            overall = ComplianceStatus.NON_COMPLIANT

        return ComplianceReport(
            frameworks=requested,
            findings=findings,
            overall_status=overall,
            compliance_score=compliance_score,
            eu_ai_act_tier=eu_tier,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _status(self, score: float) -> ComplianceStatus:
        if score >= 0.75:
            return ComplianceStatus.COMPLIANT
        if score >= 0.50:
            return ComplianceStatus.PARTIALLY_COMPLIANT
        return ComplianceStatus.NON_COMPLIANT

    def _rec(self, control_id: str, score: float, dim: str) -> str:
        if score >= 0.75:
            return f"Meets {control_id} requirements. Continue periodic review."
        if score >= 0.50:
            return (
                f"Partially meets {control_id}. Strengthen {dim} controls and "
                "document evidence for the next audit cycle."
            )
        return (
            f"Does not meet {control_id}. Immediate remediation required: "
            f"implement {dim} evaluation and mitigation procedures."
        )

    def _nist_findings(self, scores: dict[str, float]) -> list[ComplianceFinding]:
        return [
            ComplianceFinding(
                framework=Framework.NIST_AI_RMF.value,
                control_id=ctrl_id,
                control_name=ctrl_name,
                status=self._status(scores.get(dim, 0.5)),
                score=scores.get(dim, 0.5),
                evidence=f"{dim.title()} score: {scores.get(dim, 0.5):.2f}",
                recommendation=self._rec(ctrl_id, scores.get(dim, 0.5), dim),
            )
            for ctrl_id, ctrl_name, dim in _NIST_CONTROLS
        ]

    def _iso_findings(self, scores: dict[str, float]) -> list[ComplianceFinding]:
        return [
            ComplianceFinding(
                framework=Framework.ISO_42001.value,
                control_id=ctrl_id,
                control_name=ctrl_name,
                status=self._status(scores.get(dim, 0.5)),
                score=scores.get(dim, 0.5),
                evidence=f"{dim.title()} score: {scores.get(dim, 0.5):.2f}",
                recommendation=self._rec(ctrl_id, scores.get(dim, 0.5), dim),
            )
            for ctrl_id, ctrl_name, dim in _ISO_CONTROLS
        ]

    def _classify_eu_tier(self, use_case: str) -> EUAIActRiskTier:
        uc = use_case.lower()
        if any(kw in uc for kw in _EU_UNACCEPTABLE_KEYWORDS):
            return EUAIActRiskTier.UNACCEPTABLE
        if any(kw in uc for kw in _EU_HIGH_RISK_KEYWORDS):
            return EUAIActRiskTier.HIGH
        if any(kw in uc for kw in _EU_LIMITED_KEYWORDS):
            return EUAIActRiskTier.LIMITED
        return EUAIActRiskTier.MINIMAL

    def _eu_findings(
        self, tier: EUAIActRiskTier, scores: dict[str, float]
    ) -> list[ComplianceFinding]:
        if tier == EUAIActRiskTier.UNACCEPTABLE:
            return [
                ComplianceFinding(
                    framework=Framework.EU_AI_ACT.value,
                    control_id="EU-AI-ACT-Art.5",
                    control_name="Prohibited AI practices (Art. 5)",
                    status=ComplianceStatus.NON_COMPLIANT,
                    score=0.0,
                    evidence=f"Use case classified as {tier.value}",
                    recommendation=(
                        "This use case falls under prohibited AI practices (Article 5). "
                        "Deployment in the EU is not permitted."
                    ),
                )
            ]

        if tier == EUAIActRiskTier.HIGH:
            return [
                ComplianceFinding(
                    framework=Framework.EU_AI_ACT.value,
                    control_id="EU-AI-ACT-Art.9",
                    control_name="Risk management system (Art. 9)",
                    status=self._status(scores.get("compliance", 0.5)),
                    score=scores.get("compliance", 0.5),
                    evidence="High-risk AI: documented risk management system required",
                    recommendation=(
                        "Establish and maintain a documented risk management system "
                        "per Article 9 of the EU AI Act."
                    ),
                ),
                ComplianceFinding(
                    framework=Framework.EU_AI_ACT.value,
                    control_id="EU-AI-ACT-Art.10",
                    control_name="Data governance (Art. 10)",
                    status=self._status(scores.get("privacy", 0.5)),
                    score=scores.get("privacy", 0.5),
                    evidence="High-risk AI: training data documentation required",
                    recommendation=(
                        "Document training data provenance, quality criteria, and "
                        "bias mitigation per Article 10."
                    ),
                ),
                ComplianceFinding(
                    framework=Framework.EU_AI_ACT.value,
                    control_id="EU-AI-ACT-Art.13",
                    control_name="Transparency and information (Art. 13)",
                    status=self._status(scores.get("fairness", 0.5)),
                    score=scores.get("fairness", 0.5),
                    evidence="High-risk AI: transparency obligations apply",
                    recommendation=(
                        "Provide clear instructions for use and maintain technical "
                        "documentation per Article 13."
                    ),
                ),
                ComplianceFinding(
                    framework=Framework.EU_AI_ACT.value,
                    control_id="EU-AI-ACT-Art.15",
                    control_name="Accuracy, robustness, cybersecurity (Art. 15)",
                    status=self._status(
                        (scores.get("robustness", 0.5) + scores.get("security", 0.5)) / 2
                    ),
                    score=(scores.get("robustness", 0.5) + scores.get("security", 0.5)) / 2,
                    evidence="High-risk AI: accuracy and security requirements apply",
                    recommendation=(
                        "Demonstrate accuracy benchmarks and implement cybersecurity "
                        "measures per Article 15."
                    ),
                ),
            ]

        if tier == EUAIActRiskTier.LIMITED:
            return [
                ComplianceFinding(
                    framework=Framework.EU_AI_ACT.value,
                    control_id="EU-AI-ACT-Art.52",
                    control_name="Transparency obligations (Art. 52)",
                    status=ComplianceStatus.PARTIALLY_COMPLIANT,
                    score=0.7,
                    evidence="Limited-risk AI: user disclosure obligation applies",
                    recommendation=(
                        "Ensure users are informed they are interacting with an AI system "
                        "per Article 52 transparency obligations."
                    ),
                )
            ]

        # MINIMAL
        return [
            ComplianceFinding(
                framework=Framework.EU_AI_ACT.value,
                control_id="EU-AI-ACT-MinimalRisk",
                control_name="Minimal risk — voluntary codes of conduct",
                status=ComplianceStatus.COMPLIANT,
                score=1.0,
                evidence="Minimal-risk AI: no mandatory EU AI Act obligations",
                recommendation=(
                    "No mandatory obligations for this risk tier. "
                    "Consider adopting voluntary codes of conduct."
                ),
            )
        ]
