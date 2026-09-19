# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""
ResponsibleAI — Enterprise AI Governance Platform.

Public names are resolved lazily. Isolated execution children import this
package under a STRICT 256 MiB address-space ceiling; eagerly importing
sklearn/scipy (via HallucinationDetector) is an accidental import tax and
is not required for the isolation dispatch path.
"""

from __future__ import annotations

import importlib
from typing import Any

__version__ = "1.3.0"

__all__ = [
    "TrustScoreEngine",
    "TrustScore",
    "AIPassport",
    "PassportGenerator",
    "GuardrailsEngine",
    "GuardrailsPolicy",
    "GuardrailsResult",
    "PIICategory",
    "ToxicityCategory",
    "HallucinationDetector",
    "HallucinationResult",
    "ComplianceEngine",
    "ComplianceReport",
    "ComplianceStatus",
    "EUAIActRiskTier",
    "Framework",
    "RedTeamSimulator",
    "RedTeamReport",
    "AttackVector",
    "AttackCategory",
    "CostTracker",
    "CostAnalyzer",
    "ModelRouter",
    "TokenUsage",
    "ModelPricing",
    "BudgetPolicy",
    "TrustDriftMonitor",
    "DriftAlert",
]

_EXPORTS: dict[str, tuple[str, str]] = {
    "TrustScoreEngine": ("responsibleai.trust.score", "TrustScoreEngine"),
    "TrustScore": ("responsibleai.trust.score", "TrustScore"),
    "AIPassport": ("responsibleai.trust.passport", "AIPassport"),
    "PassportGenerator": ("responsibleai.trust.passport", "PassportGenerator"),
    "GuardrailsEngine": ("responsibleai.guardrails.engine", "GuardrailsEngine"),
    "GuardrailsPolicy": ("responsibleai.guardrails.engine", "GuardrailsPolicy"),
    "GuardrailsResult": ("responsibleai.guardrails.engine", "GuardrailsResult"),
    "PIICategory": ("responsibleai.guardrails.engine", "PIICategory"),
    "ToxicityCategory": ("responsibleai.guardrails.engine", "ToxicityCategory"),
    "HallucinationDetector": ("responsibleai.hallucination.detector", "HallucinationDetector"),
    "HallucinationResult": ("responsibleai.hallucination.detector", "HallucinationResult"),
    "ComplianceEngine": ("responsibleai.compliance.engine", "ComplianceEngine"),
    "ComplianceReport": ("responsibleai.compliance.engine", "ComplianceReport"),
    "ComplianceStatus": ("responsibleai.compliance.engine", "ComplianceStatus"),
    "EUAIActRiskTier": ("responsibleai.compliance.engine", "EUAIActRiskTier"),
    "Framework": ("responsibleai.compliance.engine", "Framework"),
    "RedTeamSimulator": ("responsibleai.redteam.simulator", "RedTeamSimulator"),
    "RedTeamReport": ("responsibleai.redteam.simulator", "RedTeamReport"),
    "AttackVector": ("responsibleai.redteam.simulator", "AttackVector"),
    "AttackCategory": ("responsibleai.redteam.simulator", "AttackCategory"),
    "CostTracker": ("responsibleai.cost.tracker", "CostTracker"),
    "CostAnalyzer": ("responsibleai.cost.analyzer", "CostAnalyzer"),
    "ModelRouter": ("responsibleai.cost.router", "ModelRouter"),
    "TokenUsage": ("responsibleai.cost.models", "TokenUsage"),
    "ModelPricing": ("responsibleai.cost.models", "ModelPricing"),
    "BudgetPolicy": ("responsibleai.cost.models", "BudgetPolicy"),
    "TrustDriftMonitor": ("responsibleai.drift.monitor", "TrustDriftMonitor"),
    "DriftAlert": ("responsibleai.drift.monitor", "DriftAlert"),
}


def __getattr__(name: str) -> Any:
    spec = _EXPORTS.get(name)
    if spec is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = importlib.import_module(spec[0])
    value = getattr(module, spec[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(list(globals().keys()) + list(__all__))
