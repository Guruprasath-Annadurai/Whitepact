"""Phase 4 (Enterprise Neural directive) — neural data classification
vocabulary. See `docs/enterprise-neural/04_PHASE4_DESIGN.md`.

Every neural-shaped value in this codebase must be wrapped in
`NeuralPayload`, which requires a `NeuralDataClass` at construction —
there is no way to hold neural-shaped data without declaring its
sensitivity class. `NeuralPayload.__repr__` deliberately never renders
`payload` bytes, so raw content can't leak through an accidental
`print()`, log line, or exception message that stringifies the object —
see `docs/enterprise-neural/04_PHASE4_DESIGN.md` Sec 10 (leakage tests).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class NeuralDataClass(StrEnum):
    """N0-N5, per the master directive's classification scheme."""

    N0_RAW_NEURAL = "n0_raw_neural"
    N1_NEURAL_FEATURES = "n1_neural_features"
    N2_PERSONAL_NEURAL_MODEL = "n2_personal_neural_model"
    N3_NEURAL_INFERENCE = "n3_neural_inference"
    N4_NEURAL_AUTHORITY_EVIDENCE = "n4_neural_authority_evidence"
    N5_OPERATIONAL_METADATA = "n5_operational_metadata"


# Classes that never leave the local device by default -- see design
# doc Sec 3. Enforcement of this lives in later phases' transport code;
# this constant is the single source of truth for "is this class
# local-only by default" that phase 5+ code must consult, not
# reimplement.
LOCAL_ONLY_BY_DEFAULT: frozenset[NeuralDataClass] = frozenset(
    {
        NeuralDataClass.N0_RAW_NEURAL,
        NeuralDataClass.N1_NEURAL_FEATURES,
        NeuralDataClass.N2_PERSONAL_NEURAL_MODEL,
    }
)


class ConsentCategory(StrEnum):
    """Per the master directive: "one blanket 'I agree' is explicitly
    disallowed" -- each category is granted/revoked independently."""

    BCI_CONNECTION = "bci_connection"
    LOCAL_PROCESSING = "local_processing"
    PROFILE_STORAGE = "profile_storage"
    INFERENCE_SHARING = "inference_sharing"
    EXTERNAL_LLM_SHARING = "external_llm_sharing"
    RESEARCH_CONTRIBUTION = "research_contribution"
    GLOBAL_MODEL_TRAINING = "global_model_training"
    ENTERPRISE_ADMIN_VISIBILITY = "enterprise_admin_visibility"


class ConsentStatus(StrEnum):
    GRANTED = "granted"
    REVOKED = "revoked"


class NeuralPrivacyError(Exception):
    """Base class for every error this package raises."""


class ConsentRequiredError(NeuralPrivacyError):
    """No granted, unrevoked `ConsentRecord` exists for the requested
    (subject, category) — fail-closed per Law 7 (missing consent must
    never become implicit ALLOW)."""

    def __init__(self, subject_id: str, category: ConsentCategory) -> None:
        self.subject_id = subject_id
        self.category = category
        super().__init__(
            f"No granted consent for subject={subject_id!r}, category={category.value!r}"
        )


@dataclass(frozen=True)
class NeuralPayload:
    """The one wrapper type neural-shaped data flows through. See
    module docstring for why `data_class` is mandatory and why
    `__repr__` never renders `payload`."""

    data_class: NeuralDataClass
    subject_id: str
    session_id: str
    payload: bytes
    captured_at: datetime
    device_reference: str | None = None

    def __post_init__(self) -> None:
        if not self.subject_id:
            raise ValueError("NeuralPayload.subject_id must be non-empty")
        if not self.session_id:
            raise ValueError("NeuralPayload.session_id must be non-empty")

    def __repr__(self) -> str:
        return (
            f"NeuralPayload(data_class={self.data_class.value!r}, "
            f"subject_id={self.subject_id!r}, session_id={self.session_id!r}, "
            f"payload=<{len(self.payload)} bytes redacted>, "
            f"captured_at={self.captured_at.isoformat()!r}, "
            f"device_reference={self.device_reference!r})"
        )

    def is_local_only_by_default(self) -> bool:
        return self.data_class in LOCAL_ONLY_BY_DEFAULT


@dataclass(frozen=True)
class ConsentRecord:
    """A single, per-category, versioned, revocable consent grant.
    Never construct one representing "consent for everything" — each
    `ConsentCategory` gets its own record."""

    consent_id: str
    subject_id: str
    organization_id: str | None
    category: ConsentCategory
    status: ConsentStatus
    version: int
    granted_at: datetime
    revoked_at: datetime | None = None

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError(f"ConsentRecord.version must be >= 1, got {self.version}")
        if self.status is ConsentStatus.REVOKED and self.revoked_at is None:
            raise ValueError("ConsentRecord.status is REVOKED but revoked_at is None")
        if self.status is ConsentStatus.GRANTED and self.revoked_at is not None:
            raise ValueError("ConsentRecord.status is GRANTED but revoked_at is set")

    @property
    def is_active(self) -> bool:
        return self.status is ConsentStatus.GRANTED
