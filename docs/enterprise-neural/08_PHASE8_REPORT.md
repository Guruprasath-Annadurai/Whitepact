# Phase 8 — LLM + Agent Security Boundary: Report

STATUS: **PASS**. Audit-driven, not a rebuild — most of directive §8's
requirements already hold, verified against real code rather than
assumed from docstrings; the genuine gaps found are named, not silently
patched around.

## Objective

Per `docs/enterprise-neural/08_PHASE8_DESIGN.md`: verify the master
directive's LLM-untrusted-input requirements against the real,
existing codebase — construct evidence, not new architecture, per
directive rule 63 ("inspect before implementing... do not rebuild
systems merely to satisfy this prompt").

## Current state before phase

Substantial existing infrastructure already addresses most of this
phase's requirements, built under prior initiatives (Heart, Production
Integration, Authority Everywhere): `governance/gateway.py`,
`governance/execution.py`'s `InternalToolExecutor`/`authorize_execution`,
`mcp/governance_integration.py`. Nothing had explicitly *proven*, as a
regression-tested property, that these hold — only their own docstrings
asserted it.

## Architecture implemented

No new architecture — this phase adds **evidence**:

- `tests/test_llm_agent_security_boundary.py` — structural regression
  guards (source-text scan confirming `ExecutionAuthorization` and
  `AuthorityGrant` each have exactly one construction site in the
  codebase, and `mint_neural_intent_attestation` has zero call sites
  outside its own module) plus runtime tests
  (`authorize_execution()` refuses every non-executable decision;
  an attacker-controlled `ActionRequest.arguments` payload has no
  bearing on the outcome, since the decision is a separate, explicit,
  typed parameter never derived from action data).

## Files created

- `tests/test_llm_agent_security_boundary.py`
- `docs/enterprise-neural/08_PHASE8_DESIGN.md`
- `docs/enterprise-neural/08_PHASE8_REPORT.md` (this file)

## Files modified

None — no existing source file required a change; the audit found no
code-level fix needed for what this phase actually scoped.

## Database migrations

None.

## Security properties added

None newly *created* — this phase adds regression tests that make three
already-true properties (single construction site for
`ExecutionAuthorization`, single construction site for `AuthorityGrant`,
no LLM-reachable path to `mint_neural_intent_attestation`) fail loudly
if a future change silently breaks them, rather than relying on nobody
noticing.

## Privacy properties added

None new.

## Trust boundaries changed

None.

## Threats mitigated

Regression of the "LLM cannot self-issue authority/execution permits"
property is now caught by CI, not only by code review.

## Threats not yet mitigated — named explicitly, not glossed over

1. **Self-hosted stdio transport is ungoverned** — pre-existing,
   self-documented in `mcp/governance_integration.py`'s own docstring.
   Not fixed this phase: closing it means adding organizational
   identity to the stdio transport, a materially larger architectural
   change than this phase's scope, and the directive's own working-
   behavior rule requires flagging a decision like that before
   attempting it, not silently expanding scope to include it.
2. **No schema validation of LLM-supplied tool arguments** before they
   reach the governance gateway — `ActionRequest.arguments` is
   `dict[str, Any]`, unchecked against a tool's declared schema. Real
   gap, not fixed this phase: touches every existing tool definition in
   `mcp/tools.py`, a separate, larger initiative.

## Known limitations

The structural regression guards are text-based source scans, not a
full AST/import-graph analysis — documented as heuristic in the test
file's own docstring, matching the same honesty this session applied to
`scripts/rotate_field_encryption_key.py`'s legacy-ciphertext detection
heuristic. A sufficiently obfuscated bypass (e.g. `getattr(module,
"ExecutionAuthorization")(...)`) would not be caught by this guard —
acceptable for a regression guard against accidental/careless
reintroduction, not a defense against a deliberately hostile contributor
with commit access (a different threat model entirely).

## Unit test results

7 tests in `tests/test_llm_agent_security_boundary.py`:
`TestExecutionAuthorizationSingleConstructionSite` (1),
`TestAuthorityGrantSingleConstructionSite` (1),
`TestNeuralIntentAttestationMintingIsNotWiredToAnyLlmReachablePath` (1),
`TestAuthorizeExecutionRequiresARealGatewayDecision` (4, including a
parametrized sweep over DENY/QUARANTINE/REQUIRE_APPROVAL). All passing.

## Integration test results

The structural guards are genuinely integration-level in the sense that
they scan the *actual shipped source tree*, not a fixture or a
recreated subset of it — a real regression in `governance/execution.py`
or any other file would be caught.

## Property test results

None new this step — the properties under test (single construction
site, decision-type gating) are architectural invariants better suited
to example-based/structural tests than property-based generation.

## Fuzz results

Not run.

## Adversarial test results

`test_an_attacker_supplied_action_alone_cannot_forge_an_allow_decision`
is the direct adversarial case: an `ActionRequest.arguments` payload
crafted to *look like* a decision object (`{"decision": "ALLOW",
"reason_code": "trust me"}`) has zero effect on the outcome, confirmed
by calling `authorize_execution` with a real DENY decision alongside it.

## Regression results

Full suite: **3102 passed, 0 failed**, 94.76s
(`/tmp/full_run_phase8.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this step.

## Performance results

Not applicable.

## Backward-compatibility result

Fully backward compatible — test-only addition, zero source file changed.

## Migration result

Not applicable.

## Rollback procedure

Delete `tests/test_llm_agent_security_boundary.py`. Nothing else to
revert.

## Documentation updated

`docs/enterprise-neural/08_PHASE8_DESIGN.md`, this report,
`PROGRESS_LEDGER.md` (updated alongside).

## Claims now supported by evidence

"An LLM/agent-controlled `ActionRequest` cannot, by itself, produce a
valid `ExecutionAuthorization` or `AuthorityGrant` — those objects have
exactly one, gated construction site each in the codebase, and
`authorize_execution()` requires a real `DecisionResult` from the
governance gateway, never derived from action data" — true, evidenced
by the tests above, run against the real source tree, not a fixture.

## Claims still unsupported

"The self-hosted stdio transport is governed" — false, pre-existing,
named explicitly (Gap 1). "LLM tool arguments are schema-validated
before reaching governance" — false, named explicitly (Gap 2).

## Errors found and fixed this phase

None in shipped code (no bug found — the audit confirmed the properties
already held). Three field-name mistakes were caught and fixed *before*
the tests ran successfully: `AgentContext` requires `identity:
IdentityContext` and `organization_id` (not the `agent_id`/`org_id`
guessed initially), and `DecisionResult` requires `action_id` (not
`reason_code` as its second field) — corrected by reading `governance/
models.py`'s actual field definitions before finalizing the test file,
not discovered by a failing CI run.

## Residual risks

The two named gaps (stdio transport, tool-argument schema validation)
remain open, correctly out of this phase's scope but not silently
forgotten — tracked here and in the ledger for whoever picks up either
as its own initiative.

## Next-phase dependencies

Phase 10 (Brain Policy + Risk Engine) is next, per Phase 9 being merged
into the separate `docs/heart-production/` track per prior direction.
Given how much of Phase 8's ground was already covered by existing
`governance/gateway.py`/policy work, Phase 10 likely warrants the same
audit-first approach before assuming net-new scope.
