"""Phase 4 (Enterprise Neural directive) — neural data classification,
consent, and privacy-boundary scaffolding. See
`docs/enterprise-neural/04_PHASE4_DESIGN.md` for the full design.

This package builds the classification vocabulary (`NeuralDataClass`,
`NeuralPayload`) and consent policy engine that Phases 5-7 (BCI device
adapters, decoders, intent attestation — none of which exist yet, see
the design doc Sec 0/11) will produce and consume data through. It does
not itself talk to any BCI hardware or implement a decoder.
"""

from __future__ import annotations

from responsibleai.governance.neural.policy import (
    NeuralPolicyDecision,
    NeuralPolicyReason,
    NeuralPolicyResult,
    evaluate_neural_data_flow,
)
from responsibleai.governance.neural.types import (
    LOCAL_ONLY_BY_DEFAULT,
    ConsentCategory,
    ConsentRecord,
    ConsentRequiredError,
    ConsentStatus,
    NeuralDataClass,
    NeuralPayload,
    NeuralPrivacyError,
    NeuralVaultEntry,
)

__all__ = [
    "LOCAL_ONLY_BY_DEFAULT",
    "ConsentCategory",
    "ConsentRecord",
    "ConsentRequiredError",
    "ConsentStatus",
    "NeuralDataClass",
    "NeuralPayload",
    "NeuralPolicyDecision",
    "NeuralPolicyReason",
    "NeuralPolicyResult",
    "NeuralPrivacyError",
    "NeuralVaultEntry",
    "evaluate_neural_data_flow",
]
