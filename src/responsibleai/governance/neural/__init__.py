"""Phase 4 (Enterprise Neural directive) — neural data classification,
consent, and privacy-boundary scaffolding. See
`docs/enterprise-neural/04_PHASE4_DESIGN.md` for the full design.

This package builds the classification vocabulary (`NeuralDataClass`,
`NeuralPayload`) and consent policy engine that Phases 5-7 (BCI device
adapters, decoders, intent attestation) produce and consume data
through. Phase 5 (`docs/enterprise-neural/05_PHASE5_DESIGN.md`) adds
the device trust/capability contract (`device.py`) — `DeviceTrustLevel`,
`CapabilityState`, `NeuralCapabilityManifest`, and the `BCIDeviceAdapter`
Protocol. Phase 6 (`docs/enterprise-neural/06_PHASE6_DESIGN.md`) adds
the typed decision contract (`decision.py`) — `NeuralDecision`,
`NeuralDecisionStatus`, and misuse-rejection logic (NaN/Inf, expiry,
staleness, context mismatch). Phase 7
(`docs/enterprise-neural/07_PHASE7_DESIGN.md`) adds intent attestation
(`attestation.py`) — `NeuralIntentAttestation`, minted/verified via
`governance/crypto`'s existing signing primitives, binding a decision to
an exact proposed action so that mutating any security-relevant field
invalidates the attestation. No concrete BCI hardware integration or
decoder exists yet — see `device.py`/`decision.py`'s own module
docstrings for why building either now (no real device, vendor SDK, or
trained model to validate against) would be exactly the kind of
prototype capability fabrication the master directive prohibits;
`attestation.py` is more buildable, since it's a pure transformation
over already-typed objects, not hardware/model-dependent.
"""

from __future__ import annotations

from responsibleai.governance.neural.attestation import (
    NeuralAttestationRejectReason,
    NeuralAttestationStatus,
    NeuralAttestationVerificationResult,
    NeuralIntentAttestation,
    compute_neural_action_digest,
    mint_neural_intent_attestation,
    verify_neural_intent_attestation,
)
from responsibleai.governance.neural.decision import (
    NeuralDecision,
    NeuralDecisionStatus,
    classify_decision_status,
    is_expired,
    is_stale_decoder,
    matches_context,
)
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
    "NeuralAttestationRejectReason",
    "NeuralAttestationStatus",
    "NeuralAttestationVerificationResult",
    "NeuralCapabilityManifest",
    "NeuralDataClass",
    "NeuralDecision",
    "NeuralDecisionStatus",
    "NeuralIntentAttestation",
    "NeuralPayload",
    "NeuralPolicyDecision",
    "NeuralPolicyReason",
    "NeuralPolicyResult",
    "NeuralPrivacyError",
    "NeuralVaultEntry",
    "classify_decision_status",
    "compute_neural_action_digest",
    "evaluate_neural_data_flow",
    "is_expired",
    "is_stale_decoder",
    "matches_context",
    "max_capability_state_for_trust_level",
    "mint_neural_intent_attestation",
    "verify_neural_intent_attestation",
]
