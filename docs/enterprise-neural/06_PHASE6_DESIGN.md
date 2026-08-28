# Phase 6 — Neural Signal Integrity + Decoder Safety: Design

STATUS: Design only. No runtime code changed by this document.

## 0. Scope decision (same reasoning as Phase 5)

No real decoder exists, and building one requires either a real
trained model or real device signal to validate against — neither
exists. Per the same directive rules Phase 5 applied (§48 dependency
policy, §63 no prototypes/fake claims), **this phase does not implement
a decoder**. It builds the typed `NeuralDecision` contract (directive
§33-34) that any future decoder must produce, plus the misuse-rejection
logic (NaN/Inf, expired, wrong session/device/calibration, etc.) that
operates purely on the *shape* of a decision object — testable without
any real model, since it's input validation, not signal processing.

## 1. `NeuralDecision`

Per the master directive's own required fields:

```python
@dataclass(frozen=True)
class NeuralDecision:
    schema_version: int
    prediction: str
    calibrated_probability: float
    uncertainty: float
    signal_quality: float
    decoder_id: str
    decoder_version: str
    decoder_hash: str
    calibration_id: str
    calibration_version: str
    subject_id: str
    session_id: str
    device_reference: str
    device_trust: DeviceTrustLevel  # reuse Phase 5's type, not a new one
    issued_at: datetime
    expires_at: datetime
    status: NeuralDecisionStatus
    provenance: Mapping[str, str] = field(default_factory=dict)
```

`__post_init__` rejects, unconditionally (never merely warns):

- `calibrated_probability` not in `[0.0, 1.0]` (rejects NaN, Inf,
  negative, >1 — Python's `0.0 <= nan <= 1.0` is `False`, so a bounds
  check alone already rejects NaN without a separate `math.isnan` call,
  verified empirically before relying on it)
- `uncertainty` not in `[0.0, 1.0]`
- `signal_quality` not in `[0.0, 1.0]`
- `expires_at <= issued_at`
- empty `decoder_id`/`decoder_hash`/`calibration_id`/`subject_id`/
  `session_id`

## 2. `NeuralDecisionStatus`

```python
class NeuralDecisionStatus(StrEnum):
    VALID = "valid"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"
```

Per the master directive: "Uncertainty must not become forced intent."
A helper `classify_decision_status(calibrated_probability, uncertainty,
*, ambiguous_threshold, min_probability)` — pure function, not baked
into `__post_init__` (status is caller-assigned based on decoder-
specific thresholds `NeuralDecision` itself has no opinion on) —
returns `AMBIGUOUS` when uncertainty exceeds threshold, `REJECTED` when
probability is below the minimum, `VALID` otherwise. A `REJECTED` or
`AMBIGUOUS` decision must never be treated as a command by any later
phase — enforced by convention here (Phase 6 has no "later phase" yet
to enforce it against) but the type itself makes the status visible
and impossible to omit.

## 3. Staleness / replay / identity-mismatch checks

Pure functions operating on two `NeuralDecision`-shaped inputs or a
decision plus current context — no decoder needed:

- `is_expired(decision, *, now) -> bool`
- `matches_context(decision, *, subject_id, session_id, device_reference)
  -> bool` — wrong-user/wrong-session/wrong-device detection
- `is_stale_decoder(decision, *, current_decoder_version) -> bool`

## 4. What Phase 6 does not do

No real decoder, no real signal-quality measurement, no real
calibration data. No `NeuralPayload` → `NeuralDecision` derivation
logic (that's the actual decoder, out of scope per Sec 0).

## 5. Implementation plan

1. `governance/neural/decision.py`: `NeuralDecisionStatus`,
   `NeuralDecision`, `classify_decision_status`, `is_expired`,
   `matches_context`, `is_stale_decoder`.
2. Tests: construction validation (every NaN/Inf/out-of-range/expired
   case the directive's §7 misuse list names), status classification,
   staleness/context/decoder-version checks.
3. `docs/enterprise-neural/06_PHASE6_REPORT.md`.
