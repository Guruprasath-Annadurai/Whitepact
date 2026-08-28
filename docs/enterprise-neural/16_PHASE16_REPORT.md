# Phase 16 — Neural Scientific Evidence System: Report

STATUS: **PASS**. A real, previously-unenforced gap closed with a
typed contract — not a fabricated device, decoder, or study. Same
discipline as Phases 5-6.

## Objective

Per `docs/enterprise-neural/16_PHASE16_DESIGN.md`: build the
"Neural Scientific Evidence System" the master directive's Phase 16
names, grouped with the neural/BCI track (Phases 4-7) since Phase 0's
audit confirmed zero pre-existing neural/BCI code. Per directive rule
63 and the pattern Phases 5-6 already established for this exact
track: build the typed contract a real system would need, do not
fabricate the capability (a device, a decoder, a study) that doesn't
exist.

## Current state before phase

`governance/neural/device.py`'s own module docstring quotes the master
directive directly: "WhitePact's own measured capability evidence
determines what WhitePact labels validated." Reading
`NeuralCapabilityManifest.__post_init__()`: the only structural check
was `max_capability_state_for_trust_level()` — a device transport
ceiling (Phase 5). Nothing checked whether any actual evidence backed
a `CapabilityState.VALIDATED` claim; a sufficiently trusted device
could claim `VALIDATED` for any capability with zero supporting
evidence of any kind. The transport ceiling is a necessary condition
for the claim, not the sufficient one the directive's own quoted
language describes.

## Architecture implemented

New module, mirroring Phase 4's `policy.py` shape exactly (StrEnum
decision/reason vocabulary, frozen dataclass result, single fail-
closed evaluator):

- `governance/neural/evidence.py` — `NeuralEvidenceType`
  (`WHITEPACT_MEASURED`/`INDEPENDENT_THIRD_PARTY`/`REGULATORY_CLEARANCE`
  qualify; `VENDOR_SELF_REPORTED` deliberately does not, on its own —
  the directive's own distinction between WhitePact's own measurement
  and a vendor's unverified claim), `NeuralCapabilityEvidence` (a
  DB-agnostic typed record, matching `ConsentRecord`'s own convention
  of shipping ahead of any concrete persistence layer),
  `evaluate_capability_validation_claim()` — fail-closed: no matching
  evidence, or only vendor-self-reported evidence, denies a
  `VALIDATED` claim; at least one qualifying record allows it. A
  capability not claimed `VALIDATED` in the manifest at all returns a
  distinct `NOT_A_VALIDATED_CLAIM` reason rather than being folded
  into either real outcome.

## Files created

- `src/responsibleai/governance/neural/evidence.py`
- `tests/test_neural_evidence.py`
- `docs/enterprise-neural/16_PHASE16_DESIGN.md`
- `docs/enterprise-neural/16_PHASE16_REPORT.md` (this file)

## Files modified

- `src/responsibleai/governance/neural/__init__.py` — new symbols
  exported, `__all__` updated alphabetically, module docstring
  extended.
- `tests/test_governance_package_exports.py` — regression guard added
  (`test_neural_evidence_symbols_exported`).
- `CHANGELOG.md`, `docs/enterprise-neural/PROGRESS_LEDGER.md`.

## Database migrations

None — matches Phase 4's `ConsentRecord`: the typed shape ships ahead
of any persistence layer, deliberately.

## Security/integrity properties added

A `CapabilityState.VALIDATED` claim can now be programmatically
checked against real evidence, and the check is fail-closed: absent or
insufficient (vendor-only) evidence denies the claim, never silently
allows it. This is a new, real property — nothing enforced this
before this phase.

## Privacy properties added

None — orthogonal to Phase 4's consent/privacy classification work.

## Trust boundaries changed

None — this module doesn't grant or check authority; it evaluates
whether a scientific claim is substantiated, a separate question from
Phase 5's device-trust ceiling.

## Threats mitigated

A device (or a future caller constructing manifests) can no longer
have a `VALIDATED` capability claim treated as substantiated without
an actual, on-file evidence record — and specifically cannot satisfy
that requirement with only the vendor's own unverified claim, however
many such claims exist (proven by the Hypothesis property test).

## Threats not yet mitigated — named explicitly, not glossed over

1. **No concrete evidence persistence layer exists.** `NeuralCapabilityEvidence`
   is a typed, in-memory shape only — matching Phase 4's `ConsentRecord`
   at the same stage. A real evidence store, and wiring
   `evaluate_capability_validation_claim()` into whatever constructs
   or consumes a `NeuralCapabilityManifest`, are separate, future
   work.
2. **No cross-check that `evidence_records[i].device_identity` matches
   the manifest being evaluated.** Deliberate, per the function's own
   docstring — which evidence store to query for which device is a
   caller concern; this function evaluates exactly the records it's
   given.
3. **No real device, decoder, or scientific study exists to actually
   generate a qualifying evidence record.** Same reasoning as Phases
   5-6: fabricating one now, with nothing real to validate it against,
   would be exactly the prototype capability fabrication the master
   directive prohibits.

## Known limitations

`evidence_ref` is an opaque string with no verification of what it
points to — this module records *which* evidence backs a claim, not
whether that evidence's own content actually supports the claim
(adjudicating a study's validity is out of scope for a typed contract
module).

## Unit test results

12 tests in `tests/test_neural_evidence.py`:
`TestNeuralCapabilityEvidenceValidation` (2),
`TestNotAValidatedClaim` (2),
`TestFailClosedOnMissingOrInsufficientEvidence` (3),
`TestQualifyingEvidenceAllows` (4, including a 3-way parametrized
sweep over every qualifying evidence type),
`TestVendorReportedAloneCanNeverAllow` (1 Hypothesis property test,
1-20 vendor-only records, always denies). Plus 1 new export regression
guard in `tests/test_governance_package_exports.py`. All passing.
100% coverage on `governance/neural/evidence.py`.

## Integration test results

Not applicable — no concrete device/decoder integration exists to
integration-test against, per this phase's own deliberate scope.

## Property test results

1 Hypothesis property test
(`test_any_number_of_vendor_only_records_denies`): for any count
1-20, a set of purely `VENDOR_SELF_REPORTED` evidence records never
produces `ALLOW` — the directive's own core distinction, verified
against arbitrary quantities rather than just one example.

## Fuzz results

Not run.

## Adversarial test results

`test_a_qualifying_record_alongside_vendor_only_records_still_allows`
and `test_evidence_for_a_different_capability_does_not_count` are the
adversarial-adjacent cases: mixing weak evidence with strong evidence
doesn't dilute the strong evidence's sufficiency, and evidence for an
unrelated capability can't be misattributed to satisfy a different
claim.

## Regression results

Full suite: **3145 passed, 1 skipped, 0 failed**, 132.22s
(`/tmp/full_run_phase16.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean on all
modified/created source files.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this phase.

## Performance results

Not applicable.

## Backward-compatibility result

Fully backward compatible — new module, new exports, no existing
symbol changed.

## Migration result

Not applicable.

## Rollback procedure

Delete `src/responsibleai/governance/neural/evidence.py` and
`tests/test_neural_evidence.py`; revert the `__init__.py` exports and
the `test_governance_package_exports.py` addition.

## Documentation updated

`docs/enterprise-neural/16_PHASE16_DESIGN.md`, this report,
`PROGRESS_LEDGER.md`, `CHANGELOG.md`, and
`governance/neural/__init__.py`'s own module docstring.

## Claims now supported by evidence

"A `CapabilityState.VALIDATED` claim requires at least one evidence
record of a qualifying type (`WHITEPACT_MEASURED`,
`INDEPENDENT_THIRD_PARTY`, or `REGULATORY_CLEARANCE`) — vendor-self-
reported claims alone, in any quantity, are never sufficient" — true,
evidenced by the tests above, including a property test over an
arbitrary quantity of vendor-only records.

## Claims still unsupported

"A real evidence persistence layer exists" — false, by design, same
stage as Phase 4's `ConsentRecord`. "A real device/decoder/study backs
any capability claim" — false; none exists, none is fabricated by this
phase.

## Errors found and fixed this phase

None in existing shipped code — the gap closed (no evidence
enforcement) was a genuine absence, not a bug in code that already
existed.

## Residual risks

The three named gaps (no persistence layer, no device-identity cross-
check, no real evidence to actually record) remain open, correctly
out of this phase's scope but not silently forgotten — tracked here
and in the ledger, matching Phases 5-6's own residual-risk framing for
the same neural/BCI track.

## Next-phase dependencies

Phase 17 (Full Adversarial Hardening) is next. Given the pattern
across nearly every phase since 8, an audit-first pass is again
warranted before assuming net-new scope — `SECURITY_ASSURANCE_CASE.md`'s
own §2 (24 named threats) and §5 ("Common Implementation Weaknesses —
How They're Countered") are a plausible existing foundation for what
"adversarial hardening" already covers versus what's genuinely
untested.
