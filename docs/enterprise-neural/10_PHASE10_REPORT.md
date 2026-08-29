# Phase 10 — Brain Policy + Risk Engine: Report

STATUS: **PASS**. Audit-driven, not a rebuild — SPEC.md §2.5 already
names "the Brain" as the existing `governance/gateway.py` risk +
policy pipeline; `gateway.py`'s own docstring already labels those
steps "Phase 9" (`risk.py`) and "Phase 10" (`policy.py`). This phase's
own name refers back to that pre-existing, already-shipped work, not
a component to build from scratch.

## Objective

Per `docs/enterprise-neural/10_PHASE10_DESIGN.md`: verify the master
directive's Phase 10 ("Brain Policy + Risk Engine") requirements
against the real, existing codebase — construct evidence, not new
architecture, per directive rule 63 ("inspect before implementing...
do not rebuild systems merely to satisfy this prompt"), and per Phase
8's own closing note recommending the same audit-first approach here.

## Current state before phase

`governance/risk.py` (`RiskTier`, `TOOL_RISK_TIERS`,
`classify_action_risk`), `governance/policy.py` (`PolicyRule`,
`Policy`), and `db/policy_repository.py` (`PolicyRepository`) already
existed, real and tested, from prior work — 41 dedicated tests across
`tests/test_governance_risk.py`, `tests/test_governance_policy.py`,
`tests/test_policy_repository.py`, plus dozens of indirect exercises
across `test_governance_core.py`, `test_concurrency.py`,
`test_approval_*.py`, `test_workflow_authority.py`,
`test_upstream_gateway.py`. Both live governed-call paths
(`mcp/governance_integration.py:258`, `mcp/upstream_dispatch.py`)
already load `Policy` from `PolicyRepository` per-org, unconditionally,
on every call. Nothing had explicitly *proven*, as a regression-tested
property, that these hold end-to-end through the real gateway or that
no second, unaudited call site exists — only the code's own docstrings
asserted it.

## Architecture implemented

No new architecture — this phase adds **evidence**:

- `tests/test_brain_policy_risk_boundary.py` — structural regression
  guards (source-text scan confirming `Policy.evaluate()` has exactly
  one call site, and `classify_action_risk()` has exactly the three
  audited call sites) plus runtime tests (every `DecisionResult`
  carries a real `RiskTier`; a matching `Policy` rule denies through
  the real `WhitePactRuntimeGateway.evaluate()`; an attacker-supplied
  `ActionRequest.arguments` payload shaped like a risk/policy override
  has no effect; `classify_action_risk`'s documented defaults hold
  against the real function).

## Files created

- `tests/test_brain_policy_risk_boundary.py`
- `docs/enterprise-neural/10_PHASE10_DESIGN.md`
- `docs/enterprise-neural/10_PHASE10_REPORT.md` (this file)

## Files modified

`CHANGELOG.md`, `docs/enterprise-neural/PROGRESS_LEDGER.md` — no
source file required a change; the audit found no code-level fix
needed for what this phase actually scoped.

## Database migrations

None.

## Security properties added

None newly *created* — this phase adds regression tests that make
four already-true properties (single call site for `Policy.evaluate()`,
exactly three known call sites for `classify_action_risk()`, every
decision carries a risk tier, policy rules actually gate the real
gateway) fail loudly if a future change silently breaks them.

## Privacy properties added

None new.

## Trust boundaries changed

None.

## Threats mitigated

Regression of "every governed action gets classified and can be
policy-gated, through exactly the audited code paths" is now caught by
CI, not only by code review. An attacker shaping `ActionRequest.arguments`
to look like a risk-tier or policy-effect override (`{"risk_tier":
"MINIMAL", "policy_effect": "ALLOW"}`) is proven to have zero effect —
both risk classification and policy matching read only `action_type`/
`target`/the org's persisted `Policy`, never request arguments.

## Threats not yet mitigated — named explicitly, not glossed over

1. **No richer policy rule language (OPA/Rego).** SPEC.md §3.5
   explicitly states this remains a future iteration, not implied by
   the current flat first-match-wins matching. Not this phase's scope
   — building it now would be exactly the unrequested rebuild
   directive rule 63 prohibits.
2. **Self-hosted stdio transport remains ungoverned** — already named
   in Phase 8 (`08_PHASE8_REPORT.md`, Gap 1). It has no organizational
   identity to build a `Policy`/risk-tier decision against, so no risk
   classification or policy evaluation happens on that transport at
   all. Architectural, not an oversight this phase could close.

## Known limitations

The structural regression guards are text-based source scans, not a
full AST/import-graph analysis — documented as heuristic in the test
file's own docstring, matching Phase 8's and
`scripts/rotate_field_encryption_key.py`'s own honesty about their
respective heuristics. A sufficiently obfuscated bypass (e.g.
`getattr(policy_obj, "evaluate")(...)`) would not be caught by this
guard.

## Unit test results

13 tests in `tests/test_brain_policy_risk_boundary.py`:
`TestPolicyEvaluateSingleCallSite` (1),
`TestClassifyActionRiskKnownCallSites` (1),
`TestEveryDecisionCarriesARealRiskTier` (3),
`TestPolicyRuleActuallyGatesTheRealGateway` (2),
`TestClassifyActionRiskHonestDefaults` (6, including a parametrized
sweep over four known tools' documented tiers). All passing.

## Integration test results

The structural guards scan the actual shipped source tree, not a
fixture or a recreated subset of it. The runtime tests call the real
`WhitePactRuntimeGateway.evaluate()` with real `Policy`/`PolicyRule`/
`AuthorityContext` objects — the same call shape
`mcp/governance_integration.py` and `mcp/upstream_dispatch.py` use in
production, not a mock.

## Property test results

None new this phase — the properties under test (single call site,
decision-carries-risk-tier, policy-gates-outcome) are architectural
invariants better suited to example-based/structural tests than
property-based generation, consistent with Phase 8's same judgment.

## Fuzz results

Not run.

## Adversarial test results

`test_an_attacker_supplied_action_alone_cannot_forge_a_policy_bypass`
is the direct adversarial case: an `ActionRequest.arguments` payload
crafted to look like a risk-tier/policy-effect override has zero
effect on the outcome, confirmed against a real `DENY` policy rule
through the real gateway.

## Regression results

Full suite: **3114 passed, 1 skipped, 0 failed**, 136.79s
(`/tmp/full_run_phase10.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean.

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

Delete `tests/test_brain_policy_risk_boundary.py`. Nothing else to
revert.

## Documentation updated

`docs/enterprise-neural/10_PHASE10_DESIGN.md`, this report,
`PROGRESS_LEDGER.md`, `CHANGELOG.md`.

## Claims now supported by evidence

"Every governed action, on both live dispatch paths, is classified
into a `RiskTier` and can be gated by the organization's persisted
`Policy` — with `Policy.evaluate()` and `classify_action_risk()` each
having exactly the audited call sites, and neither reachable or
forgeable via attacker-controlled action arguments" — true, evidenced
by the tests above, run against the real source tree and the real
gateway, not a fixture.

## Claims still unsupported

"The Brain includes a richer policy rule language (OPA/Rego)" — false,
explicitly out of scope per SPEC.md §3.5, named here for completeness.
"The self-hosted stdio transport is risk-classified/policy-governed" —
false, pre-existing, named explicitly (Gap 2 above, same underlying
gap as Phase 8's Gap 1).

## Errors found and fixed this phase

None — the audit confirmed the properties already held; no bug found
in shipped code.

## Residual risks

The two named gaps (no richer policy language, stdio transport
ungoverned) remain open, correctly out of this phase's scope but not
silently forgotten — tracked here and in the ledger.

## Next-phase dependencies

Phase 11 (Citadel Execution Containment) is next. Given how much of
Phase 8 and Phase 10's ground was already covered by existing
Heart/Production-Integration/SPEC.md-tracked work, Phase 11 likely
warrants the same audit-first approach before assuming net-new scope —
`governance/execution.py`'s `ExecutionAuthorization` (proven, Phase 8,
to have a single gated construction site) is a plausible existing
candidate for what "Citadel Execution Containment" already covers.
