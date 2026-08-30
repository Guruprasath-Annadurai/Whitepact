# Phase 3 — Cryptographic/Structural Execution Binding

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH CLOSURE MASTER DIRECTIVE, Phase 3. Follows directly from Phase 2's decision (`PHASE2_EXECUTION_BOUNDARY_ARCHITECTURE.md`): extend `ExecutionAuthorization`'s structural binding without adding cryptographic signing.

## What changed

`ExecutionAuthorization` (`governance/execution.py`) gained four fields:

- `consent_reference: str | None` — which persisted `ConsentProof` (if any) backed the Heart legitimacy check that authorized this action.
- `policy_version: int | None` — read directly from `DecisionResult.policy_version`, always available, no separate parameter.
- `heart_legitimacy_digest: str | None` — `AuthorityGrant.legitimacy.canonical_digest`, when a real Heart check ran.
- `execution_id: str` — a fresh UUID distinct from `authorization_id`, identifying this specific execution attempt for future audit correlation.

Plus two fields added to the dataclass shape but **not populated by anything today**, named honestly rather than fabricated: `revocation_epoch` and `purpose`. No live caller produces either value yet — `resolve_authority_grant()` doesn't query `RevocationEpochRepository` at grant time, and no `ActionRequest` carries a requested purpose. `authorize_execution()` has no parameters for them, and a test locks in that absence so a future change can't start silently fabricating a value.

**A real gap found and fixed along the way**: `AuthorityGrant.consent_reference` has existed since `authority_grant.py`'s own Phase 1 build, but `authority_resolver.py::resolve_authority_grant()` — the only function that actually knows which consent backed a grant — never populated it. Fixed: `consent_reference=consent.consent_id if consent is not None else None` now passed to `build_authority_grant()`.

**Wiring, both live call sites**: `_heart_legitimacy_denied_reason()` in both `governance_integration.py` and `upstream_dispatch.py` now returns `(denied_reason, grant)` instead of just `denied_reason` — the resolved `AuthorityGrant` is exposed to the caller whenever the Heart check actually ran, so `authorize_execution()` can bind `grant.consent_reference`/`grant.legitimacy.canonical_digest` into the authorization it builds next. `resume_approval()`'s own E6 re-check (`recheck_grant`) is wired the same way.

## Why no signature (re-confirming Phase 2's decision, not re-litigating it)

These fields are audit/provenance binding, not independently re-validated against a "current" value at `execute()` time — unlike `target_fingerprint`, which genuinely has a fresh, recomputable value to check drift against (an upstream server's resolved config can change between decision and execution). A decision's policy version and the consent/legitimacy verdict that produced it are properties of the decision itself, computed a few lines before `authorize_execution()` is called in the same synchronous call graph — there is no meaningful "current" value to recompute and compare. Signing them would protect against a threat model (an attacker forging this in-process object) that already requires arbitrary code execution in the process, at which point — per `execution.py`'s own pre-existing, correct reasoning — signing verifies nothing.

## Tests

- `tests/test_executor_bypass_invariant.py::TestExecutionAuthorizationCarriesProvenanceFields` — 6 new tests: correct `policy_version` population/absence, correct `consent_reference`/`heart_legitimacy_digest` population/absence, the honest `revocation_epoch`/`purpose` non-population locked in, `execution_id` uniqueness.
- `tests/test_authority_resolver.py` — extended two existing tests: consent-backed grant stamps `consent_reference`; no-applicable-consent grant leaves it `None`.
- `tests/test_heart_production_gauntlet.py` — extended the full-chain test with a `consent_reference` assertion.
- `tests/test_heart_wiring_phase6.py::TestExecutionAuthorizationBoundToConsentThroughLiveDispatch` — the strongest test: intercepts the real `authorize_execution()` call the live, consent-backed hosted-MCP dispatch path makes (not the isolated function), and confirms it was actually called with the right `consent_reference` and a real `heart_legitimacy_digest` string.

## Verification

- Full suite: **3346 passed, 1 skipped, 0 failed** (was 3339 before Phase 3 — 7 new tests, 0 regressions).
- `ruff check` / `ruff format --check`: clean.
- `mypy`: clean on every file this phase touched (pre-existing, unrelated `IdentityContext(kind=str)` pattern noted in the touched test files, matching this codebase's own established style, not a new issue).

## Phase 3 verdict

**READY TO ADVANCE.** The structural binding is real, tested through the actual live dispatch path (not just unit-level), and the two fields with no live data source stay honestly empty rather than fabricated. Per the directive's own instruction — stopping here, awaiting direction before Phase 4 (replay protection).
