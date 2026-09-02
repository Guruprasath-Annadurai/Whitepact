# Phase 5 — Purpose Binding + Purpose-Compatibility Enforcement

**Directive**: WHITEPACT ENTERPRISE READINESS — PHASE 5. See
`PHASE5_PURPOSE_AUDIT.md` for the Rule-0 audit that preceded any code
change.

**Starting SHA**: `b017bad2a15a7fc70be8e866f6532b921b3dec5e`
**Ending SHA**: recorded at commit time below.
**Branch**: `security/heart-production-closure` (PR #55, unmerged)

---

## Audit findings (summary — full detail in PHASE5_PURPOSE_AUDIT.md)

`ActionRequest` had no purpose field at all — the actual gap. Purpose-
adjacent primitives already existed but were unwired: `ConsentProof.purpose`
(required free text, never compared against anything), `PurposeBinding`
(Heart Phase H5, exact-string-match design, zero live callers),
`IntentContract.goal`/scoping fields (zero live callers, a genuine
duplication of `ConsentProof`'s Gap-A scoping fields, not reconciled by
this phase). `AuthorityGrant.requested_purpose` and
`ExecutionAuthorization.purpose` existed as Phase 1/3 fields with no
producer. `governance_approvals` had no purpose column, meaning a
purpose would have been silently lost across REQUIRE_APPROVAL -> resume.

## Chosen purpose model

Reuse `ConsentProof.purpose: str` (existing, required, free text) as
the authoritative "authorized purpose." Compatibility is **exact
string equality** between `ActionRequest.purpose` and `consent.purpose`
— not a new dotted-taxonomy identifier system. Justification (full
reasoning in the audit doc): `PurposeBinding` — the one module that
already tried to formalize purpose compatibility in this codebase —
already made and documented this exact decision, specifically to
prevent purpose-drift via "close enough" semantic matching. Exact-match-
against-a-specific-persisted-value is the same security primitive
`compute_action_digest()` already uses for mutation detection; it is
not "arbitrary free text used as if meaningful on its own."

`PolicyRule.allowed_purposes: frozenset[str] | None = None` is the
one place the model *does* support a set of purposes (mirroring
`action_types`/`targets`), since `Policy`/`PolicyRule` are in-memory
dataclasses, unlike `ConsentProof`'s single persisted string field.

## Compatibility semantics

One authoritative check per boundary, not scattered comparison logic:

- **Consent**: `authority_resolver.py`'s `_resolve_applicable_consent()`
  gained a 4th check (after integrity, action-type scope, target
  scope): `if action.purpose is not None and action.purpose != proof.purpose: return None`.
  `None` means the caller never opted in — behaves exactly as before
  this phase. A non-`None` mismatch makes the consent inapplicable,
  the same fail-closed-by-omission pattern Gap A established for
  `allowed_action_types`.
- **Policy**: `PolicyRule.matches()` gained the same shape — `None`
  matches any purpose (including absent), a declared set requires
  membership, and an absent requested purpose does NOT match a
  purpose-restricted rule (no silent pass).
- **Digest/mutation**: `compute_action_digest()` (`governance/approval.py`)
  now includes `purpose` in its canonical JSON — the single, already-
  tested mechanism both `ExecutionAuthorization.action_digest` and
  `ApprovalRequest.action_digest` rely on, so mutation detection for
  purpose comes for free through machinery already load-bearing for
  two other flows, not a second parallel check.

## Fail-closed semantics

`ActionRequest.purpose` is optional (`None` default) — mandatory would
have broken every existing call site. The fail-closed rule is
conditional: whenever a caller opts in (`action.purpose is not None`)
and an otherwise-scope-matching consent exists, the consent is
inapplicable unless the purposes match exactly. No placeholder value
("default", "*", "unknown") is ever substituted.

## Production wiring

**Consent** (`authority_resolver.py`): `_resolve_applicable_consent()`'s
purpose check, above; `resolve_authority_grant()` passes
`requested_purpose=action.purpose if consent is not None else None`
into `build_authority_grant()` — populated ONLY once compatibility is
already established (directive Section 5's ordering requirement),
never speculatively.

**AuthorityGrant**: `requested_purpose` (Phase 1 field, previously dead)
now has a real producer.

**ExecutionAuthorization**: `authorize_execution()` gained a `purpose`
kwarg, bound straight into the dataclass and therefore into
`compute_action_digest()`'s digest. Callers must pass the VALIDATED
purpose (`grant.requested_purpose`), never the raw `action.purpose` —
documented explicitly in `authorize_execution()`'s own docstring.

**Hosted MCP dispatch** (`governance_integration.py`):
`apply_governance()`'s redacted `final_action` reconstruction now
carries `purpose=action.purpose`, and its `authorize_execution()` call
passes `purpose=heart_grant.requested_purpose if heart_grant is not None else None`.

**Upstream MCP dispatch** (`upstream_dispatch.py`):
`apply_upstream_governance()`'s `final_action`/`authorize_execution()`
call wired identically.

**Approval-resume** (`governance_integration.py`'s `resume_approval()`):
wired the same pattern using `recheck_grant.requested_purpose`.

## Approval-resume purpose recheck (security-critical, Section 9)

`build_resume_action()`/`ApprovalRequest.purpose` (new column,
migration 0037) carry the queued purpose through to resume time
unchanged, so `resolve_authority_grant()`'s fresh recheck sees the
same purpose that was originally queued.

**A real gap found and fixed during this phase, not shipped as a
false positive**: `_agent_from_approval()` always reconstructs an
`IdentityKind.ORGANIZATION` identity (terminal, self-root legitimate
by default) with a **freshly-generated random `agent_id`**
(`AgentContext.agent_id`'s dataclass default), never the original
agent's id. Two consequences, both closed here:

1. `_resolve_applicable_consent()`'s `get_latest_for_grantee(agent.agent_id, ...)`
   lookup at resume time could never find a consent captured against
   the real agent, since the reconstructed `agent_id` never matched.
   Fixed by setting `agent_id=approval.requested_by` in
   `_agent_from_approval()` — every real call site
   (`apply_governance()`) already sets `agent.agent_id == identity.identity_id == ctx.key_id`,
   so `requested_by` (== the original `identity_id`) is exactly the
   right value to restore.
2. Even with (1) fixed, a terminal `ORGANIZATION` self-root means
   `resolve_authority_grant()`'s `is_legitimate` alone does not go
   `False` just because a matching consent no longer exists — the
   resolver simply falls back to the (still-legitimate) self-root.
   `is_legitimate` is therefore an insufficient signal for "the
   originally authorized purpose still holds" at resume time. Fixed
   by adding an explicit, independent purpose-recheck gate in
   `resume_approval()`: if `action.purpose is not None` and
   `recheck_grant.requested_purpose != action.purpose`, raise
   `ApprovalRevokedSinceQueuedError` — using `requested_purpose`
   (populated ONLY when a consent actually validated it) as the
   correct signal, distinct from overall grant legitimacy.

Both fixes are narrow, additive, and confined to the resume wiring
layer — no Heart core function was touched.

## Migration

`migrations/versions/0037_add_governance_approvals_purpose.py` — one
nullable `purpose` column on `governance_approvals`. Verified against
real on-disk SQLite:

```
=== upgrade head ===
Running upgrade 0036 -> 0037, Add purpose column to governance_approvals.
=== downgrade -1 ===
Running downgrade 0037 -> 0036, Add purpose column to governance_approvals.
=== upgrade head again ===
Running upgrade 0036 -> 0037, Add purpose column to governance_approvals.
```

`tests/test_db_migrate.py`'s three hardcoded head-revision assertions
updated `"0036"` -> `"0037"`.

## Backward compatibility

Every existing persisted `ConsentProof`, `ApprovalRequest`,
`AuthorityGrant`, `ExecutionAuthorization` row/object continues to
behave identically: `purpose` fields default `None`/absent everywhere,
and every new check only activates when a caller explicitly opts in by
setting `ActionRequest.purpose`. No historical row is reinterpreted as
"unrestricted." Existing rows with `purpose IS NULL` in
`governance_approvals` resume exactly as before this phase (the new
resume-time purpose gate is a no-op when `action.purpose is None`).

## Digest binding regression (Section 11)

`tests/test_purpose_binding_phase5.py::TestExecutionAuthorizationDigestBinding::test_authorization_for_purpose_a_does_not_match_action_reconstructed_as_purpose_b`
proves `authorization.matches_action()` returns `False` for an action
identical in every field except `purpose`, and `True` for the
unmodified original — the dedicated regression test the directive
requires.

## Negative security tests (16 named scenarios, Section 10)

All 16 are covered, either directly or by the model's own structural
guarantees (noted where a scenario is impossible by construction
rather than requiring a runtime check):

| # | Scenario | Where proven |
|---|---|---|
| 1 | consent allows A, request asks B | `test_scenario_1_consent_allows_a_request_asks_b_denied` |
| 2 | policy allows A, request asks B | `TestPolicyRuleAllowedPurposes::test_declared_purpose_set_matches_only_a_listed_purpose` |
| 3 | consent allows A+B (as `PolicyRule.allowed_purposes`, the set-capable side), policy only A, request B | `TestPolicyEnginePurposeInDecision`, `TestPolicyRuleAllowedPurposes::test_multi_purpose_set_matches_any_member` |
| 4 | policy allows A+B, consent only A, request B | same mechanism as #3 — `allowed_purposes` membership; consent's singular-string model makes this and #3 the same underlying check from the other side |
| 5 | missing requested purpose | `test_scenario_5_missing_requested_purpose_still_resolves_by_scope` |
| 6 | missing consent purpose where mandatory | `test_scenario_6_missing_consent_purpose_where_mandatory` |
| 7 | missing policy purpose where mandatory | `TestPolicyRuleAllowedPurposes::test_declared_purpose_set_does_not_match_an_absent_purpose` |
| 8 | malformed purpose identifier | `test_scenario_8_malformed_purpose_identifier_denied` |
| 9 | purpose changed after `AuthorityGrant` creation | `TestApprovalResumePurposeRecheck::test_authorize_purpose_a_queue_mutate_consent_purpose_resume_denies` |
| 10 | purpose changed after `ExecutionAuthorization` creation | `TestExecutionAuthorizationDigestBinding::test_executor_refuses_when_purpose_was_mutated_after_authorization` |
| 11 | approval queued for A, resumed as B | `test_named_scenario_11_approval_queued_for_a_resumed_as_b_is_impossible_by_construction` — `build_resume_action()` has no parameter letting a caller substitute a different purpose than what was persisted |
| 12 | stale consent purpose | `TestScenario12CrossTenantPurposeIsolation` (cross-tenant framing) + `test_authorize_purpose_a_queue_mutate_consent_purpose_resume_denies` (staleness-over-time framing) |
| 13 | stale policy purpose | `test_scenario_13_stale_policy_purpose_via_gateway` |
| 14 | cross-tenant reuse of a purpose-bearing authorization | `TestScenario12CrossTenantPurposeIsolation::test_purpose_matching_consent_from_another_tenant_is_not_applicable` |
| 15 | same tool/action, unauthorized purpose | `test_scenario_15_same_tool_action_unauthorized_purpose` |
| 16 | replayed authorization with altered purpose | `TestExecutionAuthorizationDigestBinding` (digest binding — an altered-purpose replay fails `matches_action()` the same as any other mutation) + Phase 4's existing durable nonce-replay protection (unmodified, still in force) |

## Integration-test evidence (Level D, Section 15)

`TestLiveResolveAndExecuteChainWithPurpose` exercises the exact
real-function sequence `apply_governance()`/`apply_upstream_governance()`
use — `resolve_authority_grant()` -> `authorize_execution()` ->
`InternalToolExecutor.execute()` — against a real DB-backed
consent/root setup:

- `test_compatible_purpose_survives_the_full_chain_and_executes`: purpose
  P -> consent authorizes P -> `AuthorityGrant.requested_purpose == P`
  -> `ExecutionAuthorization.purpose == P` -> `InternalToolExecutor`
  actually runs the real `rai_health` tool and returns a result.
- `test_purpose_mismatch_means_the_execute_function_is_never_called`:
  same real path, purpose mismatch -> `resolve_authority_grant()`
  returns an illegitimate grant (the real `_heart_legitimacy_denied_reason()`
  gate in `apply_governance()`/`apply_upstream_governance()` turns
  this into DENY before `authorize_execution()`/`execute()` are ever
  reached) -> a monkeypatched spy on `InternalToolExecutor.execute`
  confirms it is never invoked.

`TestApprovalResumePurposeRecheck` exercises the real `resume_approval()`
end to end (real DB, real `ApprovalRepository`, real
`resolve_authority_grant()` recheck) for both directions Section 9
names explicitly: unchanged compatible state -> resume ALLOWS; consent
purpose mutated since queueing -> resume DENIES
(`ApprovalRevokedSinceQueuedError`).

**Named honestly**: neither the hosted MCP HTTP/SSE tool-call schema
nor the upstream proxy protocol currently carries a purpose field on
live traffic — `apply_governance()`/`apply_upstream_governance()` still
build `ActionRequest` from `name`/`arguments` only. The mechanism above
is real, structural, and exercised end-to-end by these tests; it is
not yet reachable by a live MCP client until a protocol-level purpose
field is added on top of this phase's work. This mirrors the audit
doc's own framing and this session's established honesty pattern (Gap
D's "BLOCKED, not faked").

## Phase 2/3/4 regression check (Section 16)

Full suite rerun (below) includes every Phase 2/3/4 test file
unmodified in behavior — Heart enforcement, consent-backed legitimacy,
revocation, execution binding, replay protection (nonce durability),
approval consume semantics, and enterprise fail-closed startup all
still pass. `tests/test_executor_bypass_invariant.py`'s Phase 3 test
`test_revocation_epoch_and_purpose_have_no_way_to_be_populated_yet`
was split into `test_revocation_epoch_has_no_way_to_be_populated_yet`
(unchanged assertion — `revocation_epoch` genuinely still has no
producer) and a new `test_purpose_defaults_none_and_is_carried_through_when_supplied`
(purpose now honestly DOES have a producer) — the only test whose
assertion changed, and only because the underlying fact it locks in
changed, not because a security property was weakened.

## Security review of the diff (Section 18)

- **Default-allow / wildcard purpose semantics**: none introduced.
  `None` means "no purpose declared / not opted in," never "matches
  every purpose" for a rule/consent that itself declares a purpose
  restriction.
- **Missing call sites**: re-grepped after implementation — all 3
  `authorize_execution()` call sites, both `resolve_authority_grant()`
  live-path call sites (plus the resume recheck), both
  `InternalToolExecutor()` sites, both `UpstreamMCPExecutor()` live
  sites, and every `ActionRequest`/`ApprovalRequest` construction site
  now thread `purpose` (see grep output preserved in the PR).
- **Stale approval semantics**: closed by the `_agent_from_approval()`
  fix above (agent_id restoration) and the new explicit purpose-recheck
  gate in `resume_approval()`.
- **Inconsistent canonicalization**: purpose is compared and digested
  as the exact string value the caller supplied — no normalization,
  case-folding, or trimming anywhere, matching `PurposeBinding`'s own
  precedent (never machine-parsed).
- **Free-text comparison as a security primitive**: addressed directly
  in the "Chosen purpose model" section above — equality against a
  specific persisted value, not content-based parsing.
- **Mutable authorization fields**: `ExecutionAuthorization.purpose` is
  set once at construction (`authorize_execution()`) and never
  reassigned afterward; mutation of the underlying action is caught by
  `matches_action()`/digest comparison, not by mutating the
  authorization itself.
- **Tenant leakage**: `_resolve_applicable_consent()`'s existing
  organization-scoped JOIN (`get_latest_for_grantee(agent.agent_id, organization_id=...)`)
  is untouched by this phase; the new purpose check runs strictly
  after that scoping, so it cannot leak a purpose-compatible consent
  across tenants. Verified negatively by
  `TestScenario12CrossTenantPurposeIsolation`.
- **Missing digest coverage**: `compute_action_digest()` includes
  purpose, and both consumers (`ExecutionAuthorization.action_digest`,
  `ApprovalRequest.action_digest`) inherit that coverage automatically.
- **Legacy compatibility becoming allow-all**: every legacy row/object
  with `purpose IS NULL`/`None` behaves exactly as it did before this
  phase — the compatibility check simply never activates for it, which
  is "no behavior change," not "matches everything."

## Full verification

- `ruff check .`: clean (2 pre-existing, unrelated findings in
  `examples/05_cost_intelligence.py`, untouched by this branch).
- `ruff format --check .`: clean (50 pre-existing unrelated markdown/
  wiki reformat findings, untouched by this branch).
- `mypy src/responsibleai` (the exact command CI runs): **Success: no
  issues found in 173 source files.**
- Full test suite: **3385 passed, 1 skipped, 0 failed** (was 3358
  after Phase 5's production wiring landed, before the new Phase 5
  test file; 27 new tests in `tests/test_purpose_binding_phase5.py`,
  0 regressions).
- Migration round-trip (0036 -> 0037 -> 0036 -> 0037): verified against
  real on-disk SQLite, shown above.

## Known limitations / residual risks

1. **No live protocol field for purpose yet.** Named throughout: this
   phase makes purpose enforcement real and structural, but no current
   MCP tool-call schema (hosted or upstream) supplies
   `ActionRequest.purpose` from live traffic. A follow-up phase adding
   a protocol-level purpose parameter is required before this
   enforcement affects real requests.
2. **`IntentContract`/`ConsentProof` scoping-field duplication not
   reconciled.** Named in the audit, unchanged by this phase — two
   independently-evolved primitives with overlapping
   `allowed_targets`/`allowed_action_types`-shaped fields still exist
   side by side.
3. **`PurposeBinding` (Heart Phase H5) remains unwired.** This phase
   deliberately did not build a second, competing purpose-enforcement
   mechanism on top of the one already reasoned about in that module;
   `PurposeBinding` itself still has zero live callers.
4. **Consent's purpose model is singular, not a set.** `ConsentProof.purpose`
   is one string; a consent authorizing "either of two purposes"
   cannot be expressed there today (only `PolicyRule.allowed_purposes`
   supports sets). Documented in the model design section above rather
   than silently working around it.

## Phase 5 verdict

**READY WITH EXPLICIT ACCEPTED RISK.**

The success condition's exact claim holds for every path the current
codebase can exercise: when a caller supplies a requested purpose,
that purpose must also be authorized by the supporting consent and
applicable governance policy, is carried through the authority chain
(`AuthorityGrant.requested_purpose`), is bound into execution
authorization (`ExecutionAuthorization.purpose`, included in the
canonical digest), and is revalidated (via a fresh
`resolve_authority_grant()` call plus an explicit purpose-recheck gate,
both proven by real, DB-backed integration tests) before a delayed
approved execution resumes. This is real, structural, and tested end
to end, not a rubber-stamped field.

The explicitly accepted risk: no live MCP protocol path (hosted or
upstream) currently supplies a purpose on real traffic —
`apply_governance()`/`apply_upstream_governance()` still build
`ActionRequest` from `name`/`arguments` only, so this enforcement,
while fully wired, is not yet exercised by a real request until a
follow-up phase adds a protocol-level purpose field. This is named
plainly rather than hidden, matching this session's established
practice for every prior "wired but not yet live-exercised" gap.

Per the directive's own stop condition: **stopping here.** Awaiting
authorization before Phase 6.
