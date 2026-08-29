# Phase 14 — Resilience + Fail-Closed Operations: Design

## Objective

Per the master directive's Phase 14 and `00_PHASE0_AUDIT.md` §7's own
sequencing note ("resilience/fail-closed matrix"). `THREAT_MODEL.md`
§3 already documents two specific, deliberately asymmetric cases:
evidence-write failures fail *closed* (block the call); Trust Index
lookup failures fail *open* (don't block). Per directive rule 63:
build the matrix by auditing every real dependency in the governed
decision path, not by inventing new failure-handling machinery.

## Audit: every external dependency `apply_governance()` calls before/around the decision

Reading `mcp/governance_integration.py`'s `apply_governance()` in
full, in call order:

| Dependency | Guarded by try/except? | Existing regression test? |
|---|---|---|
| `services.ceiling_repo.get()` | No | No |
| `recent_violation_count()` (`evidence_repo`) | No | No |
| `services.policy_repo.get_policy()` | No | No |
| `services.delegation_repo.get_latest_delegation()` | No | No |
| `services.workflow_rule_repo.get_rules()` | No | No |
| `services.evidence_repo.list_recent_actions()` (only when workflow rules exist) | No | No |
| `services.autonomy_budget_repo.get()` | No | No |
| `recent_autonomous_action_count()` (only when a budget exists) | No | No |
| `services.intent_repo.get_active_for_agent()` | No | No |
| `services.gateway.evaluate()` | No | **Yes** — `tests/test_mcp_governance_dispatch.py::TestAuthoritySubsystemCrashFailsClosed` |
| `services.evidence_repo.record()` | **Yes**, explicit | **Yes** — `TestEvidenceWriteFailsClosed` |
| Trust Index HTTP lookup | **Yes**, explicit (fails open by design) | **Yes** — `test_governance_trust_state.py` |

**The pattern already established, generalized**: none of the nine
pre-`evaluate()` dependency calls has an explicit `try/except` — an
exception from any of them propagates out of `apply_governance()`
exactly the same way `TestAuthoritySubsystemCrashFailsClosed` already
proves happens for `gateway.evaluate()` itself: before evidence is
written, before `authorize_execution()`/`InternalToolExecutor` is ever
reached, so the underlying tool structurally cannot have run. This is
the deliberate design already in place — SPEC.md/`THREAT_MODEL.md`'s
own reasoning for the evidence-write case ("an unrecorded decision
should always block, since evidence is this platform's entire
audit-trail guarantee") applies with equal force to every dependency
that runs *before* evidence gets written: none of them should be able
to silently produce an ALLOW.

**What's missing**: this property was proven for exactly one of the
ten pre-evidence-write dependencies (`gateway.evaluate()`). The other
eight (`ceiling_repo`, `policy_repo`, `delegation_repo`,
`workflow_rule_repo`, `autonomy_budget_repo`, `intent_repo`, and the
two `recent_*_count()` helper calls) rely on the same propagation
mechanism but have never been individually regression-tested for it —
only true by code-reading, the same gap Phase 11 closed for
`_validate_authorization()`'s call sites and Phase 8 closed for
`ExecutionAuthorization`'s construction site.

## Genuine, narrowly-scoped gap this phase closes

Generalize `TestAuthoritySubsystemCrashFailsClosed`'s exact pattern
(monkeypatch a dependency to raise, call a real governed tool through
the live `governed_app` fixture, assert the result is never the tool's
real payload and no evidence record was fabricated) across the six
repository dependencies that are unconditionally reachable in the
`governed_app` test fixture's wiring (all six are always constructed
when `mcp_governance_enabled=True`, per `mcp/server.py`'s
`_build_http_app()`): `ceiling_repo.get()`, `policy_repo.get_policy()`,
`delegation_repo.get_latest_delegation()`,
`workflow_rule_repo.get_rules()`, `autonomy_budget_repo.get()`,
`intent_repo.get_active_for_agent()`.

**Deliberately not covered by this phase**: the two `recent_*_count()`
helper paths and `evidence_repo.list_recent_actions()` are only
reached under additional preconditions (an existing violation history,
a configured workflow rule) that would need extra fixture setup beyond
what a parametrized sweep over the always-reachable six can share —
real, correctly out of scope for this pass rather than silently
assumed covered, tracked as a residual gap.

## Scope for this phase

`tests/test_resilience_fail_closed_matrix.py`: one parametrized test
class sweeping the six dependencies above, each proving:
1. A crash never produces the tool's real success payload.
2. No evidence record was fabricated for the crashed call (the same
   double-check `TestAuthoritySubsystemCrashFailsClosed` already
   performs, generalized).

No source file changes. No new architecture. No database migration.
