# Phase 16 — Neural Scientific Evidence System: Design

## Objective

Per the master directive's Phase 16 ("Neural Scientific Evidence
System") — grouped with the neural/BCI track (Phases 4-7) since Phase
0's audit confirmed zero pre-existing neural/BCI code of any kind.
Same discipline as Phases 5-6: build the typed contract a real system
would need, do not fabricate a capability (a study, a measurement, a
device) that doesn't exist.

## Audit: the exact gap already named, not yet closed

`governance/neural/device.py`'s own module docstring, quoting the
master directive directly: **"WhitePact's own measured capability
evidence determines what WhitePact labels validated"** — evidence
requires a trustworthy transport to measure over, which is why
`max_capability_state_for_trust_level()` forbids `TRUST_D` devices
from ever claiming `VALIDATED`.

That ceiling is the *only* structural check today. Reading
`NeuralCapabilityManifest.__post_init__()`: a `TRUST_A`/`TRUST_B`/
`TRUST_C` device's manifest may claim `CapabilityState.VALIDATED` for
any capability with **zero supporting evidence of any kind** — nothing
requires the "measured evidence" the directive's own quoted language
says should be the actual basis for that label. A sufficiently
trusted transport is a necessary condition for a `VALIDATED` claim
(Phase 5's ceiling), not a sufficient one — measured evidence is what
the directive says makes it sufficient, and nothing enforces that
today.

This is the Phase 4 pattern repeating: Phase 4 built `ConsentCategory`/
`ConsentRecord` and a fail-closed evaluator (`evaluate_neural_data_flow`)
so a data flow requires an actual, on-file consent record, not merely
a device capable of asking for one. Phase 16 is the identical shape
applied to scientific substantiation: a `VALIDATED` claim should
require an actual, on-file evidence record, not merely a device
trusted enough to be allowed to make the claim.

## What this phase deliberately does not build

No real evidence database, no fabricated study, no invented accuracy
number, no concrete decoder to validate (Phase 6 already declined to
build one, for the same reason). This phase adds the typed evidence
record and the fail-closed evaluator that *would* gate a real
`VALIDATED` claim once real evidence exists to attach — the same
"typed contract now, concrete substance later" pattern as Phases 5
and 6's `BCIDeviceAdapter` Protocol and `NeuralDecision` contract.

## Design

New module `governance/neural/evidence.py`, mirroring
`policy.py`'s exact shape (StrEnum decision/reason vocabulary, frozen
dataclass result, a single fail-closed evaluator function):

- `NeuralEvidenceType` — distinguishes evidence by *who measured it*,
  since that's the directive's own stated criterion ("WhitePact's
  *own* measured... evidence"):
  - `WHITEPACT_MEASURED` — WhitePact's own measurement process.
  - `INDEPENDENT_THIRD_PARTY` — an independently conducted,
    publicly-checkable study (e.g. peer-reviewed).
  - `REGULATORY_CLEARANCE` — a regulator's own determination (e.g.
    FDA clearance) — inherently independent by construction.
  - `VENDOR_SELF_REPORTED` — the device vendor's own, unverified
    claim. Deliberately **not** a qualifying type on its own — a
    vendor's marketing claim is not "WhitePact's own measured
    evidence," and treating it as equivalent would defeat the entire
    point of the directive's distinction.
- `NeuralCapabilityEvidence` (frozen dataclass) — `device_identity`,
  `capability_name`, `evidence_type`, `description`, `evidence_ref`
  (a citation/document pointer, opaque string — no assumption about
  where evidence records are actually stored, matching `ConsentRecord`'s
  own DB-agnostic shape), `recorded_at`.
- `NeuralEvidenceDecision` (ALLOW/DENY) / `NeuralEvidenceReason`
  (`EVIDENCE_QUALIFIES`, `NO_EVIDENCE_RECORD`, `EVIDENCE_INSUFFICIENT`
  — matching evidence exists but only as `VENDOR_SELF_REPORTED`,
  `NOT_A_VALIDATED_CLAIM` — the capability isn't claimed `VALIDATED`
  in the manifest at all, so there's nothing to substantiate).
- `evaluate_capability_validation_claim(manifest, capability_name,
  evidence_records)` — fail-closed: a `VALIDATED` claim with no
  matching evidence record, or only `VENDOR_SELF_REPORTED` ones,
  is `DENY`; at least one `WHITEPACT_MEASURED`/`INDEPENDENT_THIRD_PARTY`/
  `REGULATORY_CLEARANCE` record is required for `ALLOW`. A capability
  not claimed `VALIDATED` in the manifest at all returns
  `NOT_A_VALIDATED_CLAIM` (nothing to check) rather than being folded
  into either real outcome.

## Scope for this phase

1. `governance/neural/evidence.py` (new).
2. `governance/neural/__init__.py` — export the new symbols,
   alphabetized, matching the existing convention exactly.
3. `governance/__init__.py` — no change needed; it already re-exports
   the `neural` submodule wholesale (confirmed by reading it).
4. `tests/test_neural_evidence.py` (new) — the fail-closed cases
   (no record, vendor-only record), the passing cases (each
   qualifying evidence type individually), the not-a-claim case, and
   a Hypothesis property test that no combination of purely
   `VENDOR_SELF_REPORTED` records can produce `ALLOW`.
5. `tests/test_governance_package_exports.py` — regression guard for
   the new symbols, matching the existing per-phase pattern.

No database migration (mirrors Phase 4's `ConsentRecord` — the typed
shape ships before any persistence layer). No device/decoder/study
fabricated.
