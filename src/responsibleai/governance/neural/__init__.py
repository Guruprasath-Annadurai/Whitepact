"""Phase 4 (Enterprise Neural directive) — neural data classification,
consent, and privacy-boundary scaffolding. See
`docs/enterprise-neural/04_PHASE4_DESIGN.md` for the full design.

This package builds the classification vocabulary (`NeuralDataClass`,
`NeuralPayload`) and consent policy engine that Phases 5-7 (BCI device
adapters, decoders, intent attestation) produce and consume data
through. Phase 5 (`docs/enterprise-neural/05_PHASE5_DESIGN.md`) adds
the device trust/capability contract (`device.py`) — `DeviceTrustLevel`,
`CapabilityState`, `NeuralCapabilityManifest`, and the `BCIDeviceAdapter`
Protocol. No concrete BCI hardware integration exists yet — see
`device.py`'s own module docstring for why building one now (no real
device or vendor SDK to validate against) would be exactly the kind of
prototype capability fabrication the master directive prohibits.
"""

from __future__ import annotations

from responsibleai.governance.neural.device import (
    BCIDeviceAdapter,
    CapabilityState,
    DeviceTrustLevel,
    NeuralCapabilityManifest,
    max_capability_state_for_trust_level,
)
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
    "BCIDeviceAdapter",
    "CapabilityState",
    "ConsentCategory",
    "ConsentRecord",
    "ConsentRequiredError",
    "ConsentStatus",
    "DeviceTrustLevel",
    "NeuralCapabilityManifest",
    "NeuralDataClass",
    "NeuralPayload",
    "NeuralPolicyDecision",
    "NeuralPolicyReason",
    "NeuralPolicyResult",
    "NeuralPrivacyError",
    "NeuralVaultEntry",
    "evaluate_neural_data_flow",
    "max_capability_state_for_trust_level",
]
