# Phase 7 — Neural Intent Attestation + Action Binding: Design

STATUS: Design only. No runtime code changed by this document.

## 0. This phase is more buildable than 5/6, and why

Unlike device adapters (Phase 5) or decoders (Phase 6), attestation
itself — canonical serialization, signing, action-hash binding — is
genuinely buildable without a live decoder: it's a pure transformation
over an already-constructed `NeuralDecision` (Phase 6) plus a proposed
action, using cryptographic primitives Phase 2 already built and
tested. What Phase 7 *cannot* do without a real decoder is populate a
`NeuralIntentAttestation` with a genuine `NeuralDecision` — but it can
build, and fully test, the attestation object, its canonical
serialization, its signing/verification, and — the actual point of this
phase — the mutation-invalidates-authorization property, using
synthetic-but-structurally-valid `NeuralDecision` fixtures (which Phase
6 already makes easy to construct).

## 1. What this object proves, and what it doesn't

Per the master directive §8, stated exactly, not softened: "This object
DOES NOT prove a human thought. It proves that: a particular
authenticated decoder, using a particular model/calibration, during a
particular session, produced a particular inference, under documented
conditions." `NeuralIntentAttestation`'s own docstring repeats this
verbatim — the honesty is load-bearing, not decorative.

## 2. `NeuralIntentAttestation`

```python
@dataclass(frozen=True)
class NeuralIntentAttestation:
    schema_version: int
    attestation_id: str
    session_id: str
    subject_id: str  # "human identity reference" -- reuses NeuralDecision's subject_id concept
    decision: NeuralDecision  # embeds the full Phase 6 decision, not just a summary
    purpose: str
    target: str
    action_digest: str  # binds to the EXACT canonical action -- see Sec 3
    consent_scope: tuple[ConsentCategory, ...]
    issued_at: datetime
    expires_at: datetime
    nonce: str
    signing_key_id: KeyId  # reuses governance/crypto's KeyId, KeyPurpose.NEURAL_ATTESTATION
    signature: str
```

Reuses `governance/crypto`'s `KeyId`/`sign`/`verify` directly (Phase
2's canonical signing interface, already built, already tested) rather
than inventing new cryptography — the master directive's own rule 13
("never invent cryptography") applies exactly here. A new
`KeyPurpose.NEURAL_ATTESTATION` value is added to
`governance/crypto/types.py`'s existing enum (additive, no other
`KeyPurpose` consumer affected).

## 3. Canonical action digest — the actual security property

Per directive §9: "If ANY security-relevant field changes... the prior
authorization becomes invalid." Reuses the exact pattern
`governance/approval.py::compute_action_digest` and
`governance/authority_grant.py`'s canonical-digest convention already
established in this codebase — a canonical JSON serialization of
`(action_type, target, purpose, arguments)` hashed with SHA-256. Not a
new digest scheme; the same one this codebase already uses for
execution authorization (`governance/execution.py`'s
`ExecutionAuthorization.action_digest`), extended to neural attestation
for consistency.

## 4. `mint_neural_intent_attestation` / `verify_neural_intent_attestation`

```python
def mint_neural_intent_attestation(
    decision: NeuralDecision,
    *,
    purpose: str,
    target: str,
    action_digest: str,
    consent_scope: tuple[ConsentCategory, ...],
    dek: bytes,
    key_id: KeyId,
    ttl_seconds: float,
) -> NeuralIntentAttestation: ...


def verify_neural_intent_attestation(
    attestation: NeuralIntentAttestation,
    *,
    dek: bytes,
    current_action_digest: str,
    now: datetime,
) -> NeuralAttestationVerificationResult: ...
```

`verify_neural_intent_attestation` checks, in order, fail-closed at
every step (any failure → REJECTED, no partial-trust state):

1. Signature valid (via `governance/crypto.verify`).
2. Not expired (reuses Phase 6's `is_expired`-style check).
3. `action_digest == current_action_digest` — **the mutation test**:
   if the caller recomputes the digest for what's actually about to
   execute and it doesn't match what was attested, reject. This is the
   literal implementation of directive §9's ₹1,000→₹100,000 example.
4. Embedded `decision.status is VALID` — an AMBIGUOUS or REJECTED
   decision can never have produced a usable attestation in the first
   place (enforced again here, defense in depth, not solely relied
   upon at mint time).

## 5. What Phase 7 does not do

- No wiring into any real execution path (`governance/execution.py`
  untouched — that's a materially larger, separate integration
  decision, same "don't silently wire into the live decision path"
  discipline this session applied throughout Phase 2).
- No real `NeuralDecision` source (still Phase 6's boundary).

## 6. Implementation plan

1. `governance/crypto/types.py`: add `KeyPurpose.NEURAL_ATTESTATION`
   (additive enum value).
2. `governance/neural/attestation.py`: `NeuralIntentAttestation`,
   `NeuralAttestationVerificationResult`,
   `mint_neural_intent_attestation`, `verify_neural_intent_attestation`,
   canonical action-digest helper (reusing the existing pattern, not a
   new implementation — check whether `governance/approval.py`'s
   `compute_action_digest` can be imported directly before writing a
   parallel one).
3. Tests: mint/verify round trip, signature tamper rejection, expiry,
   the mutation-invalidates-authorization property (the actual point of
   this phase) for each security-relevant field (target, purpose,
   arguments-affecting-digest), AMBIGUOUS/REJECTED decision rejection.
4. `docs/enterprise-neural/07_PHASE7_REPORT.md`.
