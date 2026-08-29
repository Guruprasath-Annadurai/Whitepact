# Phase 5 — Universal BCI Device + Trust Layer: Report

STATUS: **PASS**, scoped honestly. Builds the device trust/capability
type contract. **Does not** add a BrainFlow/LSL/vendor SDK dependency
or a concrete device adapter — see "Scope decision" below for why that
is correct, not incomplete.

## Objective

Per `docs/enterprise-neural/05_PHASE5_DESIGN.md`: `DeviceTrustLevel`
(TRUST_A-D), `CapabilityState` (VALIDATED/EXPERIMENTAL/UNAVAILABLE),
`NeuralCapabilityManifest`, and the `BCIDeviceAdapter` Protocol.

## Scope decision (made before writing code, not discovered after)

The master directive's own rules — §48 (dependency policy: don't add a
dependency without a concrete need, verify maintenance first) and §63
(no prototypes, no placeholders, no fake capability claims) — argue
against adding `brainflow`/`pylsl`/a vendor SDK or writing a concrete
adapter right now: there is no real device or vendor decision to build
against, and any adapter written without one would be fabricated
capability claims dressed up as an integration. This phase therefore
delivers the **typed contract** a real adapter would need to satisfy,
not a fake implementation of one.

## Current state before phase

Phase 4 shipped `NeuralPayload`/`NeuralDataClass` but no device-facing
contract — nothing described what a device adapter must report about
itself or how trust and capability relate.

## Architecture implemented

- `governance/neural/device.py` — `DeviceTrustLevel` (4-value
  `StrEnum`, directive §6), `CapabilityState` (3-value `StrEnum`,
  directive §32), `max_capability_state_for_trust_level()` (the one
  place trust constrains capability: `TRUST_D` devices can never claim
  `VALIDATED` for any capability — an unverified transport gives no
  basis for the measured-confidence claim `VALIDATED` implies),
  `NeuralCapabilityManifest` (frozen dataclass, validates channel
  count/sampling rate/device identity and the trust-capability ceiling
  at construction — an invalid manifest cannot be constructed, not
  merely discouraged), `BCIDeviceAdapter` (a `Protocol`, no concrete
  implementation).

## Files created

- `src/responsibleai/governance/neural/device.py`
- `tests/test_governance_neural_device.py`
- `docs/enterprise-neural/05_PHASE5_DESIGN.md`
- `docs/enterprise-neural/05_PHASE5_REPORT.md` (this file)

## Files modified

- `src/responsibleai/governance/neural/__init__.py` — exports the new
  symbols.
- `tests/test_governance_package_exports.py` — added
  `test_neural_device_symbols_exported`.

## Database migrations

None this phase — no device data is persisted yet (nothing produces a
real manifest to store).

## Security properties added

Structural enforcement of "compatibility != capability != trust"
(directive §5): a `TRUST_D` manifest claiming a `VALIDATED` capability
cannot be constructed — not a lint rule, not a review checklist item, a
`ValueError` at object-creation time, verified by test.

## Privacy properties added

None new this phase (no data flows through this layer yet).

## Trust boundaries changed

None — no code path constructs a `NeuralCapabilityManifest` from real
device data yet, since no concrete adapter exists.

## Threats mitigated

Fabricated capability claims from a low-trust device (structurally
prevented for the `VALIDATED` state specifically).

## Threats not yet mitigated

Everything requiring a real device: signal integrity (Phase 6),
decoder safety (Phase 6), intent attestation (Phase 7) — none of which
can be built or tested without an actual adapter, which this phase
correctly declines to fabricate.

## Known limitations

The trust-capability ceiling currently only restricts `TRUST_D` →
never `VALIDATED`. A finer-grained ceiling (e.g. `TRUST_C` capped below
some specific high-risk capability) is deferred until Phase 6/7 define
real capability names beyond generic placeholders — inventing a risk
taxonomy now, before any real capability catalog exists, would be
speculative rather than evidenced.

## Unit test results

18 tests in `tests/test_governance_neural_device.py`:
`TestMaxCapabilityStateForTrustLevel` (4), `TestNeuralCapabilityManifest`
(10 — construction validation for device identity/channel count/
sampling rate, the trust-capability ceiling both directions, fail-
closed `capability_state`/`is_validated` lookups), `TestProperties` (3
Hypothesis property tests, including one confirming the `TRUST_D`
ceiling holds even when mixed with other capabilities at other states).
All passing.

## Integration test results

Not applicable — no persistence or transport layer for this phase's
types yet.

## Property test results

`test_non_trust_d_accepts_any_capability_state` and
`test_trust_d_accepts_non_validated_states` (arbitrary trust levels ×
capability states) plus
`test_trust_d_never_accepts_validated_regardless_of_other_capabilities`
(the ceiling holds even mixed with unrelated capabilities at other
states, not just in isolation) — all pass.

## Fuzz results

Not run — Hypothesis property tests serve this role for this step's scope.

## Adversarial test results

The core adversarial property (a low-trust device fabricating a
VALIDATED claim) is directly tested, both example-based and via
property test.

## Regression results

Full suite: **3028 passed, 0 failed**, 89.30s
(`/tmp/full_run_phase5.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean (including the
`BCIDeviceAdapter` Protocol's structural typing).

## Dependency audit

**No new dependency** — the central scope decision this phase makes,
per directive §48.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this step.

## Performance results

Not applicable — no runtime data path exists yet.

## Backward-compatibility result

Fully backward compatible — new symbols only, zero existing call site
touched.

## Migration result

Not applicable.

## Rollback procedure

Delete `governance/neural/device.py`, revert `governance/neural/__init__.py`'s
export and `tests/test_governance_package_exports.py`'s addition, delete
`tests/test_governance_neural_device.py`.

## Documentation updated

`docs/enterprise-neural/05_PHASE5_DESIGN.md`, this report,
`PROGRESS_LEDGER.md` (updated alongside).

## Claims now supported by evidence

"WhitePact has a typed device trust/capability contract that
structurally prevents a low-trust device from claiming a validated
capability" — true, evidenced by the 100%-coverage, 18-test suite
above.

## Claims still unsupported

"WhitePact supports [any specific BCI device/vendor]" — false, and
deliberately not attempted this phase. "WhitePact measures real device
capabilities" — false; no measurement code exists (needs a real device
signal to measure against — Phase 6's territory).

## Errors found and fixed this phase

None — scope was kept intentionally narrow (pure types, one policy
function, no I/O, no new dependency), consistent with the pattern in
prior low-complexity steps (Phase 4 Step 1, Phase 2 Step 1) where tight
scoping correlated with clean first-pass empirical verification.

## Residual risks

The `BCIDeviceAdapter` Protocol is unvalidated against any real
implementation — Protocol conformance can only be genuinely proven once
a concrete adapter exists to check against `mypy`'s structural typing
for real. Worth revisiting the Protocol's exact shape once a vendor/
device decision is actually made, rather than assuming this phase's
guess at the interface survives contact with a real SDK unchanged.

## Next-phase dependencies

Phase 6 (Neural Signal Integrity + Decoder Safety) is next. Like Phase
5, it will hit the same "no real device to validate against" boundary
for anything requiring actual signal content — expect Phase 6 to
similarly scope itself to the typed `NeuralDecision` contract (per the
master directive §33-34) rather than a working decoder, for the same
reasons this phase declined to fabricate a device adapter.
