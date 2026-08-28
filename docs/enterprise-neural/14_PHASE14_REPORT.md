# Phase 14 — Resilience + Fail-Closed Operations: Report

STATUS: **PASS**. Audit-driven, not a rebuild. `THREAT_MODEL.md`
already documents the deliberate fail-closed/fail-open asymmetries
(evidence-write closed, Trust Index open) and one pre-existing test
already proved the gateway-crash case fails closed too — this phase
generalizes that exact regression-test pattern across the rest of the
governed decision pipeline's dependencies.

## Objective

Per `docs/enterprise-neural/14_PHASE14_DESIGN.md`: build the
"resilience/fail-closed matrix" `00_PHASE0_AUDIT.md` §7 named as
Phase 14's expected scope — by auditing every real dependency
`apply_governance()` calls, not by inventing new failure-handling
machinery, per directive rule 63.

## Current state before phase

`mcp/governance_integration.py`'s `apply_governance()` calls ten
external dependencies before/at the decision point: six repository
reads (`ceiling_repo`, `policy_repo`, `delegation_repo`,
`workflow_rule_repo`, `autonomy_budget_repo`, `intent_repo`), two
conditional `recent_*_count()` helper calls, `gateway.evaluate()`, and
`evidence_repo.record()`. Only two had explicit failure-mode handling:
`evidence_repo.record()` (explicit try/except, fails closed with
`governance_evidence_unavailable`) and the Trust Index HTTP lookup
(explicit, fails open by design). `gateway.evaluate()` had no
try/except but was already regression-tested
(`TestAuthoritySubsystemCrashFailsClosed`) to prove exception
propagation alone is sufficient — the tool structurally cannot run
before evidence is written or the executor is reached. The other six
repository dependencies relied on the identical propagation mechanism
but had never been individually tested for it.

## Architecture implemented

No new architecture — this phase adds **evidence**:

- `tests/test_resilience_fail_closed_matrix.py` —
  `TestPreEvaluateDependencyCrashesFailClosed`, a parametrized
  generalization of `TestAuthoritySubsystemCrashFailsClosed`'s exact
  pattern across the six always-reachable repository dependencies:
  monkeypatch each to raise, call a real tool through the live
  `governed_app` fixture, assert the result is never the tool's real
  payload and no evidence record was fabricated for the crashed call.

## Files created

- `tests/test_resilience_fail_closed_matrix.py`
- `docs/enterprise-neural/14_PHASE14_DESIGN.md`
- `docs/enterprise-neural/14_PHASE14_REPORT.md` (this file)

## Files modified

`CHANGELOG.md`, `docs/enterprise-neural/PROGRESS_LEDGER.md` — no
source file required a change.

## Database migrations

None.

## Security properties added

None newly *created* — the propagation mechanism that makes every
pre-evaluate dependency fail closed already existed. This phase makes
that property regression-tested for six dependencies where it was
previously only true by code-reading (the same "properties already
true, now enforced" pattern as Phases 8, 10, 11, and 12).

## Privacy properties added

None new.

## Trust boundaries changed

None.

## Threats mitigated

Regression of "a crash in any pre-decision dependency silently
produces an ALLOW instead of blocking the call" is now caught by CI
for six previously-unguarded dependencies, not only the one
(`gateway.evaluate()`) that already had a test.

## Threats not yet mitigated — named explicitly, not glossed over

1. **`recent_violation_count()` and `recent_autonomous_action_count()`
   crashes are not covered by this phase's parametrized sweep.** Both
   read through `evidence_repo` but need additional fixture state
   (an existing violation history, a configured autonomy budget) the
   shared six-dependency sweep doesn't set up. Real, correctly out of
   scope for this pass — not silently assumed covered by the general
   `EvidenceRepository`-related coverage `TestEvidenceWriteFailsClosed`
   already has (that test covers `.record()`, a different method).
2. **`evidence_repo.list_recent_actions()` crashes are not covered.**
   Only reached when `workflow_rule_repo.get_rules()` returns at least
   one rule — same reasoning as above.

## Known limitations

The parametrized test uses a single generic `_raise(*args, **kwargs)`
monkeypatch target for every dependency — this proves the propagation
property holds regardless of a dependency's specific exception type,
which is the correct scope (the fail-closed property shouldn't depend
on what kind of exception occurs), but does not exercise any
dependency-specific exception handling (there is none to exercise —
that's exactly the point).

## Unit test results

6 tests in `tests/test_resilience_fail_closed_matrix.py`
(`TestPreEvaluateDependencyCrashesFailClosed`, parametrized over
`OrgAuthorityCeilingRepository.get`, `PolicyRepository.get_policy`,
`DelegationRepository.get_latest_delegation`,
`WorkflowRuleRepository.get_rules`, `OrgAutonomyBudgetRepository.get`,
`IntentContractRepository.get_active_for_agent`). All passing.

## Integration test results

Exercises the real, live Starlette ASGI app (`_build_http_app()`) via
a real MCP `ClientSession` over Streamable HTTP — the same integration
depth as `TestAuthoritySubsystemCrashFailsClosed`, not a unit-level
mock of `apply_governance()`.

## Property test results

None new this phase — a specific set of six named dependencies is
better suited to parametrized example-based tests than property-based
generation, consistent with the judgment applied in Phases 8, 10, 11,
12, and 13.

## Fuzz results

Not run.

## Adversarial test results

Every test in this phase *is* an adversarial test — each parametrized
case simulates a hostile/failing dependency and confirms the platform
never silently proceeds as if it succeeded.

## Regression results

Full suite: **3132 passed, 1 skipped, 0 failed**, 129.43s
(`/tmp/full_run_phase14.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy src/responsibleai`:
clean (no source file changed).

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this phase.

## Performance results

Not applicable.

## Backward-compatibility result

Fully backward compatible — test-only addition, zero source file
changed.

## Migration result

Not applicable.

## Rollback procedure

Delete `tests/test_resilience_fail_closed_matrix.py`. Nothing else to
revert.

## Documentation updated

`docs/enterprise-neural/14_PHASE14_DESIGN.md`, this report,
`PROGRESS_LEDGER.md`, `CHANGELOG.md`.

## Claims now supported by evidence

"Every one of `apply_governance()`'s six repository dependencies that
run before `WhitePactRuntimeGateway.evaluate()` fails closed on a
crash — never produces the underlying tool's real payload, never
fabricates an evidence record" — true, evidenced by the tests above,
run against the real live ASGI app and real repository classes, not
mocks of `apply_governance()` itself.

## Claims still unsupported

"Every dependency in the governed decision path is covered by this
matrix" — false; `recent_violation_count()`,
`recent_autonomous_action_count()`, and
`evidence_repo.list_recent_actions()` remain untested for this
specific property, named explicitly above as a residual gap.

## Errors found and fixed this phase

None — the audit confirmed the properties already held; no bug found
in shipped code.

## Residual risks

The three named untested dependency paths remain open, correctly out
of this phase's scope but not silently forgotten — tracked here and
in the ledger for a future pass with dedicated fixture setup.

## Next-phase dependencies

Phase 15 (Enterprise Trust + Procurement Readiness) is next. Given the
pattern across Phases 8 and 10-14, an audit-first pass is again
warranted — `trust/badge.py`/`trust/score.py`/`trust/passport.py`
already exist and are tested; `ENTERPRISE_RC_GATE_REGISTER.md`-style
external-gate cataloging (seen on the reviewed `codex/enterprise-readiness`
branch, PR #51 — a real, good pattern worth considering here too) is a
plausible foundation for what "procurement readiness" concretely
needs versus what's genuinely unbuilt.
