# Phase 7 — Neural Intent Attestation + Action Binding: Report

STATUS: **PASS**. Builds `NeuralIntentAttestation`, minting/verification,
and the mutation-invalidates-authorization property — fully tested,
unlike Phases 5/6, since attestation is a pure transformation over
already-typed objects, not hardware/model-dependent.

## Objective

Per `docs/enterprise-neural/07_PHASE7_DESIGN.md`: `NeuralIntentAttestation`
(directive §8's required fields), minting and verification reusing
Phase 2's `governance/crypto` signing primitives directly, and the
directive §9 mutation-invalidates-authorization property.

## Current state before phase

Phase 6 shipped `NeuralDecision` but nothing bound a decision to a
specific proposed action, and no signing/verification existed for
neural-originated authorization.

## Architecture implemented

- `governance/crypto/types.py` — added `KeyPurpose.NEURAL_ATTESTATION`
  (additive enum value; verified no existing test enumerates
  `KeyPurpose` by fixed count before adding it — only a Hypothesis
  `sampled_from(list(KeyPurpose))` strategy exists, which correctly
  now also exercises the new value).
- `governance/neural/attestation.py` — `compute_neural_action_digest`
  (canonical SHA-256 digest over action_type/target/purpose/arguments —
  deliberately not a reuse of `governance/approval.py::compute_action_digest`,
  which requires a full `ActionRequest`/`AgentContext` neural
  attestation has no natural value for, and omits `purpose`, which the
  directive explicitly requires), `NeuralAttestationStatus`,
  `NeuralAttestationRejectReason`, `NeuralAttestationVerificationResult`,
  `NeuralIntentAttestation` (embeds the full `NeuralDecision`, not a
  summary), `mint_neural_intent_attestation` (signs via
  `governance/crypto.sign`), `verify_neural_intent_attestation`
  (fail-closed, checked in order: signature → expiry → action-digest
  match → embedded decision status).

## Files created

- `src/responsibleai/governance/neural/attestation.py`
- `tests/test_governance_neural_attestation.py`
- `docs/enterprise-neural/07_PHASE7_DESIGN.md`
- `docs/enterprise-neural/07_PHASE7_REPORT.md` (this file)

## Files modified

- `src/responsibleai/governance/crypto/types.py` — added
  `KeyPurpose.NEURAL_ATTESTATION`.
- `src/responsibleai/governance/neural/__init__.py` — exports the new
  symbols.
- `tests/test_governance_package_exports.py` — added
  `test_neural_attestation_symbols_exported` and
  `test_crypto_neural_attestation_key_purpose_exported`.

## Database migrations

None — no attestation is persisted yet (this phase builds the mint/
verify mechanism; storage is a later integration concern, deliberately
not addressed here per the design doc Sec 5's "no wiring into any real
execution path" boundary).

## Security properties added

**The actual point of this phase**: mutation-invalidates-authorization,
directive §9's worked example (₹1,000 → ₹100,000, recipient A → B)
implemented literally — `verify_neural_intent_attestation` recomputes
nothing itself; it compares the attestation's stored `action_digest`
against a caller-supplied `current_action_digest` for what's actually
about to execute, and rejects on any mismatch. Also: fail-closed
verification ordering (signature checked first, so a forged attestation
never reaches the mutation/expiry/decision-status checks at all),
`REJECTED`/`AMBIGUOUS`-decision attestations always fail verification
regardless of mint-time discipline (defense in depth).

## Privacy properties added

None new this phase — `NeuralIntentAttestation` embeds `NeuralDecision`,
which already carries no raw N0/N1/N2 payload (Phase 6's own scope).

## Trust boundaries changed

None — no code path mints a real attestation yet (no decoder to
produce a real `NeuralDecision` from, same boundary Phase 6 stated).

## Threats mitigated

Action mutation after attestation (the directive's central worked
example, directly implemented and tested). Signature forgery (fails
before any other check runs). Replay past expiry.
`REJECTED`/`AMBIGUOUS` decisions being smuggled through as if valid.

## Threats not yet mitigated

Attestation replay *before* expiry (same-attestation-used-twice) isn't
addressed — that's an execution-permit concern (single-use consumption,
directive Phase 8's territory, mirroring how
`ExecutionAuthorization` in `governance/execution.py` already handles
single-use consumption for the non-neural case) rather than
attestation-verification's own job. Flagged, not silently assumed
covered.

## Known limitations

No persistence layer for attestations — nothing stores a minted
attestation for later, out-of-process verification. This phase covers
mint-then-verify-in-the-same-process correctness; a real integration
would need a store, which is deliberately not built here (same "don't
wire into a live path prematurely" discipline as every prior phase).

## Unit test results

24 tests in `tests/test_governance_neural_attestation.py`:
`TestComputeNeuralActionDigest` (5 — determinism, sensitivity to
amount/target/purpose changes, argument-key-order independence),
`TestNeuralIntentAttestationConstruction` (6 — every required-field
empty-string case plus expiry ordering), `TestMintAndVerify` (7 —
valid round trip, wrong key, tampered signature, expired at and past
the boundary, AMBIGUOUS/REJECTED decision rejection at verify),
`TestMutationInvalidatesAuthorization` (4 — amount/recipient/purpose
mutation, plus a sanity check that identical actions still verify),
`TestProperties` (2 Hypothesis property tests). All passing.

## Integration test results

`TestMintAndVerify` and `TestMutationInvalidatesAuthorization` are
genuinely end-to-end within this module's own scope: real
`governance/crypto.sign`/`verify` (not mocked), real
`compute_neural_action_digest` calls, exercising the full mint →
verify pipeline exactly as a real integration would call it.

## Property test results

`test_any_amount_mutation_invalidates` (arbitrary amount pairs, mutation
always rejected when values differ — generalizes the example-based
amount-mutation test) and
`test_verification_only_succeeds_under_the_signing_key` (arbitrary
32-byte key pairs, verification only succeeds under the exact signing
key) — both pass.

## Fuzz results

Not run — Hypothesis property tests serve this role for this step's scope.

## Adversarial test results

Every adversarial scenario the directive's §7 names for this specific
object (signature tamper, action mutation, replay-past-expiry,
uncertain/rejected decision smuggled through) is directly tested.

## Regression results

Full suite: **3095 passed, 0 failed**, 89.01s
(`/tmp/full_run_phase7.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean.

## Dependency audit

No new dependency — reuses `governance/crypto`'s existing
`cryptography`-backed `sign`/`verify`.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this step.

## Performance results

Not benchmarked — no production call site exists yet.

## Backward-compatibility result

Fully backward compatible — `KeyPurpose.NEURAL_ATTESTATION` is a purely
additive enum value (verified against the one existing test that
enumerates `KeyPurpose` via Hypothesis `sampled_from`, which correctly
now also covers it, not broken by it); everything else is new symbols.

## Migration result

Not applicable — no persistence this step.

## Rollback procedure

Delete `governance/neural/attestation.py`, revert
`governance/crypto/types.py`'s `KeyPurpose.NEURAL_ATTESTATION` addition
and `governance/neural/__init__.py`'s export, revert
`tests/test_governance_package_exports.py`'s additions, delete
`tests/test_governance_neural_attestation.py`.

## Documentation updated

`docs/enterprise-neural/07_PHASE7_DESIGN.md`, this report,
`PROGRESS_LEDGER.md` (updated alongside).

## Claims now supported by evidence

"WhitePact can mint and verify a cryptographically signed neural intent
attestation bound to an exact proposed action, where mutating any
security-relevant field of that action after attestation invalidates
it" — true, evidenced by the 100%-coverage, 24-test suite above,
including the literal ₹1,000→₹100,000 and recipient-A→B scenarios the
directive names.

## Claims still unsupported

"Attestations are persisted or wired into any real execution path" —
false, deliberately not attempted. "Attestation replay (same token used
twice, before expiry) is prevented" — false; that's a single-use-
consumption concern for a future execution-permit integration, not this
phase's own scope.

## Errors found and fixed this phase

None in the shipped implementation — the empirical verification script
(covering mint/verify round trip, all three mutation dimensions, wrong-
key rejection, expiry, and AMBIGUOUS-decision rejection) passed cleanly
on first run. One test-authoring mistake caught and fixed before commit:
an initial `test_rejects_empty_attestation_id` used
`dataclasses.asdict()` to build a modified copy of an existing
attestation, which silently converts the nested `NeuralDecision` field
into a plain dict too (a known `dataclasses.asdict` behavior for nested
dataclasses) — rewritten to construct the test case directly instead of
routing through a recursive `asdict`/reconstruct pattern that doesn't
actually work for objects with dataclass-typed fields.

## Residual risks

Same as Phase 5/6: this contract is unvalidated against a real decoder
or a real downstream execution-permit consumer. The mint/verify API
shape (positional/keyword split, TTL-as-seconds vs. an explicit
`expires_at`) may need revision once Phase 8 (execution permit binding)
or a real integration puts it under real load.

## Next-phase dependencies

Phase 8 (LLM + Agent Security Boundary) is next in the directive's own
numbering. Phase 8's own directive text is about treating every LLM as
potentially compromised and constraining what it can do — largely
independent of the neural track (Phases 4-7), and closer in spirit to
the already-completed Heart production-integration work
(`docs/heart-production/`) than to BCI-specific scaffolding. Worth a
fresh design pass checking what, if anything, already exists in this
codebase for LLM/tool-call constraint before assuming net-new scope the
way Phases 5-7 correctly did for hardware-dependent work.
