"""
ResponsibleAI — Enterprise AI Governance Platform.

Three pillars:
- BiasBuster    : quantify and track LLM demographic bias
- PrivacyLabel  : federated data labeling with differential privacy
- DeepfakeDetector : media authenticity verification

Five new governance modules:
- TrustScoreEngine : composite AI trust metric (0-100, A-F grade)
- AIPassport       : verifiable trust certification artifact
- GuardrailsEngine : PII detection, toxicity filtering, policy enforcement
- HallucinationDetector : factual reliability estimation
- ComplianceEngine : NIST AI RMF, EU AI Act, ISO 42001 evaluation
- RedTeamSimulator : automated adversarial probing
"""

from responsibleai.compliance.engine import (
    ComplianceEngine,
    ComplianceReport,
    ComplianceStatus,
    EUAIActRiskTier,
    Framework,
)
from responsibleai.guardrails.engine import (
    GuardrailsEngine,
    GuardrailsPolicy,
    GuardrailsResult,
    PIICategory,
    ToxicityCategory,
)
from responsibleai.hallucination.detector import HallucinationDetector, HallucinationResult
from responsibleai.redteam.simulator import (
    AttackCategory,
    AttackVector,
    RedTeamReport,
    RedTeamSimulator,
)
from responsibleai.trust.passport import AIPassport, PassportGenerator
from responsibleai.trust.score import TrustScore, TrustScoreEngine

__version__ = "0.4.0"

__all__ = [
    "TrustScoreEngine",
    "TrustScore",
    "AIPassport",
    "PassportGenerator",
    "HallucinationDetector",
    "HallucinationResult",
    "GuardrailsEngine",
    "GuardrailsPolicy",
    "GuardrailsResult",
    "PIICategory",
    "ToxicityCategory",
    "ComplianceEngine",
    "ComplianceReport",
    "ComplianceStatus",
    "EUAIActRiskTier",
    "Framework",
    "RedTeamSimulator",
    "RedTeamReport",
    "AttackVector",
    "AttackCategory",
]
