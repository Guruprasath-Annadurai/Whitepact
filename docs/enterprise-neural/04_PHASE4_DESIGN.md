# Phase 4 — Neural Data Classification + Privacy Boundary: Design

STATUS: Design only. No runtime code changed by this document.

## 0. Ground truth (re-confirmed before writing this doc)

`grep -ril -E "neural|BCI|EEG" src/` returns zero matches for actual
functionality — every hit in the current tree is this session's own
`docs/enterprise-neural/` cross-references. **This phase is 100% net-new
product surface**, consistent with the Phase 0 audit's original finding.
Nothing here reuses an existing neural-specific module because none
exists; it does reuse WhitePact's existing *infrastructure* wherever
sound (`governance/crypto/` for encryption, the `db/` repository
pattern for persistence), per the directive's own rule 2.

## 1. Scope of Phase 4 specifically

Per the master directive: data classification (N0-N5), the default
privacy-preserving data flow (BCI → local processing → minimal derived
`NeuralIntent` → WhitePact → LLM only if needed), a Neural Vault, a
consent ledger, retention rules, export/delete/reset controls,
application-access revocation, learning/sharing disable, a provider
data manifest, and a neural privacy policy engine — plus automated
leakage tests proving raw neural data never reaches logs, traces,
exceptions, telemetry, or an LLM request by default.

Phase 4 does **not** build a BCI device adapter (Phase 5), a decoder
(Phase 6), or intent attestation (Phase 7) — it builds the
*classification vocabulary and storage/consent/retention scaffolding*
those phases will produce and consume data through.

## 2. Data classification (N0–N5)

```python
class NeuralDataClass(StrEnum):
    N0_RAW_NEURAL = "n0_raw_neural"  # raw sensor stream
    N1_NEURAL_FEATURES = "n1_neural_features"  # processed features/embeddings
    N2_PERSONAL_NEURAL_MODEL = "n2_personal_neural_model"  # calibration, decoder params
    N3_NEURAL_INFERENCE = "n3_neural_inference"  # derived inference (attention, YES/NO, ...)
    N4_NEURAL_AUTHORITY_EVIDENCE = (
        "n4_neural_authority_evidence"  # minimal proof-of-authorization metadata
    )
    N5_OPERATIONAL_METADATA = "n5_operational_metadata"  # non-neural ops data
```

**Sensitivity tiers**, explicit, not implied:

| Class | Sensitivity | Default residency |
|---|---|---|
| N0, N1, N2 | Highest | Local device only — never transmitted by default |
| N3 | Sensitive | Local by default; may cross to WhitePact only as a minimal derived value |
| N4 | Controlled security information | May be persisted server-side (it's evidence *about* an inference, not the inference's raw content) |
| N5 | Non-neural, cannot reconstruct neural state | Ordinary operational data |

**Every data structure this phase and later phases produce must declare
its class** — enforced structurally: `NeuralPayload` (below) is a
generic wrapper that *requires* a `NeuralDataClass` at construction, not
an optional field a caller can omit.

## 3. Default data flow (privacy boundary)

```
BCI
 ↓
local device adapter          (Phase 5)
 ↓
local signal processing        (Phase 5/6)
 ↓
local personal model (N2)      — never leaves the endpoint by default
 ↓
local decoder                  (Phase 6)
 ↓
minimal derived NeuralIntent (N3) — the only thing that may cross to WhitePact
 ↓
WhitePact
 ↓
LLM, only if the action genuinely requires it, and never N0/N1/N2
```

Phase 4's job in this diagram: define `NeuralPayload`/`NeuralDataClass`
precisely enough that Phase 5/6/7 code has an unambiguous type system to
build against, and build the boundary enforcement (leakage tests,
policy engine) that makes "N0/N1/N2 never leaves local by default" a
checked property, not a convention.

## 4. Reuse map (existing WhitePact infrastructure this phase builds on)

| Need | Existing WhitePact infrastructure reused |
|---|---|
| Encrypting Neural Vault contents at rest | `governance/crypto/` — a new `KeyPurpose.NEURAL_VAULT` value, `LocalEnvelopeKeyProvider`, envelope format — same pattern as field encryption (Phase 2 Step 3), not a new crypto scheme |
| Persisting consent records, retention state, the Neural Vault index | `db/` repository pattern (SQLAlchemy Core Table + async repository class), same as every other `db/*_repository.py` |
| Tenant isolation | Existing `org_id`-scoping convention already used throughout `db/` |
| Audit trail for consent grants/revocations | `governance/evidence.py` / `EvidenceRepository` pattern, reused, not reinvented |

## 5. Core types (this step's actual deliverable)

```python
@dataclass(frozen=True)
class NeuralPayload:
    """The one wrapper type every later phase's neural data flows
    through. Requires a NeuralDataClass at construction -- there is no
    way to hold neural-shaped data without declaring its sensitivity
    class."""

    data_class: NeuralDataClass
    subject_id: str  # the human this data is about
    session_id: str
    payload: bytes  # opaque to this layer -- Phase 5/6/7 define the actual encoding
    captured_at: datetime
    device_reference: str | None = None

    def __post_init__(self) -> None:
        # N0/N1/N2 must never be constructed without an explicit
        # acknowledgement that this payload is subject to the
        # local-only default -- see NeuralVault.store()'s own
        # enforcement, not just a naming convention here.
        ...
```

`ConsentRecord`, `RetentionPolicy`, `NeuralVaultEntry` — persisted types,
detailed in the implementation step (kept out of this design doc's own
body to avoid the doc drifting from the actual code; see the Phase
Report for the final schema once built).

## 6. Neural Vault

A `NeuralVaultRepository` (same `db/*_repository.py` pattern) storing
**references and encrypted local-residency metadata for N0/N1/N2 data**
— explicitly **not** a server-side store of raw neural content by
default (that would violate the privacy boundary this phase exists to
build). What it stores server-side: which subject/session/device
combinations exist, their retention/consent state, and (only when a
user has explicitly, separately consented) an encrypted copy for
cross-device sync — a distinct, opt-in capability from the default.

## 7. Consent ledger

Distinguishes categories per the master directive: BCI connection,
local neural processing, neural-profile storage, derived-inference
sharing, external LLM sharing, research contribution, global model
training, enterprise/admin visibility. **One blanket "I agree" is
explicitly disallowed** — `ConsentRecord` is per-category, versioned,
timestamped, revocable.

## 8. Retention, export, delete, revoke

`RetentionPolicy` per data class (N0/N1/N2 default to short/no
server-side retention since they don't leave the device by default;
N3/N4/N5 get explicit, configurable retention windows). Export/delete
are real operations against the Neural Vault index and any consented
server-side copies — **deletion semantics must be explicit**: this
phase will document precisely what "delete" removes (Vault index,
consented sync copies) versus what it cannot reach (a device's own
local storage, which WhitePact doesn't control) — never claim more than
is true, per the directive's own rule 46.

## 9. Neural privacy policy engine

A `NeuralPrivacyPolicy` evaluator: given a proposed data flow (data
class, source, destination, purpose) and the subject's current consent
records, returns ALLOW/DENY — fail-closed (missing consent record =
DENY, per Law 7). This is intentionally a narrow, single-purpose policy
evaluator, not a rebuild of `governance/gateway.py`'s general policy
engine — reused conceptually (same ALLOW/DENY-with-reason shape this
codebase already established), not literally imported, since neural
consent has a genuinely different decision surface (data class ×
category, not action-type × risk-tier).

## 10. Leakage tests (the actual enforcement mechanism)

Automated tests proving N0/N1/N2 content, once it exists as test
fixtures in later phases, never appears in:
`logging` output, exception messages/tracebacks, OpenTelemetry spans,
SQL query logs, metric labels, HTTP access logs. Phase 4 itself has no
N0/N1/N2 *content* yet (no decoder exists until Phase 6) — so this
phase's own leakage tests exercise the **wrapper type's own
`__repr__`/`__str__`/logging behavior** (a `NeuralPayload` must never
render its raw `payload` bytes in a log-friendly representation) as the
concrete, testable slice of this requirement available now. Full
end-to-end leakage testing (a real decoder output never reaching an LLM
request) is necessarily Phase 6/7/8's job, once those layers exist —
flagged here, not silently assumed covered.

## 11. What Phase 4 does not do

- No BCI hardware integration (Phase 5).
- No decoder, no real N0→N3 derivation logic (Phase 6).
- No `NeuralIntentAttestation` (Phase 7).
- No claim that any of this is active in a shipped product — same
  "mechanism, not activation" honesty Phase 2 maintained throughout.

## 12. Implementation plan

1. `governance/neural/` new package: `NeuralDataClass`, `NeuralPayload`,
   `ConsentCategory`, `ConsentRecord`, exceptions.
2. `db/neural_vault_repository.py` + migration: Neural Vault index,
   consent ledger tables.
3. `governance/neural/policy.py`: the fail-closed consent-based policy
   evaluator.
4. Leakage tests for `NeuralPayload`'s own representation.
5. `docs/enterprise-neural/04_PHASE4_REPORT.md` per the mandatory
   format.

Phase 4 design complete. Proceeding to Step 1 implementation.
