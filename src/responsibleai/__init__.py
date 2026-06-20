"""
ResponsibleAI — Enterprise AI Governance Platform.

Core governance modules:
- TrustScoreEngine      : composite AI trust metric (0-100, A-F grade)
- AIPassport            : verifiable trust certification artifact
- GuardrailsEngine      : PII detection, toxicity filtering, policy enforcement
- HallucinationDetector : factual reliability estimation
- ComplianceEngine      : NIST AI RMF, EU AI Act, ISO 42001 evaluation
- RedTeamSimulator      : automated adversarial probing

Cost Intelligence:
- CostTracker           : SQLite-backed token usage and cost tracking
- CostAnalyzer          : prompt efficiency and waste detection
- ModelRouter           : cheapest acceptable model for a given task

Drift Monitoring:
- TrustDriftMonitor     : detect trust score degradation over time
"""

from responsibleai.compliance.engine import (
    ComplianceEngine,
    ComplianceReport,
    ComplianceStatus,
    EUAIActRiskTier,
    Framework,
)
from responsibleai.cost.analyzer import CostAnalyzer
from responsibleai.cost.models import BudgetPolicy, ModelPricing, TokenUsage
from responsibleai.cost.router import ModelRouter
from responsibleai.cost.tracker import CostTracker
from responsibleai.drift.monitor import DriftAlert, TrustDriftMonitor
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
    # Trust
    "TrustScoreEngine",
    "TrustScore",
    "AIPassport",
    "PassportGenerator",
    # Guardrails
    "GuardrailsEngine",
    "GuardrailsPolicy",
    "GuardrailsResult",
    "PIICategory",
    "ToxicityCategory",
    # Hallucination
    "HallucinationDetector",
    "HallucinationResult",
    # Compliance
    "ComplianceEngine",
    "ComplianceReport",
    "ComplianceStatus",
    "EUAIActRiskTier",
    "Framework",
    # Red Team
    "RedTeamSimulator",
    "RedTeamReport",
    "AttackVector",
    "AttackCategory",
    # Cost Intelligence
    "CostTracker",
    "CostAnalyzer",
    "ModelRouter",
    "TokenUsage",
    "ModelPricing",
    "BudgetPolicy",
    # Drift
    "TrustDriftMonitor",
    "DriftAlert",
]
