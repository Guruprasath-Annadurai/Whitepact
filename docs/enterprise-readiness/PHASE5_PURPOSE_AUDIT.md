# Phase 5 — Purpose Binding: Rule 0 Audit

**Directive**: WHITEPACT ENTERPRISE READINESS — PHASE 5. No code changed to produce this document.

**Starting SHA**: `b017bad2a15a7fc70be8e866f6532b921b3dec5e`
**Branch**: `security/heart-production-closure` (PR #55)

---

## Every existing representation of purpose/intent/scope, traced to source

| Component | Existing purpose semantics | Source | Destination | Enforced? | Gap |
|---|---|---|---|---|---|
| `ConsentProof.purpose: str` | Free text, **required** at construction (`build_consent_proof()`'s `purpose` positional param has no default) — the subject's declared reason for consenting. | `governance/consent_proof.py:107,152` | Persisted (`governance_consent_proofs.purpose`), returned in `to_dict()` | **No** — descriptive only. Never compared against anything at resolution time. | This is the gap Phase 5 closes. |
| `PurposeBinding` (Heart Phase H5) | A record type wrapping a `ConsentProof` + `IntentContract` pair. `validate_purpose_binding()` checks the binding's own `purpose` matches the referenced `ConsentProof.purpose` **verbatim** — module docstring explicitly rejects semantic/fuzzy matching ("never machine-parsed... silently accepting close enough is exactly what constitutional law H4 exists to prevent"). | `governance/purpose_binding.py` | Nowhere — module docstring's own "Not built here" section: "any wiring from a real authorization flow... and any DB persistence layer." | **No** — the primitive exists, zero live callers construct one. Confirmed by grep: only referenced in its own tests and `sovereignty_kernel.py`'s optional-input handling. | Deliberately not reimplemented by Phase 5 — see "Design decision" below for why. |
| `IntentContract.goal: str` | Free text, "never machine-parsed" (module's own docstring). `allowed_targets`/`denied_targets`/`allowed_action_types` are STRUCTURED scoping fields — the same shape I (Gap A, prior session) later added independently to `ConsentProof` without reconciling the two. | `governance/intent.py:53-103` | `sovereignty_kernel.evaluate()`'s optional `intent` param | **No live wiring** — same as `PurposeBinding`, zero real callers construct/pass one. | Genuine architectural duplication between `IntentContract`'s scoping fields and `ConsentProof.allowed_action_types`/`allowed_targets` (Gap A). Named honestly, not fixed here — reconciling two independently-evolved primitives is a larger refactor than Phase 5's scope; see "Known limitations." |
| `ActionRequest` | **No purpose field at all.** `agent`, `action_type`, `target`, `arguments`, `action_id`, `proposed_at` only. | `governance/models.py:502-514` | N/A | N/A | **The actual missing piece.** No "requested purpose" exists anywhere on the object every dispatch path builds. Phase 5 must add it. |
| `PolicyRule` | Matches on `risk_tiers`/`action_types`/`targets` only. No purpose concept whatsoever. | `governance/policy.py:41-60` | `Policy.evaluate()` | N/A | Policy engine has no purpose dimension to enforce or violate today. |
| `AuthorityGrant.requested_purpose: str \| None` | Field exists (`authority_grant.py:120`), **never populated** — confirmed by grep: `authority_resolver.py`'s `build_authority_grant()` call passes `root_reference`/`consent_reference` but not `requested_purpose`. | `governance/authority_grant.py` | `build_authority_grant()`'s `to_dict()`, `canonical_digest` computation (already includes it — see below) | **No** | Phase 3 (prior) named this explicitly as deferred: "no `ActionRequest` field represents a requested purpose... this phase does not invent one." |
| `ExecutionAuthorization.purpose: str \| None` | Field exists (`execution.py`, Phase 3), **never populated** — `authorize_execution()` has no `purpose` parameter. Phase 3's own test (`test_revocation_epoch_and_purpose_have_no_way_to_be_populated_yet`) locks in this exact absence. | `governance/execution.py` | Nowhere — dead field today | **No** | Same Phase 3 deferral. |
| `governance_approvals` table / `ApprovalRequest` | **No purpose column at all.** `build_approval_request()`/`build_resume_action()` round-trip `action_type`, `target`, `arguments` — not purpose (there is nothing to round-trip yet). | `db/engine.py:437-475`, `governance/approval.py:125-150,203-225,227-` | N/A | N/A | A purpose set on a future `ActionRequest` would be **silently lost** across a REQUIRE_APPROVAL → resume cycle unless persisted. Real gap for Section 9's requirement. |
| `compute_action_digest()` | SHA-256 over `action_type`/`target`/`arguments` only — the exact mutation-detection mechanism `authorize_execution()`/`ApprovalRequest.action_digest` both already rely on for "did this action change since it was authorized." | `governance/approval.py:72-95` | `ExecutionAuthorization.action_digest`, `ApprovalRequest.action_digest` | N/A (mechanism, not itself a purpose check) | **Reusable, not a gap**: if `ActionRequest.purpose` is added and included here, mutation detection for purpose comes for free through machinery already tested and already load-bearing for two other flows. |

### Production call sites of the four functions the directive names

Confirmed by grep, exhaustive:

- `resolve_authority_grant(`: 3 hits — its own definition (`authority_resolver.py`), `mcp/governance_integration.py`'s `_heart_legitimacy_denied_reason()`, `mcp/upstream_dispatch.py`'s `_heart_legitimacy_denied_reason()`. (A third caller, `resume_approval()`'s own E6 recheck, calls it directly too — 4 real call sites total once `resume_approval()`'s own inline call is counted.)
- `authorize_execution(`: 3 real call sites — `apply_governance()` (`governance_integration.py`), `apply_upstream_governance()` (`upstream_dispatch.py`), `resume_approval()` (`governance_integration.py`).
- `InternalToolExecutor(`: constructed fresh per call as of Phase 4 — 2 sites (`apply_governance()`, `resume_approval()`'s internal-tool branch).
- `UpstreamMCPExecutor(`: 3 sites — `dashboard/app.py`'s `upstream_call_tool()`, `resume_approval()`'s upstream-approval branch, plus test fixtures.

This matches exactly the set of call sites already touched by Phases 3 and 4 — no new, previously-unknown execution path exists.

---

## Design decision: canonical purpose model

**Chosen**: reuse `ConsentProof.purpose: str` (existing, already-required field) as the authoritative "authorized purpose." Compatibility is **exact string match** between a new `ActionRequest.purpose` and `consent.purpose` — not a dotted-taxonomy identifier system, not semantic/fuzzy matching.

**Why, not a new taxonomy**: the directive's own escape hatch ("if WhitePact's existing model requires a different representation, document why") applies directly. This codebase already has TWO independently-built purpose-adjacent primitives (`ConsentProof.purpose`, `IntentContract.goal`), both explicitly free text, and `PurposeBinding` — the one module that already tried to formalize purpose compatibility — **already made and documented this exact decision**: exact-string match, no semantic comparison, specifically to prevent purpose-drift. Inventing a competing dotted-identifier taxonomy (`analytics.read`, etc.) now would be the "parallel policy subsystem" the directive explicitly says not to build, and would leave THREE incompatible purpose representations in the codebase instead of reconciling toward one.

**Why exact-string match is still a real security primitive, not "arbitrary free text"**: the directive's bad examples (`purpose="because user asked"`) describe *unvalidated, uncompared* free text used as if it were meaningful on its own. That is not what this design does — the security property here comes from **exact equality against a specific, previously-persisted, already-authorized value**, not from the string's own content being structured. A SHA-256 digest is also "just a string," and it is exactly this codebase's existing security primitive for action mutation detection (`compute_action_digest()`). Purpose compatibility reuses the identical pattern: match-or-deny against a stored value, fail-closed on any mismatch.

**What Phase 5 does NOT do**: build `PurposeBinding`'s live wiring, or reconcile `IntentContract`'s scoping fields with `ConsentProof.allowed_action_types`/`allowed_targets`. Both are real, adjacent gaps this audit found but did not invent a fix for — see "Known limitations" in the closing evidence report.

## Where purpose compatibility becomes mandatory (fail-closed)

`ActionRequest.purpose` is added as **optional** (`str | None = None`) — a hard requirement on every existing `ActionRequest` construction site would be an immediate breaking change across dozens of call sites and every prior phase's own test suite, the same class of mistake self-caught and reverted earlier this session for `ConsentProof.build_consent_proof()`'s `allowed_action_types`.

The **mandatory, fail-closed** rule: whenever `action.purpose is not None` (the caller opted in to purpose-aware authorization) **and** a consent-backed grant is otherwise applicable (action-type/target scope already matched), the consent is **not applicable** unless `action.purpose == consent.purpose` exactly. This is the same fail-closed-by-omission shape Gap A already established for `allowed_action_types` — an empty/mismatched value never silently passes.

**Named honestly, not hidden**: no live MCP tool-call schema on either hosted dispatch path (Streamable HTTP/SSE, upstream proxy) has a protocol-level field for "what purpose is this call for" today — MCP tool arguments are the tool's own schema, not a governance envelope field. This means the new enforcement mechanism is real, structural, and tested end-to-end, but **not yet exercised by live traffic on the current dispatch paths**, since nothing populates `action.purpose` there yet. This mirrors this session's own established honesty pattern (Gap D's S3 verification: real code, environment cannot exercise it live) rather than fabricating a purpose source that doesn't genuinely exist in the current protocol.

## Persistence changes required

1. `governance_approvals.purpose` (new nullable column, migration) — otherwise a purpose set on a queued action is silently lost across REQUIRE_APPROVAL → resume, defeating Section 9's requirement before it can even be tested.
2. `PolicyRule.allowed_purposes: frozenset[str] | None = None` (in-memory dataclass field, no persistence — `Policy`/`PolicyRule` are not currently DB-row-mapped 1:1 the way approvals are; confirmed by reading `db/policy_repository.py`'s own (de)serialization, which already round-trips arbitrary rule fields via JSON).

## Backward compatibility

Every existing persisted `ConsentProof`, `ApprovalRequest`, and any future `ExecutionAuthorization` continues to behave identically: `action.purpose` defaults `None`, and the new check only activates when a caller explicitly supplies a requested purpose. No historical row is reinterpreted as "unrestricted" — the check simply does not fire for a caller that never opts in, matching this session's own established pattern for every prior optional-field addition (Gap A, Gap B, Phase 3, Phase 4).
