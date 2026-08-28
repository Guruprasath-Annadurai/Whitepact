# Phase 6 — Neural Signal Integrity + Decoder Safety: Report

STATUS: **PASS**, scoped honestly — same discipline Phase 5 established.
Builds the typed `NeuralDecision` contract and misuse-rejection logic.
**No decoder ships.**

## Objective

Per `docs/enterprise-neural/06_PHASE6_DESIGN.md`: `NeuralDecision`
(directive §7's required fields), `NeuralDecisionStatus`
(VALID/AMBIGUOUS/REJECTED), and pure functions for staleness/replay/
context-mismatch detection — all testable without a real decoder,
since they validate the *shape* of a decision, not signal content.

## Scope decision

Same reasoning as Phase 5: no real trained model or device signal
exists to validate a decoder against. Building one now would be
fabricated capability, not integration. This phase delivers the
contract a real decoder must produce and the misuse checks that operate
on that contract's shape alone.

## Current state before phase

Phase 5 shipped the device trust/capability contract but nothing
described what a single neural *inference* (as opposed to a device's
static capability manifest) looks like, or how to reject a malformed
one.

## Architecture implemented

- `governance/neural/decision.py` — `NeuralDecisionStatus` (3-value
  `StrEnum`), `NeuralDecision` (every field the directive's §7 lists:
  schema version, prediction, calibrated probability, uncertainty,
  signal quality, decoder/calibration identity+version+hash, subject/
  session/device context, device trust — reusing Phase 5's
  `DeviceTrustLevel`, not a new type — issuance/expiry, status,
  provenance). `__post_init__` rejects NaN/Inf/out-of-range
  probability/uncertainty/signal-quality via a single bounds check
  (`0.0 <= x <= 1.0`, verified empirically to reject NaN and both
  infinities without a separate `math.isnan` call before relying on
  it), non-increasing expiry, and empty required identifiers.
  `classify_decision_status` (pure, threshold-parameterized — checks
  uncertainty before probability, so a low-probability-but-genuinely-
  uncertain decision is AMBIGUOUS, not REJECTED for the wrong reason).
  `is_expired`, `matches_context` (all three of subject/session/device
  must match), `is_stale_decoder`.

## Files created

- `src/responsibleai/governance/neural/decision.py`
- `tests/test_governance_neural_decision.py`
- `docs/enterprise-neural/06_PHASE6_DESIGN.md`
- `docs/enterprise-neural/06_PHASE6_REPORT.md` (this file)

## Files modified

- `src/responsibleai/governance/neural/__init__.py` — exports the new
  symbols.
- `tests/test_governance_package_exports.py` — added
  `test_neural_decision_symbols_exported`.

## Database migrations

None — no decision is persisted yet (nothing produces a real one to
store).

## Security properties added

Structural rejection of malformed neural decisions (directive §6's
required misuse list: NaN, Infinity, negative/>1 probabilities,
expired, non-finite uncertainty) at construction time — a caller cannot
hold an invalid `NeuralDecision` object at all, the same discipline
Phase 5's `NeuralCapabilityManifest` established for device manifests.

## Privacy properties added

None new this phase.

## Trust boundaries changed

None — no code path constructs a real `NeuralDecision` yet.

## Threats mitigated

The specific misuse classes the directive names (NaN/Inf confidence,
expired decisions, wrong user/session/device, stale decoder) are all
structurally rejected or explicitly detectable via the pure functions
above — verified by test, not merely intended.

## Threats not yet mitigated

Everything requiring a real decoder or signal: actual signal-quality
measurement, actual decoder inference, replayed-inference detection at
the transport layer (this phase provides `is_expired`/staleness
*checks*, not a replay cache — that's an integration concern for
whatever later phase actually consumes decisions over a network).

## Known limitations

`classify_decision_status`'s thresholds are caller-supplied, by design
— this module has no opinion on what "too uncertain" means for a
specific decoder, since no real decoder exists yet to calibrate
against. A future integration will need real, evidenced threshold
values, not placeholders invented here.

## Unit test results

40 tests in `tests/test_governance_neural_decision.py`:
`TestNeuralDecisionConstruction` (9, covering every NaN/Inf/out-of-
range/expiry/empty-string case), `TestClassifyDecisionStatus` (6,
including the uncertainty-before-probability ordering),
`TestIsExpired` (3), `TestMatchesContext` (4), `TestIsStaleDecoder`
(2), `TestProperties` (3 Hypothesis property tests). All passing.

## Integration test results

Not applicable — no persistence or transport layer yet.

## Property test results

`test_valid_range_inputs_never_raise_on_construction` (arbitrary
in-range floats never rejected — confirms no over-tight validation),
`test_out_of_range_or_non_finite_probability_always_rejected` (NaN,
both infinities, and arbitrary out-of-range floats all rejected —
generalizes the example-based NaN/Inf tests), and
`test_status_is_never_valid_when_uncertainty_exceeds_threshold`
(arbitrary uncertainty/threshold pairs) — all pass.

## Fuzz results

Not run — Hypothesis property tests serve this role for this step's scope.

## Adversarial test results

The directive's own named misuse list (§6) is directly, explicitly
tested — not inferred to be covered by generic validation tests.

## Regression results

Full suite: **3069 passed, 0 failed**, 86.27s
(`/tmp/full_run_phase6.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this step.

## Performance results

Not applicable — no runtime data path exists yet.

## Backward-compatibility result

Fully backward compatible — new symbols only.

## Migration result

Not applicable.

## Rollback procedure

Delete `governance/neural/decision.py`, revert
`governance/neural/__init__.py`'s export and
`tests/test_governance_package_exports.py`'s addition, delete
`tests/test_governance_neural_decision.py`.

## Documentation updated

`docs/enterprise-neural/06_PHASE6_DESIGN.md`, this report,
`PROGRESS_LEDGER.md` (updated alongside).

## Claims now supported by evidence

"WhitePact has a typed neural-decision contract that structurally
rejects NaN/Inf/out-of-range confidence values, non-increasing expiry,
and empty required identifiers, plus pure functions for staleness/
context-mismatch/decoder-version detection" — true, evidenced by the
100%-coverage, 40-test suite above.

## Claims still unsupported

"WhitePact decodes neural signals" — false, and deliberately not
attempted. "WhitePact measures decoder confidence" — false; no decoder
exists.

## Errors found and fixed this phase

None — scope kept intentionally narrow (pure types + pure functions,
no I/O, no new dependency), same pattern as Phase 5.

## Residual risks

Same as Phase 5's residual risk, applied to decoders instead of
devices: this module's fields and thresholds are a best-effort guess at
what a real decoder integration will need, unvalidated against any
actual decoder. Expect revision once Phase 7 (intent attestation) or a
real decoder integration puts this contract under real load.

## Next-phase dependencies

Phase 7 (Neural Intent Attestation + Action Binding) is next — it will
bind a `NeuralDecision` to a specific proposed action
(`NeuralIntentAttestation`, per directive §8-9), and is likely to hit
the same "no real signing key material flowing through a real pipeline
yet" boundary, though attestation itself (canonical serialization,
signing, action-hash binding) is more buildable without a live decoder
than Phase 5/6 were without live hardware — worth checking during that
phase's own design pass rather than assuming.
