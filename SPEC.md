# WhitePact — Architecture Specification

> **Status of this document**: this is the target architecture contract for
> WhitePact Enterprise Foundation v2. Sections are explicitly marked
> **[TODAY]** (verified against current source, working now) or
> **[TARGET]** (the architecture this spec defines, not yet built). Do not
> read a **[TARGET]** section as a claim that the described component
> exists — per this project's own engineering rules, implementation status
> is never assumed, only what's been inspected in source. See
> `MIGRATION_WHITEPACT_V2.md` (forthcoming) for the phased plan that
> closes the gap between the two.

Last reviewed: 2026-08-11 · Repository: `Guruprasath-Annadurai/Whitepact`
(renamed from `ResponsibleAi`; package identity migration in progress —
see Section 9). Sections 2-3's core entities, a first, deterministic
`WhitePactRuntimeGateway`, risk-tiered routing (Phase 9), and a first
policy engine (Phase 10) now exist in `src/responsibleai/governance/`
(see `MIGRATION_WHITEPACT_V2.md` Section 8) — each affected section
below has been updated in place to say exactly what's real and what
remains **[TARGET]**; none of the original **[TARGET]** markers were
removed wholesale.

---

## 1. What WhitePact is

**WhitePact is not "ResponsibleAI renamed." It is not "27 MCP governance
tools." It is not "an MCP gateway."**

WhitePact is an independent runtime authority, governance, and assurance
layer for autonomous systems.

> AI systems may decide what they want to do. WhitePact determines
> whether they should be allowed to do it.

The distinction that matters:

- **IAM answers**: *"Can this identity access this resource?"* — a
  static, pre-provisioned permission check.
- **WhitePact answers**: *"Should this autonomous action be permitted in
  this context, right now, given who's asking, what's been delegated to
  them, what the action actually is, and what the organization's policy
  says about it?"* — a dynamic, per-action decision.

**[TODAY]**: this project ships as a governance *evaluation* platform —
trust scoring, guardrails (PII/toxicity), hallucination detection, red
teaming, compliance mapping (NIST AI RMF / EU AI Act / ISO 42001), cost
intelligence, drift monitoring, a public leaderboard, a Trust Index, an
AI Incident Database, and 27 MCP tools exposing all of it. All of these
are real, tested, and running (verified: 1349 tests passing, mypy/ruff
clean, CI green on GitHub Actions as of commit `6ffe933`).

**[TARGET]**: WhitePact becomes a runtime decision layer that sits
*between* an agent's proposed action and the enterprise system it would
affect, using the existing evaluation capabilities as the intelligence
behind a five-way decision, not just a report a human reads after the
fact.

---

## 2. The core pipeline **[PARTIALLY TODAY — Phases 8-12]**

```
Organization
  → delegates authority to
Agent (identity + framework + model)
  → proposes
Action (an MCP tool call, an API operation, a transaction, a data export...)
  → evaluated against
Policy (deterministic organizational rules)              [TODAY, first version — Phase 10]
  → informed by
Trust (existing Trust Index / leaderboard signals)        [TODAY, not yet wired in]
  → and
Risk (classified severity of the action)                 [TODAY — Phase 9]
  → produces a
Decision: ALLOW | ALLOW_WITH_REDACTION | REQUIRE_APPROVAL | DENY | QUARANTINE
  → routes to
Execution (the actual MCP/API/SaaS/database call, only if allowed)
  → and always produces
Evidence (an immutable, exportable record of the whole decision) [TODAY, first version — Phase 12]
```

**[TODAY]**: `src/responsibleai/governance/` now has a real, tested
component that takes "agent proposes action" as input and returns one
of the five decisions above as output —
`WhitePactRuntimeGateway.evaluate(action, authority, policy=None)`
(`tests/test_governance_core.py` + `test_governance_risk.py` +
`test_governance_policy.py`, 49 tests across the package). Concretely,
today it checks, in order: (1) does the caller-supplied
`AuthorityContext` grant this action's type at all; (2) risk
classification (`governance/risk.py`) — every action gets a real
`RiskTier`, always recorded on the result; (3) an *optional*
organization `Policy` (`governance/policy.py`) — if supplied and a rule
matches, a `DENY`/`REQUIRE_APPROVAL` effect short-circuits, an `ALLOW`
effect is recorded but doesn't skip the next step; (4) does the
existing, tested `GuardrailsEngine` find PII (→
`ALLOW_WITH_REDACTION`, reusing its own redaction) or
toxicity/custom-pattern matches (→ `DENY`) in any string-valued
argument. A `DecisionResult` can now be turned into a persisted,
hash-chained `EvidenceRecord` (`db/evidence_repository.py`, Phase 12)
and a `REQUIRE_APPROVAL` decision into a persisted, resolvable
`ApprovalRequest` (`db/approval_repository.py`, Phase 11) — both real,
tested (`tests/test_governance_persistence.py`,
`tests/test_governance_api.py`), and exposed via
`/api/governance/evidence`, `/api/governance/evidence/verify`,
`/api/governance/approvals`, and
`/api/governance/approvals/{id}/resolve` in the dashboard API — see
Section 3.7 and MIGRATION_WHITEPACT_V2.md Section 8 for exactly what's
covered.

Three gaps this section used to flag as **[TARGET]** are now real,
tested, MIGRATION_WHITEPACT_V2.md Section 11 gap-closure work:
`GovernanceDecision.QUARANTINE` is reachable
(`governance/quarantine.py`'s cross-request violation tracking,
consulted before every other check); `AgentContext.trust_state` is
populated (`governance/trust_integration.py`) and consulted (a known,
low-scoring model downgrades an otherwise-`ALLOW` to
`REQUIRE_APPROVAL`); and the gateway is wired into the live, hosted MCP
tool-call dispatch path (`mcp/governance_integration.py`), opt-in via
`Settings.mcp_governance_enabled` — see that field's own docstring for
why it defaults to `False` rather than silently changing existing
hosted deployments' behavior. Genuinely still **[TARGET]**: a richer
policy rule language (OPA/Rego) beyond Section 3.5's flat matching, and
governing the self-hosted stdio transport (it has no organizational
identity to build an `AuthorityContext`/`Policy` against, so this
wiring only ever applies to org-scoped Streamable HTTP/SSE calls).

---

## 2.5 The WhitePact Heart (Sovereignty Kernel) **[TODAY, first version — Phases H0-H14]**

A new, deliberately small trusted-computing-base layer answering one
question, and only one: *why does this machine have the legitimate
right to exercise this authority at all* — logically prior to
everything in Section 3 below, which governs *how* an already-granted
authority gets checked against a specific proposed action.

**Canonical relationship**: `EXECUTABLE_AUTHORITY ⊆ BRAIN_AUTHORITY ⊆
HEART_AUTHORITY`. The Heart bounds the maximum legitimate authority
available to the existing gateway/policy/risk pipeline (the "Brain")
below — it does not replace, evaluate intelligence about, or make
suspicion judgments the way `WhitePactRuntimeGateway` already does.
Architecturally, the Heart sits *before* `WhitePactRuntimeGateway.evaluate()`
is ever called, not as one more check inside its existing
first-match-wins chain — see `docs/heart/HEART_CURRENT_STATE.md` §8
for why.

**Foundational law**: machines may exercise authority; machines may
never originate it. Every machine authority must trace to a legitimate
human- or organization-established root — no model, memory entry,
tool output, or prior ALLOW decision may manufacture missing
authority.

**[TODAY]**: `governance/constitution.py`'s `AuthorityConstitutionVersion`
— a versioned, immutable, digestible set of fifteen constitutional
laws (H1-H15) protecting the integrity of the authority mechanism
itself, distinct from the existing, deliberately org-mutable `Policy`
(§3.5). `CONSTITUTION_V1` ratifies all fifteen founding laws;
`_CONSTITUTION_HISTORY` is a `MappingProxyType` — a real, enforced
immutability guarantee, not a convention — so a historical
`constitution_version` reference can never silently mean something
different later. Deliberately not cryptographically signed in this
phase; full reasoning in `docs/heart/HEART_SIGNING_DECISION.md`.

**Full audit of what's reused vs. genuinely new** (root-of-authority,
consent proof, purpose binding, revocation epoch, the Heart veto
itself, and how each maps onto — or deliberately doesn't duplicate —
the existing `AuthorityContext`/`validate_attenuation`/`DelegationRepository`/
`IntentContract`/`AuthorityPassport` infrastructure documented in
Section 3 below): see `docs/heart/HEART_CURRENT_STATE.md`.

**[TODAY, Phase H2]**: `governance/authority_lattice.py`'s
`AuthorityEnvelope` — an explicit authority representation across
fifteen dimensions (action types, targets, resources, data scope,
max/max-total value, frequency, time window, environment,
jurisdiction, delegation depth, approval requirements, allowed/denied
tools, recipient restrictions), generalizing the informal dict-based
comparisons `AuthorityContext` already performs. `compare_envelopes()`
returns one of three outcomes — `LEGITIMATE_SUBSET`, `ESCALATION`, or
`UNREPRESENTABLE_CONSTRAINT` — never a bare boolean, so "fits within
the parent" and "this constraint isn't representable in the lattice"
stay distinguishable (constitutional law H10). `intersect_envelopes()`
combines multiple envelopes (root/org/intent/delegation/constitution/
context) via per-dimension intersection only — no operation in this
module can widen authority through union. `authority_context_to_envelope()`
raises `UnrepresentableConstraintError` rather than silently dropping
an `AuthorityContext.constraints` key the envelope has no dimension
for (e.g. `memory_scope`).

**A real, documented gap closed in the same phase**:
`validate_attenuation()` (`governance/models.py`) never checked
`constraints["allowed_hours_utc"]` for attenuation — its own docstring
said so, explicitly, since Phase 8. A delegated child could previously
claim a *wider* time window than its parent held, uncaught. Fixed by
extending the existing, live-used function directly (not routed
through the new lattice module, which stays dependency-free of
`governance.models` at runtime by design) — verified with a real
escalation case (parent `22:00-06:00`, child `20:00-06:00`, two extra
hours) that now correctly denies.

**[TODAY, Phase H3]**: `governance/root_authority.py`'s
`RootAuthorityRecord` and `validate_root_chain()` — the first
executable form of constitutional laws H1 ("every machine authority
has a legitimate root") and H2 ("machines cannot originate authority").
`RootType` distinguishes two terminal types (`HUMAN`, `ORGANIZATION` —
legitimate roots needing no further chain) from two non-terminal types
(`SERVICE_PRINCIPAL`, `WORKLOAD_IDENTITY` — must chain, via
`authority_source`, to a terminal root). `validate_root_chain()` walks
that chain against an abstract `RootResolver` (no `db.*` dependency,
per the Heart TCB-minimization principle already established in H1/H2)
with explicit, never-silent handling of every failure mode:
`ROOT_TYPE_CANNOT_SELF_ORIGINATE` (non-terminal, no source),
`SOURCE_NOT_FOUND` (dangling pointer), `CYCLE_DETECTED`,
`CHAIN_TOO_DEEP` (depth-bounded circuit breaker at 32 hops), and
`REVOKED`/`NOT_YET_VALID`/`EXPIRED` for any ancestor — including
intermediate ones — that fails its own temporal validity check.
`subject_id` is deliberately opaque (an identity_id, not a name or
email) — this module verifies authority provenance, not identity.
Not cryptographically signed, for the same reasoning as `governance/
constitution.py` (see `docs/heart/HEART_SIGNING_DECISION.md`).

**[TODAY, Phase H4]**: `governance/consent_proof.py`'s `ConsentProof`
and `validate_consent_proof()` — a structured, digest-bound record
that a specific human (or otherwise-legitimate root) actually
consented to a specific grant of authority, for a specific purpose,
distinguishable from mere authentication (`docs/heart/HEART_CURRENT_STATE.md`
§4 confirms no such concept existed before this phase).
`ConsentMethod` names how consent was actually captured (explicit UI
action, signed document, recorded verbal consent, an authenticated API
call, or a standing delegated policy) — never inferred, never
defaulted. `validate_consent_proof()` composes with Phase H3: it takes
an already-computed `RootValidationResult` for the claimed
`consenting_root_id` as a parameter rather than resolving the root
chain itself, keeping this module dependency-free of `root_authority.py`
at runtime (only imported under `TYPE_CHECKING`) — continuing the
TCB-minimization discipline H1-H3 already established. A consent proof
is only `VALID` when the passed-in root result is both for the exact
claimed root (`ROOT_MISMATCH` otherwise) and itself legitimate
(`ROOT_NOT_LEGITIMATE` otherwise), AND the proof itself is temporally
valid (`REVOKED`/`NOT_YET_VALID`/`EXPIRED` otherwise) — root legitimacy
is checked first, so an illegitimate root is never masked by also
reporting the consent's own, independent expiry.

**[TODAY, Phase H5]**: `governance/purpose_binding.py`'s
`PurposeBinding` and `validate_purpose_binding()` — the executable
form of constitutional law H4 ("authority remains bound to purpose").
Per `docs/heart/HEART_CURRENT_STATE.md` §4, this phase deliberately
**absorbs** the existing `governance/intent.py` `IntentContract`
rather than reimplementing a second purpose-scoping mechanism —
`PurposeBinding` wraps it by reference (`intent_ref` = a
`contract_id`), never duplicating its `allowed_action_types`/
`allowed_targets`/`max_value_usd` machinery. What `PurposeBinding`
adds is the piece that didn't exist before: tying a declared intent to
the exact `ConsentProof` (Phase H4) that authorized it, via
`consent_ref`, so authority consented to for one purpose cannot be
silently exercised under a different declared intent later.
`validate_purpose_binding()` composes with H4 the same way H4 composed
with H3: it takes an already-computed `ConsentValidationResult` as a
parameter rather than re-deriving it, and both `ConsentProof` and
`IntentContract` are imported only under `TYPE_CHECKING`. Purpose
matching is deliberately exact-string, never semantic — mirroring
`IntentContract.goal`'s own "never machine-parsed" precedent — so a
rephrased purpose requires a fresh `ConsentProof`, not a judgment call
about how "close enough" two purpose strings are.

**[TODAY, Phase H6]**: `governance/delegation_kernel.py`'s
`validate_delegation_legitimacy()` — composes the three independent
Heart legitimacy checks from H3-H5 (root, consent, purpose) with a
`DelegationRecord`'s own active/revoked/expired state into one
verdict. Per `docs/heart/HEART_CURRENT_STATE.md` §3, `DelegationRecord`
and `DelegationRepository` (`grant()`, `get_active_delegation()`,
`get_authority_chain()`, `revoke_branch()`, `get_org_graph()`,
`get_descendants()`) are already real, tested, and exactly what a
delegation kernel needs operationally — this phase does not rebuild
any of that, nor `DelegationGraph`/`DelegationGraphNode`'s existing
org-wide read-model (Authority Everywhere Phase 6). What was missing
is the Heart-level question none of those answer: even a
well-formed, correctly-attenuated delegation says nothing about
whether the delegator's own authority traces to a legitimate root, was
actually consented to, and stays bound to its declared purpose.
Ordering (`ROOT_NOT_LEGITIMATE` → `CONSENT_NOT_LEGITIMATE` →
`PURPOSE_NOT_BOUND` → `DELEGATION_NOT_ACTIVE`) mirrors the same
"upstream legitimacy before an object's own local state" principle H4
and H5 already established. Honestly documented limitation: since
`DelegationRecord` has no field linking it to a specific
`root_id`/`consent_id`/`binding_id` (it predates the Heart and is not
schema-changed by this phase, per its own REUSE classification), this
module cannot cross-check that the three results supplied actually
*pertain* to the delegation in question — callers are responsible for
that correspondence.

**[TODAY, Phase H7]**: `governance/non_delegable_authority.py`'s
`check_non_delegable_authority()` — the executable form of
constitutional law H11 ("non-delegable authority remains
non-delegable"). Every prior Heart phase (H3-H6) answers "is this
grant legitimate" — a question about *provenance*. This phase answers
a logically prior one: is this *category* of authority even the kind
of thing that can be delegated at all, regardless of how legitimate
its root, consent, and purpose are. A fixed, Heart-owned (not
org-configurable) registry maps action-type `fnmatch` patterns (same
mechanism `IntentContract.denied_targets` already uses) to one of two
severities: `NON_DELEGABLE` (can never appear in any delegated grant —
amending the constitution, issuing/revoking a root of authority,
overriding a Heart veto) or `HUMAN_RESERVED` (may be delegated to
*initiate*, but execution must always require a human in the loop,
unconditionally — a constitutional floor beneath the org-configurable
`require_approval_for`). Deliberately narrow: only meta-level
operations that would let a delegate undermine the Heart's own
guarantees are reserved; ordinary business-domain action types stay
governed by existing, org-mutable `Policy`. When both severities match
a requested action-type set, `NON_DELEGABLE` is always reported first
(property-verified).

**[TODAY, Phase H8]**: `governance/authority_lifetime.py`'s
`check_lifetime()` — the executable form of constitutional laws H13
("historical authorization does not imply current authorization") and
H14 ("material authority mutation requires reauthorization"). Every
object-level expiry check in this codebase (`RootAuthorityRecord.is_temporally_valid()`,
`ConsentProof.is_temporally_valid()`, `IntentContract.is_active()`,
`DelegationRecord.is_active()`) answers "is this object still valid
right now" — none of the four Phase H3-H6 *verdict* types
(`RootValidationResult`, `ConsentValidationResult`,
`PurposeBindingValidationResult`, `DelegationLegitimacyResult`) carry
an evaluation timestamp, so nothing stops a caller from computing one
once and treating it as permanently true. `check_lifetime()` answers
two independent staleness questions: `STALE_BY_AGE` (a verdict older
than its `LifetimeWindow.max_age_seconds`, checked second) and
`STALE_BY_MUTATION` (the underlying object's `canonical_digest` has
changed since evaluation, checked first — a materially mutated object
invalidates a verdict regardless of how recently it was computed).
Named default windows (`ROOT_AUTHORITY_LIFETIME_WINDOW` 24h,
`CONSENT_PROOF_LIFETIME_WINDOW` 24h, `PURPOSE_BINDING_LIFETIME_WINDOW`
1h, `DELEGATION_LEGITIMACY_LIFETIME_WINDOW` 5min) are suggestions, not
enforced — generalizing the existing, live "continuous
re-authorization" pattern (`MACHINE_AUTHORITY_V1.md` §2: a delegation
is checked fresh on every governed call) from one object type to all
four Heart verdict types. Deliberately never re-runs validation itself
— a caller receiving a stale result is responsible for re-invoking the
relevant H3-H6 function.

**[TODAY, Phase H9]**: `governance/revocation_kernel.py`'s
`RevocationEpoch`/`check_revocation_epoch()` — the thin, additive
primitive `docs/heart/HEART_CURRENT_STATE.md` §6 specifies for closing
the one confirmed real gap in this codebase's revocation story: five
independent revocation mechanisms exist (delegation cascading
revocation, delegation expiry, Authority Passport revocation, Authority
Passport drift detection, API key revocation), none sharing a counter.
A `RevocationEpoch` is a monotonically increasing counter per
`(organization_id, scope)`; `check_revocation_epoch()` compares an
issuance-time epoch against the current one, turning "has anything
been revoked since I was issued" into one integer comparison
(`REVOKED_SINCE_ISSUANCE`) instead of five separate live re-checks.
None of the five existing mechanisms are refactored — each keeps its
exact existing logic; this phase does not decide what bumps which
scope's epoch, deliberately deferred integration work. This phase also
closes a second, concrete gap the same audit section named: cascading
revocation (`revoke_branch()`) had no dedicated concurrency test or
latency measurement, unlike the grant side. `tests/test_concurrency.py`
now includes both, with one genuine, honest race-condition finding —
concurrent `revoke_branch()` calls on the same identity can each
report having revoked it (a check-then-act race on `revoked_ids`,
mirroring the already-documented autonomy-budget gap) even though the
database itself ends up correctly, terminally revoked — and one
confirmed protection (a `grant()` racing a `revoke_branch()` of its
parent is correctly rejected with `DelegationEscalationError`, not
silently allowed to create an orphaned active child).

**[TODAY, Phase H10]**: `governance/authority_conflict_resolver.py`'s
`resolve_authority_conflicts()` — the single point that decides, when
several of the independent Phase H3-H9 legitimacy checks are available
for the same authority decision and they disagree, which verdict wins
and in what deterministic order, rather than depending on which check
a caller happened to run or read first. Fixed precedence, most
severe/foundational first: `NON_DELEGABLE` (H7) → `REVOKED` (H9,
`REVOKED_SINCE_ISSUANCE` or `SCOPE_MISMATCH` both fail closed) →
`ROOT_NOT_LEGITIMATE` (H3) → `CONSENT_NOT_LEGITIMATE` (H4) →
`PURPOSE_NOT_BOUND` (H5) → `DELEGATION_NOT_LEGITIMATE` (H6) → `STALE`
(H8, checked last among blocking reasons — "cannot currently confirm"
is less informative than a confirmed illegitimacy) → `LEGITIMATE`.
Every one of the seven inputs is optional; `None` means "not
evaluated," never "failed," so a caller that only computed a subset of
the Heart's checks for a given request isn't penalized for what it
didn't compute. `human_reserved` is a separate, non-blocking boolean
signal (H7's `HUMAN_RESERVED` scope doesn't itself deny — it may be
delegated to *initiate* — but is still surfaced for a future
execution-time enforcement to act on). Deliberately never calls any of
the seven H3-H9 functions itself, keeping zero runtime dependency on
any of them (all seven imports are `TYPE_CHECKING`-only).

**[TODAY, Phase H11]**: `governance/heart_veto.py`'s
`apply_heart_veto()`/`enforce_heart_veto()` — the executable form of
constitutional law H12 ("Heart veto cannot be overridden"), and the
first Heart module whose entire purpose is to have real teeth rather
than only report a status. `apply_heart_veto()` derives a
`HeartVetoRecord` from an already-computed `ConflictResolutionResult`
(H10) — any `status` other than `LEGITIMATE` vetoes. `enforce_heart_veto()`
is the sharp edge: it raises `HeartVetoError` for a `VETOED` record and
is a no-op otherwise, with **no parameter of any kind** that could
suppress, downgrade, or bypass a veto — verified structurally (its
signature has exactly one parameter), not merely claimed in a
docstring. A `VETOED` record can only become `NOT_VETOED` by re-running
`apply_heart_veto()` against a genuinely different, freshly-legitimate
`ConflictResolutionResult`. `human_reserved` (H7) passes through
unchanged regardless of veto outcome — the binary allow/deny decision
and the human-reserved signal are orthogonal.

**[TODAY, Phase H12]**: `governance/legitimacy_envelope.py`'s
`LegitimacyEnvelope`/`build_legitimacy_envelope()` — the single,
portable, digestible artifact that packages the Heart's final verdict
(H11's `HeartVetoRecord`) about one identity's authority, at one point
in time, into an exportable object with an identity (`envelope_id`),
context (`organization_id`/`subject_identity_id`), a timestamp
(`issued_at`), and a `canonical_digest` — the same shape every other
Heart record type (H1, H3, H4, H5) already has. Does not re-derive the
veto or embed the seven individual upstream H3-H9 results; wraps
exactly the already-final `HeartVetoRecord`, since that record already
*is* H10's precedence-resolved answer. `explain()` mirrors the
established deterministic-explanation pattern
(`governance/constitution.py`'s `explain_constitution()`,
`db/delegation_repository.py`'s `explain_authority()`) — a plain,
structured dict, never an LLM call.

**[TODAY, Phase H13]**: `governance/sovereignty_kernel.py`'s
`evaluate()` — the first, and so far only, place in this codebase that
actually calls the H3-H12 Heart functions together, for one real
request, and returns one `LegitimacyEnvelope`. Given whichever of
root/consent/purpose/delegation/requested-action-types/revocation-
epoch inputs a caller supplies for one `(organization_id,
subject_identity_id)` decision, it runs the applicable H3-H9 checks
(skipping any whose prerequisites weren't supplied — partial input is
a first-class case, not degraded behavior, mirroring H10's own
"`None` means not evaluated, never failed" design), composes their
verdicts via H10, applies H11's veto, and wraps the result in H12's
envelope. This is the one Heart module allowed — required — to import
and call H3-H12's real functions directly, since every phase before it
deliberately avoided doing so specifically so this wiring could exist
without circularity. Still deliberately does not resolve anything from
a database — accepts already-constructed domain objects (and, for
root-chain walking, an abstract `RootResolver` callable) rather than
looking anything up, exactly like every prior phase's own "not built
here."

**[TODAY, Phase H14]**: `docs/heart/HEART_INVARIANTS.md` — an honest
ledger of every invariant claimed by Phases H1-H13, each paired with
the specific test that verifies it, and every claim without a test
marked `UNVERIFIED` rather than silently omitted. Explicitly **not**
formal verification in the TLA+/Coq/model-checker sense — every
property is checked against Hypothesis-generated inputs across a large
sampled space, not proven for all possible inputs. `tests/test_heart_formal_properties.py`
adds cross-cutting property tests spanning the full H3-H13 chain that
no single phase's own tests could exercise: `evaluate()`'s (H13)
result is always consistent with manually composing
`resolve_authority_conflicts()` (H10) + `apply_heart_veto()` (H11)
from the same underlying results; denial is monotonic (adding any
single blocking condition to an otherwise-legitimate chain always
flips the result, never masked by legitimate inputs present
alongside it); every canonical-digest function across the Heart
(root, consent, purpose binding, legitimacy envelope, constitution)
is sensitive to every one of its own fields, individually verified;
and `is_legitimate` is a pure function of the supplied verdicts,
independent of the non-deterministic identity fields every issued
record carries.

**Not built yet**: no DB persistence layer exists yet for
`RootAuthorityRecord`, `ConsentProof`, `PurposeBinding`, or
`LegitimacyEnvelope` — this Heart, even now end-to-end wireable for a
single call, still has no live caller anywhere in
`WhitePactRuntimeGateway.evaluate()` or any other production decision
path, and no code resolves real persisted state into the domain
objects `evaluate()` accepts. No execution-time enforcement turns a
`HUMAN_RESERVED` finding (H7) into an actual mandatory-approval gate
yet, no org-configurable extension mechanism exists for adding
organization-specific `HUMAN_RESERVED` action types on top of the
fixed built-in set, and none of the five existing revocation
mechanisms actually call `bump_epoch()` yet. The remaining Heart
phases (H15-H17: the adversarial gauntlet, performance, and enterprise
hardening) are further verification and hardening work on what now
exists, not new authority primitives.

## 3. Core entities

### 3.1 Agent **[TODAY — Phase 8]**

An autonomous or semi-autonomous software actor requesting an action.

```
AgentContext:
  agent_id: str                 # stable identifier for this agent instance
  organization_id: str          # tenant boundary — see RBAC below
  identity: IdentityContext     # who/what is actually behind this agent
  framework: str | None         # e.g. "langchain", "langgraph", "adk", "mcp-client"
  provider: str | None          # e.g. "openai", "anthropic", "azure-openai"
  model: str | None             # e.g. "gpt-4o", a customer's Azure deployment name
  trust_state: TrustCheckResult | None  # cached Trust Index result for this agent/tool, if known
  metadata: dict[str, Any]      # framework-specific extras, never secrets
```

**[TODAY]**: `AgentContext` is a real, tested dataclass
(`src/responsibleai/governance/models.py`) — this is verified current
source, not the target shape above restated as a claim. It reuses the
existing `TrustCheckResult` (`src/responsibleai/integrations/client.py`)
for `trust_state` rather than inventing a new `TrustSummary` type, since
`TrustCheckResult` already is exactly "a lookup of a model or tool's
public trust score" and nothing about `AgentContext` needed anything
more. `governance/trust_integration.py`'s `enrich_agent_trust_state()`
now populates it from a live Trust Index lookup when a call names a
`provider`/`model`, and `WhitePactRuntimeGateway` consults it (see
Section 2 above) — no longer caller-constructed-only.

### 3.2 Identity **[TODAY, partially — Phase 8]**

Who or what is making the request. Must support humans, service
accounts, agents, API keys, OAuth/OIDC identities, and future workload
identities.

**[TODAY]**: `OrgContext` (`src/responsibleai/rbac/models.py`) already
carries `key_id`, `role` (`OWNER`/`ADMIN`/`ANALYST`/`VIEWER`), `org_id`,
and `plan` — this is a real, working, tested identity model, but it's
scoped to *human/API-key* access to the REST API and dashboard, not to
an *agent* acting on a human's or organization's behalf. OIDC/SSO
support exists (`src/responsibleai/auth/` — see `sso` extra in
`pyproject.toml`). MFA (TOTP, RFC 6238) is implemented and tested.

`IdentityContext` (`src/responsibleai/governance/models.py`) now
generalizes `OrgContext` as described — `IdentityContext.from_org_context()`
maps a real `OrgContext` (from a static API key or an OIDC JWT, see
`mcp/server.py`'s `_authenticate`) into the broader vocabulary, without
modifying `OrgContext` itself. A non-human principal (service account,
external attested agent) now has a second, real path in —
`IdentityContext.from_principal_claim()`, kind `"vc"` — see §3.2.1.
What remains genuinely unimplemented: a SPIFFE/SPIRE-style workload
identity has no real issuer or verification path anywhere in this
codebase — `IdentityContext.kind` accepts the string `"workload"`, but
nothing produces or validates one today, so treat that specific kind as
aspirational, not working.

#### 3.2.1 Verified Principal **[TODAY, first version — Authority Everywhere Phase 3]**

`docs/architecture/AUTHORITY_EVERYWHERE.md`'s lifecycle table named this
gap directly: §3.2 above verifies *human* identities via an enterprise
IdP, but has no path for a *non-human* principal — a service account,
or another organization's attested agent — to present its own
cryptographic credential and be recognized as the actor behind a
governed action.

`auth/verifiable_credential.py`'s `VerifiableCredentialProvider` closes
this for one concrete, real shape: a **JWT-VC bearer presentation**,
verified against an admin-configured trusted-issuer allowlist
(`Settings.vc_trusted_issuers`) using the exact same JWKS-fetch,
`kid`-resolution, private-key-rejection, and weak-RSA-key-rejection
machinery `auth/oidc.py`'s `OIDCProvider` already established — a
credential issuer is just another entity publishing a JWKS at
`<issuer>/.well-known/jwks.json`. `mcp/server.py`'s `_authenticate`
tries this path (`_resolve_vc_context`) after the existing OIDC path,
routed by an unverified peek for a `vc` claim (`looks_like_vc_jwt`) that
is never trusted for anything beyond which verifier to invoke — full
verification always happens afterward. A successful verification is
logged, append-only, to `verified_principals`
(`db/principal_repository.py`, migration `0027`) via a governance-layer
`PrincipalClaim` (`governance/principal.py`) that deliberately discards
the raw credential payload — field names only, same "never raw values"
discipline `EvidenceRecord.argument_keys` and `OutcomeRecord.result_summary`
already apply.

**Deliberately not built**: DID resolution (`did:key`, `did:web`),
JSON-LD proof formats (`Ed25519Signature2020` etc.), the full
OpenID4VP authorization-request/response presentation-exchange
protocol, or revocation-list checking against a presented credential's
issuer — none of the libraries the first three would need are
dependencies of this codebase today, and revocation-status checking is
a real, separate protocol this phase doesn't attempt. A credential
presented as a JSON-LD proof or resolved via a DID document is
rejected outright, not silently accepted with weaker checks. Whether a
verified principal should receive a *different* authority ceiling than
an API-key identity (§3.3 below) is also unanswered — `PrincipalClaim`
resolves to an `identity_id` string that plugs into the existing
delegation/ceiling chain unchanged, with no verification-method-aware
branching yet.

### 3.3 Authority **[TODAY, minimal — Phase 8]**

What authority has been delegated to the agent. This is deliberately
**not** the same thing as a raw RBAC role.

- **RBAC/IAM question**: does this API key have the `ADMIN` role, which
  technically permits calling `POST /api/trust-index/certify`?
- **Authority question**: even though this agent's identity *can*
  technically reach that endpoint, has this organization actually
  delegated "certify trust passports" authority to *this specific
  agent*, in *this context* (time of day, transaction value, data
  sensitivity, environment)?

**[TODAY]**: `AuthorityContext` exists
(`src/responsibleai/governance/models.py`) as a minimal, real
implementation: `granted_action_types` (a set the caller supplies —
nothing derives it from RBAC roles automatically yet) and
`require_approval_for`, both enforced by `WhitePactRuntimeGateway`. The
"in *this context*" part of the authority question above — time of day,
transaction value, data sensitivity — is represented only as an open
`constraints: dict[str, Any]` bag; nothing in the gateway actually reads
or enforces those constraints yet. There is still no delegation
*workflow* (an org granting authority to a specific agent through some
UI or API) — callers construct `AuthorityContext` directly in code
today. RBAC roles remain the only authority signal enforced
automatically anywhere in the codebase.

#### 3.3.1 Authority Passport **[TODAY, first version — Authority Everywhere Phase 5]**

`docs/architecture/AUTHORITY_EVERYWHERE.md`'s lifecycle table (row 3)
named this gap: `OrgAuthorityCeiling` above is a real subset of what a
full "portable, provable" credential needs, but it's an in-process
object, not something a principal can hold, export, or have
independently re-verified later. The Phase 2 naming-collision
resolution reserved **"Authority Passport"** for exactly this concept
(distinct from the already-shipped `trust/passport.py`'s `AIPassport`
— a *model's* Trust Index certification, unrelated to principal
authority).

`governance/authority_passport.py`'s `AuthorityPassport` is a portable
snapshot of what a principal was authorized to do at issuance,
exported from either the org's current `OrgAuthorityCeiling`
(`build_authority_passport_from_ceiling()`) or an active
`DelegationRecord` (`build_authority_passport_from_delegation()`).
Issued via `POST /api/governance/authority-passports` (ADMIN+, since
exporting a portable credential exports real usable authority),
revocable independent of its source (`POST .../{id}/revoke`), and
persisted append-only (`db/authority_passport_repository.py`,
migration `0029`) — "latest issued, still-active passport wins" per
principal, the same resolution `DelegationRepository`/
`IntentContractRepository` already use.

**"Independently verifiable" without cryptographic signing**:
`GET /api/governance/authority-passports/{id}` always re-fetches the
live source (the org's current ceiling, or the specific delegation the
passport was exported from) and compares — `verify_passport()` returns
`VALID`, `DRIFTED` (the source has since changed), `SOURCE_NOT_FOUND`
(the source is gone/revoked), `REVOKED`, or `EXPIRED`. This never
trusts the passport's own stored fields alone — the same "integrity by
linkage to an already-real source" pattern `governance/attestation.py`
already established against `EvidenceRecord`'s hash chain, generalized
here to a ceiling/delegation row. **Deliberately not cryptographically
signed**, for the identical reason `attestation.py`/`execution.py`
already state: a live signing key in the running server process is a
real secret-management burden with no infrastructure built for it, and
a forged passport would need the same DB write access that could also
rewrite its own source row.

**Not built here**: wiring a *presented* passport into
`WhitePactRuntimeGateway.evaluate()`'s live per-call authority
resolution as an alternative to the ceiling/delegation lookup
`mcp/governance_integration.py` already performs fresh on every call —
deciding how much to trust an externally-presented credential versus
re-deriving authority is real, separate integration work with its own
threat model. Today `AuthorityPassport` is the portable, exportable,
independently verifiable *representation* of a principal's authority,
not yet a new input to the hot governance-decision path.

#### 3.3.2 Delegation Graph as a first-class object **[TODAY, first version — Authority Everywhere Phase 6]**

`docs/architecture/AUTHORITY_EVERYWHERE.md`'s lifecycle table (row 4)
already credited `governance/delegation.py` + `db/delegation_repository.py`
with being "a working delegation graph today" — `validate_attenuation()`
enforces `CHILD AUTHORITY ⊆ PARENT AUTHORITY` at grant time, and
`get_authority_chain()`/`revoke_branch()` already walk the structure
correctly. What was missing: every existing query was *pairwise* (one
identity's own backward chain to its root, or a mutation that walked
forward only to revoke) — there was no way to ask "what does the whole
graph look like right now" independent of any single decision.

`governance/delegation_graph.py`'s `DelegationGraph`/`DelegationGraphNode`
close that gap: `DelegationRepository.get_org_graph()` builds the
org-wide forest (every root grant and everything transitively
delegated from it), and `get_descendants()` is the public, read-only,
forward-direction counterpart to `revoke_branch()`'s internal BFS.
Both are built from each identity's *current* state
(`get_latest_delegation()`), not a raw historical-row walk — an
identity re-delegated under a new parent shows up under that parent
only, not duplicated or left stale under the old one. New endpoints
`GET /api/governance/delegations/{identity_id}/descendants` and
`GET /api/governance/delegations/graph`.

**Deliberately unchanged**: no new invariant, no new migration, no
change to `grant()`/`revoke_branch()`/`validate_attenuation()`'s
existing behavior — this phase is a read-only export of state that
was always reconstructable from the existing `governance_delegations`
table, exactly matching the lifecycle table's own framing ("package
it," not "rebuild it").

### 3.4 Action **[TODAY — Phase 8]**

A proposed operation an agent wants to execute. Conceptually:

```
ActionRequest:
  action_id: str
  agent: AgentContext
  action_type: str        # "mcp_tool_call" | "api_call" | "transaction" |
                           # "db_operation" | "message_send" | "deployment" |
                           # "approval" | "data_export" | ...
  target: str              # e.g. the MCP tool name, or the API route
  arguments: dict[str, Any]  # sanitized before it ever reaches Evidence storage
  proposed_at: datetime
```

**[TODAY]**: `ActionRequest` is a real dataclass
(`src/responsibleai/governance/models.py`) matching the shape above
exactly, and a genuinely used one: `mcp/governance_integration.py`
constructs one from every hosted-MCP tool call (when
`Settings.mcp_governance_enabled` is on — see Section 2) and routes it
through `WhitePactRuntimeGateway` before `dispatch_tool()` in
`mcp/tools.py` ever runs — and, since the executor-abstraction work,
"before ... ever runs" is now structurally enforced, not just true by
convention: an ALLOW/ALLOW_WITH_REDACTION decision produces an
`ExecutionAuthorization` (`governance/execution.py`,
`authorize_execution()`), and `InternalToolExecutor.execute()` — the
only code path left that calls `dispatch_tool()` on the governed
route — validates that authorization (matching digest, matching org,
unexpired, unconsumed) before invoking it. `arguments` is sanitized
before it reaches Evidence storage in practice, not just in the field
comment above — `EvidenceRecord` stores only `argument_keys`, never
values (Section 3.7).

**[TODAY, extended — "Execution Permit v2" / Authority Everywhere Phase
9]**: for `UpstreamMCPExecutor` specifically, `ExecutionAuthorization`
now also carries an optional `target_fingerprint` — a hash of the
resolved upstream server's URL, enabled state, and whether a credential
is attached, computed once when the gateway makes its decision
(`mcp/upstream_dispatch.py`) and recomputed immediately before dispatch
(`governance/upstream_executor.py`). A mismatch raises
`AuthorizationTargetDriftError` and the call is refused — this closes a
real gap the original binding left open: `action_digest` covers the
action's own shape (agent, action_type, the target *string*
`server_id::tool_name`, arguments) but never captured what that target
string currently *resolves to*, so a server's registration changing
between decision and execution could not previously be detected by the
permit itself. `InternalToolExecutor` is unaffected — its target
(`action_type`) has no external resolution step, so it never sets a
fingerprint.

**[TODAY, first version — "JIT Credential Broker" / Authority
Everywhere Phase 10]** (not to be confused with this section's own
"Phase 10" label below, from the original SPEC numbering):
`governance/jit_credential.py` — `UpstreamMCPExecutor` no longer reads
`UpstreamServer.auth_token` directly. It asks `issue_jit_credential()`
for a `JITCredential` bound to the exact, already-validated
`ExecutionAuthorization`, whose own expiry is
`min(authorization.expires_at, now + ttl_seconds)` — a credential can
never outlive the permit that produced it, only expire sooner
(defaulting to 15 seconds). `consume_jit_credential()` is the one place
the token is ever read for actual use, single-use, raising
`CredentialAlreadyConsumedError`/`CredentialExpiredError` on reuse or
staleness. Every issuance and consumption is recorded to
`credential_issuances` (migration `0025`,
`db/credential_issuance_repository.py`) — metadata only (who, which
server, when, whether a credential existed at all), never the secret
value itself.

Stated honestly, as this module's own docstring does: this does not
perform OAuth token exchange or ask an upstream server to mint a
narrower-scoped credential on demand — most third-party MCP servers
have no such protocol. What it narrows is *access* to the existing
standing credential: "held indefinitely by whatever code path can
reach the DB row" becomes "issued once, per permit, time-boxed, and
logged." If a future upstream server supports real token exchange,
this is the module that would grow that capability without changing
any caller.

#### 3.4.1 Intent Contract **[TODAY, first version — Authority Everywhere Phase 4]**

`docs/architecture/AUTHORITY_EVERYWHERE.md`'s lifecycle table (row 2)
named this gap: `ActionRequest` states what's being done, not what was
*promised* up front — there was no way to declare a goal and its bounds
before an agent starts taking actions, so nothing could check "does
this action still match what this task was supposed to be," only "is
this action individually allowed."

`governance/intent.py`'s `IntentContract` closes this for one task at a
time: an agent (or its human operator, via
`POST /api/governance/intent-contracts`) declares a `goal` string plus
optional bounds — `max_value_usd`, `allowed_targets`/`denied_targets`,
`allowed_action_types` — before starting a task. Every subsequent
action from that `agent_id` is checked against the most recently
declared, still-active contract
(`IntentContractRepository.get_active_for_agent()`) via
`WhitePactRuntimeGateway.evaluate()`'s new optional `intent` parameter,
checked immediately after the existing authority-attenuation check and
before `authority.permits()` — a violation is a `DENY` with reason code
`INTENT_VIOLATED`, before the org's own delegated-authority checks even
run.

**Deliberately distinct from `AuthorityContext.constraint_violation()`**
(§3.3): that checks what the *organization* delegated to the agent's
authority grant, set once by an admin and rarely revisited; this checks
what the *agent itself* promised for the current task. An agent can
hold broad org-granted authority and still choose (or be required) to
declare a narrower intent per task — the two checks are independent
gates, not a replacement for each other.

**Deliberately not built**: goal *understanding* — `goal` is a free-text
string, stored and surfaced for audit/attestation review, never
machine-parsed to check whether an action's target/arguments are
semantically related to it. That would require interpreting free-text
intent against arbitrary tool arguments, real, separate, model-assisted
work this phase doesn't attempt. Also not built: any REST/MCP
endpoint on the dashboard's human-login surface beyond the two REST
endpoints above — declaring intent for a non-MCP action (e.g. a direct
REST-driven governed operation) isn't wired to check it, since no such
call site fetches an `IntentContract` today.

### 3.5 Policy **[TODAY, first version — Phase 10]**

Machine-enforceable organizational rules governing actions. The "small,
strongly typed internal model first — not an LLM, not necessarily
OPA/Rego on day one" this section originally called for (see Section 6
below on deterministic vs. probabilistic controls) now exists:
`Policy`/`PolicyRule` in `src/responsibleai/governance/policy.py`. A
`Policy` is an ordered list of `PolicyRule`s, each matching on risk
tier / action type / target and producing an `ALLOW`/`DENY`/
`REQUIRE_APPROVAL` effect; evaluation is first-match-wins, deliberately
with no priority/specificity scoring to explain. This is genuinely the
first, smallest version — no OPA/Rego, no expression language, no rule
persistence (an organization's `Policy` is constructed in code and
handed to `WhitePactRuntimeGateway.evaluate()` per call; there is no
`policies` database table, no API to author or store one, and no UI).
`rai_policy_check` (a separate, existing MCP tool that evaluates text
against blocklists/disclaimers) is unrelated and unchanged by this —
still a real, narrow, working feature, still not this engine.

### 3.6 Decision **[TODAY — Phase 8]**

One of exactly five outcomes:

| Decision | Meaning | Status |
|---|---|---|
| `ALLOW` | The action proceeds unmodified. | **[TODAY]** — produced by the gateway when nothing else fires. |
| `ALLOW_WITH_REDACTION` | The action proceeds, but the payload is modified first (e.g. PII stripped) — see `GuardrailsEngine`'s existing redaction logic, which this reuses. | **[TODAY]** — produced when `GuardrailsEngine` finds PII-only findings. |
| `REQUIRE_APPROVAL` | The action is held pending a human (or delegated-authority) approval — see Section 3.7. | **[TODAY]** — produced when the caller-supplied `AuthorityContext.require_approval_for` names the action type (or a matching `Policy` rule says so, Section 3.5); `db/approval_repository.py`'s `ApprovalRepository` now persists it as a resolvable request (`PENDING` → `APPROVED`/`DENIED`, double-resolution rejected), queryable and resolvable via `GET /api/governance/approvals` and `POST /api/governance/approvals/{id}/resolve`. Genuinely still missing: any notification beyond an optional webhook fire, and no automatic re-evaluation or execution of the action once approved — resolving records a human decision, acting on it is the caller's job. |
| `DENY` | The action is blocked outright. | **[TODAY]** — produced on a missing authority grant, or a toxicity/custom-pattern guardrails match. |
| `QUARANTINE` | The action, the agent, or both are held for review beyond a single decision — e.g. an agent exhibiting a pattern of policy violations gets its authority suspended pending investigation, distinct from a single denied action. | **[TODAY]** — `governance/quarantine.py`'s `recent_violation_count()` queries persisted evidence for a caller's recent `DENY` decisions; at or above `QUARANTINE_VIOLATION_THRESHOLD` (5, within a 60-minute window), `WhitePactRuntimeGateway.evaluate()` returns `QUARANTINE` before even checking authority. Tested end-to-end, including via the live MCP dispatch path. |

`GovernanceDecision` is a real five-way `StrEnum`
(`src/responsibleai/governance/models.py`), replacing what used to be
true of every decision-shaped output in this codebase — binary
(`GuardrailsEngine.scan()` still returns `is_blocked: bool` at its own
layer; `GovernanceDecision` is a layer above it, not a replacement for
it).

### 3.7 Evidence **[TODAY, first version — Phase 12]**

Immutable, tamper-evident structured evidence for every decision.
Conceptually (this is the *target* shape; see below for what's actually
implemented against it):

```
EvidenceRecord:
  evidence_id: str
  organization_id: str
  request_id: str
  agent_id: str
  human_identity: str | None       # the ultimate human/service accountable
  model: str | None
  provider: str | None
  mcp_server: str | None
  tool_or_action: str
  sanitized_arguments_metadata: dict[str, Any]  # never raw secrets
  authority_used: str
  policies_evaluated: list[str]
  trust_signals: dict[str, Any]
  deterministic_checks: dict[str, Any]
  probabilistic_checks: dict[str, Any]
  risk_classification: str
  decision: GovernanceDecision
  reason_codes: list[str]
  approval: ApprovalRecord | None
  timestamps: dict[str, datetime]
  execution_result_metadata: dict[str, Any] | None
  prev_hash: str | None
  hash: str
```

**[TODAY]**: `governance/evidence.py`'s `EvidenceRecord` +
`db/evidence_repository.py`'s `EvidenceRepository` implement a real,
persisted, hash-chained subset of the shape above —
`tests/test_governance_persistence.py` proves tamper detection
(mutating a stored field, or breaking the `prev_hash` link between two
entries, both make `verify_chain()` return `False`) and per-org chain
independence. This generalizes the AI Incident Database's proven
hash-chaining pattern (`db/public_incident_repository.py`,
`GET /api/incident-db/verify`) into per-org evidence rather than
inventing tamper-evidence from scratch, exactly as originally planned
— except chained **per organization**, not globally, since an org's own
evidence trail should be independently verifiable without needing any
other org's records. Exposed via `GET /api/governance/evidence` and
`GET /api/governance/evidence/verify`.

Field-by-field honesty against the target shape above —
`governance/evidence.py`'s module docstring has the full accounting,
summarized: `sanitized_arguments_metadata` is implemented as
`argument_keys: list[str]` (field *names* only, deliberately never
values); `trust_signals` as its own structured `EvidenceRecord` field
is still not populated — `AgentContext.trust_state` is now computed
live (`governance/trust_integration.py`) and consulted by the gateway
*before* the decision, but the evidence record itself only captures
`provider`/`model`, not the trust score that fed the decision; a
low-trust downgrade's reason code (`trust_state:low_score:N`) is the
current way to see it in `reason_codes`. `deterministic_checks` /
`probabilistic_checks` are not broken out as separate structured
fields, `reason_codes` carries what a `GuardrailsResult`/`Policy` match
found instead; `execution_result_metadata` is not populated as a field
*on* `EvidenceRecord` itself, but the gap it names — "no visibility into
whether an allowed action was actually executed" — is now closed by a
separate, linked record; see 3.7.1 below. `human_identity` is populated
from `AgentContext.identity.identity_id`, since no concept of "the human
behind the agent, distinct from the API key/OIDC identity that
authorized it" exists yet.

#### 3.7.1 Outcome, Reconciliation, and Attestation **[TODAY, first version — Authority Everywhere Phases 12-14]**

Closes the gap 3.7 names honestly above: `EvidenceRecord` records the
*decision*, never whether the executor's own attempt to carry it out
actually succeeded.

**Outcome Observation (Phase 12)** — `src/responsibleai/governance/outcome.py`'s
`OutcomeRecord` (`SUCCEEDED` / `FAILED` / `ERRORED`, plus an optional,
deliberately minimal `result_summary` — never the raw result payload,
same "field names/shapes, never values" discipline `argument_keys`
already applies) is linked to its authorizing `EvidenceRecord` via
`evidence_id`. Auto-recorded, fail-open (the action already executed by
the time this write happens — there is nothing left to block on a
failure), at both governed-execution call sites:
`mcp/governance_integration.py`'s `apply_governance()` and
`resume_approval()`, and `mcp/upstream_dispatch.py`'s
`apply_upstream_governance()`. Persisted via `OutcomeRepository`
(`governance_outcomes` table, migration `0026`). A caller whose
execution happens outside a governed dispatch call entirely can report
one manually via `POST /api/governance/evidence/{evidence_id}/outcome`.

**Reconciliation (Phase 13)** — `governance/reconciliation.py`'s
`reconcile_outcome()` is honestly narrower than it might sound: the
strongest invariant ("the action that executed was byte-identical to
what governance authorized") is already structurally enforced
*synchronously, before* execution by `ExecutionAuthorization.matches_action()`
and, for upstream calls, `check_target_fingerprint()` — an
`OutcomeRecord` can only exist for an action that already passed those.
What this adds: `RECONCILED` (an outcome exists and its `action_id`
agrees with the evidence's), `MISSING_OUTCOME` (a decision that
authorized execution never got an outcome reported at all — a real,
useful anomaly signal), `ACTION_MISMATCH` (a defensive check nothing
else catches), and `NOT_APPLICABLE` (DENY/QUARANTINE/REQUIRE_APPROVAL —
never expected to have an outcome).

**Attestation (Phase 14)** — `governance/attestation.py`'s
`AttestationRecord` packages one evidence entry's decision, outcome
status, and reconciliation status into one exportable statement.
**Deliberately not cryptographically signed** — stated in the module's
own docstring, generalizing the identical reasoning
`ExecutionAuthorization` already gives (3.4): an automated per-action
signature would need a live signing key sitting in the running server
process, a real secret-management/rotation burden this project has no
infrastructure for, and a forged record would need the same DB write
access that could also rewrite the evidence hash chain itself — a
signature only helps once chain checkpoints are also committed
somewhere external, which isn't built here. Integrity today is by
linkage to `EvidenceRecord.hash` (verifiable via the existing
`GET /api/governance/evidence/verify` chain check), stated explicitly
in every `to_dict()` output's `integrity_note` field rather than left
implicit. Exposed via `GET /api/governance/evidence/{evidence_id}/attestation`.

---

## 4. The WhitePact Governance Engine — mapping today's 27 MCP tools

**[TODAY, verified against `src/responsibleai/mcp/tools.py`]**: exactly
27 tools are registered via `TOOL_DEFS`, dispatched through
`dispatch_tool()`. Under the target architecture, these become the
**deep governance intelligence** the Decision pipeline calls into —
they do not disappear, get renamed at the tool level, or lose their
existing MCP-client-facing contract. They are reorganized conceptually
into the risk-tiered execution model (Phase 9):

| Tier | Risk | Existing tools (verified names) |
|---|---|---|
| Identity/health (near-zero cost, safe to run on every request) | MINIMAL | `rai_health`, `rai_audit_summary`, `rai_org_status` |
| Deterministic scan (fast, no LLM) | LOW | `rai_scan` (PII/harm detection), `rai_pii_report`, `rai_policy_check`, `rai_stream_scan` |
| Trust/cost lookups (cached-friendly) | LOW | `rai_trust_score`, `rai_check_trust`, `rai_cost_estimate`, `rai_budget_check`, `rai_model_route` |
| Compliance classification | MEDIUM | `rai_compliance`, `rai_eu_ai_act_classify`, `rai_iso42001_gap` |
| Deeper/probabilistic evaluation | HIGH | `rai_hallucination`, `rai_bias_evaluate`, `rai_drift_check`, `rai_redteam_payloads`, `rai_redteam_analyze`, `rai_compare_models`, `rai_benchmark`, `rai_benchmark_prompts` |
| Record-keeping (writes — never mislabel as read-only) | MEDIUM | `rai_incident_log`, `rai_passport_generate`, `rai_executive_summary`, `rai_webhook_status` |

**[TODAY]**: this table is now executable, not just proposed —
`governance/risk.py`'s `TOOL_RISK_TIERS` and `classify_action_risk()`
implement it exactly (`tests/test_governance_risk.py` asserts the table
stays in sync with the live `TOOL_DEFS` list, so it can't silently drift
as tools are added). What "risk-tiered execution" doesn't yet mean:
there's no automatic behavioral difference *between* the four tiers
baked into the gateway itself — a `HIGH`-tier action isn't automatically
held for approval or subjected to extra scrutiny by `risk.py` alone. The
tier is a real, computed classification made available to a `Policy`
(Section 3.5) to act on; whether it actually changes a decision depends
entirely on whether an organization's `Policy` has a rule that reads it.
No default policy ships that does this automatically — that would be an
opinionated governance stance imposed on every deployment, not a neutral
capability.

### 4.1 MCP Trust/Supply-Chain Scanner **[TODAY, first version — Phase 13]**

Before this section's work: no code anywhere evaluated the
trustworthiness of a *third-party* MCP server before an organization
grants an agent authority to use it — a real gap distinct from
everything else in this document, which governs actions against
*this* server's own tools, not decides whether to trust *someone
else's*.

**[TODAY]**: `src/responsibleai/supplychain/` — `SupplyChainScanner`
takes a caller-supplied `McpServerManifest` (server name, publisher,
tool name/description list) and returns a `SupplyChainReport`: a list
of `Finding`s, each classified `VERIFIED_FACT` / `INFERRED_SIGNAL` /
`UNKNOWN` — never collapsed into a single opaque score, per this
section's one hard requirement. Three checks, each honestly scoped to
what it can actually claim:

1. **Confusable-character check** (`VERIFIED_FACT` either way) — a
   bounded Cyrillic/Greek lookalike-character lookup table against
   server and tool names (the classic typosquat trick). Presence or
   absence is a verifiable fact about the string itself. Deliberately
   *not* a full Unicode TR39 confusables implementation — that's real,
   separate, larger work; this is a stated, bounded subset.
2. **Tool description content scan** (always `INFERRED_SIGNAL`) —
   reuses the existing, tested `GuardrailsEngine` against every tool
   description, looking for injected-instruction/PII/toxicity patterns.
   A match is a signal worth a human look; a clean scan is not proof of
   safety, only that this heuristic found nothing.
3. **Known public incident cross-reference** (`VERIFIED_FACT` if found,
   `UNKNOWN` if not — optional, needs a `PublicIncidentRepository`) —
   reuses the existing AI Incident Database's `check()` method. Filed
   incidents are a real fact; their absence is explicitly *not* treated
   as evidence of safety, since a new or low-visibility server may
   simply not have been scrutinized yet.

This scanner never connects to a remote MCP server itself — it
analyzes whatever manifest a caller already has (from a real
`tools/list` response, a registry listing, etc.). Actually speaking
the MCP protocol to an arbitrary third-party server is real, separate
transport-layer work with its own security questions (SSRF risk in
fetching an arbitrary server-supplied URL, for one), not implied by
this scanner's existence. Exposed via `POST
/api/governance/supplychain/scan` (not org-scoped: the checks are
either pure or query the public, org-agnostic incident database, so
there's no per-org data to isolate).

### 4.2 Tool Trust Network **[TODAY, first version — Authority Everywhere Phase 8]**

Section 4.1's scanner produces a report a human has to read, and
`governance/upstream.py`'s registry ("registration is the approval
step") never changes once an admin approves a server. Neither answers
"should calls to this specific server keep being allowed *right now*"
— a question that can change after registration without the
registration itself changing (a later scan finds a typosquat pattern,
an incident gets filed, an admin revokes trust).

**[TODAY]**: `src/responsibleai/governance/tool_trust.py` —
`compute_trust_score()` turns one `SupplyChainReport` into a
deterministic `ToolTrustScore` (0-100, one of `TRUSTED` / `PROVISIONAL`
/ `UNTRUSTED` / `BLOCKED`): a `70`-baseline, minus a large penalty for a
`VERIFIED_FACT` confusable-character hit, a capped penalty per flagged
tool description, and a large penalty per known incident. A server that
has never been scanned is `PROVISIONAL`, capped below `TRUSTED` — trust
cannot accrue from silence. `apply_admin_override()` is the one path
that can force `BLOCKED` (immediately) or `TRUSTED` (ahead of a scan),
always attributed to an admin id and a non-empty reason. Persisted via
`ToolTrustRepository` (`tool_trust_scores` table, migration `0024`).

**Wired into the request path**: `mcp/upstream_dispatch.py`'s
`apply_upstream_governance()` checks the server's current tier
immediately after the registration check and before the gateway is even
consulted — a `BLOCKED` tier is denied with the (previously reserved,
now used) `ReasonCode.UNTRUSTED_MCP_SERVER`, the same shape
`UNAPPROVED_MCP_SERVER` already used. `TRUSTED`/`PROVISIONAL`/
`UNTRUSTED` all still pass through to the existing risk-based decision
path unchanged in this first version — modulating risk tier by trust
tier is a natural next increment, not built here, per this project's
own discipline against building ahead of a stated requirement.

REST surface (all under `/api/governance/upstream/servers/{server_id}/trust`):
`GET` (ANALYST+, returns the current score or an unscanned default),
`POST .../scan` (ADMIN, runs the scanner against the server's
currently-discoverable tool list via the existing
`discover_upstream_tools()` and persists the result), `POST
.../override` (ADMIN, records an explicit tier override).

### 4.3 Causal Influence Firewall **[TODAY, first version — Authority Everywhere Phase 7]**

Before this section's work: `governance/memory_firewall.py` scanned
exactly one kind of content — text about to be written to persistent
memory — for prompt-injection patterns. A tool-call argument built from
a prior tool's output, a sub-agent's returned result, or a scraped web
page carries exactly the same "replayed as trusted context" risk memory
does, and none of it was ever scanned unless it happened to also be a
memory write.

**[TODAY]**: `src/responsibleai/governance/causal_influence.py` is now
the canonical home of the injection-pattern table (moved from
`memory_firewall.py`, which delegates to it — same public API,
generalized implementation, per Phase 0's "ABSORB INTO AUTHORITY LAYER"
classification of that module). A caller declares a list of
`ProvenanceEntry` objects (`kind`: `memory_read` / `tool_output` /
`sub_agent_result` / `user_input` / `external_content`; `trust`:
`TRUSTED` / `UNTRUSTED` / `UNKNOWN`; optional `content`/`source_id`) via
the reserved `_provenance` key in an `ActionRequest`'s `arguments` —
the same argument-driven, action-type-agnostic convention
`AuthorityContext.constraints`' `memory_scope` already established.
`analyze_causal_influence()` runs the shared pattern scan across every
entry's content and separately tracks which entries are
untrusted/unknown.

**Honestly scoped, stated in the module's own docstring**: this
platform does not sit inside an agent framework's reasoning loop and
cannot observe on its own what upstream content actually shaped a given
tool call — there is no runtime hook here to intercept an LLM's context
window. Provenance must be *declared*; no caller declaring it (every
caller before this module existed) means this check never fires,
identical to prior behavior.

**Wired into the request path**: `WhitePactRuntimeGateway._causal_influence_reasons()`
runs alongside the existing memory-firewall check. A matched injection
pattern in any provenance entry's content is a hard `DENY`
(`ReasonCode.CAUSAL_INFLUENCE_VIOLATION`) — the same severity
`MEMORY_FIREWALL_VIOLATION` already carries, generalized to any source.
Untrusted/unknown provenance with no pattern match is a softer,
non-blocking, evidence-visible marker
(`ReasonCode.CAUSAL_INFLUENCE_UNTRUSTED_SOURCE`) attached to whatever
decision the action otherwise receives (including a plain `ALLOW`) —
never a reason to deny by itself in this first version, matching the
Tool Trust Network's own deliberately bounded first-increment choice
(§4.2) rather than also modulating risk tier.

Exposed directly via the `rai_causal_influence_check` MCP tool for
standalone pre-flight checks, independent of whether the caller routes
through governed dispatch at all.

---

## 5. Multi-tenancy and organization boundary **[TODAY]**

Every entity in this spec that carries `organization_id` is not
aspirational — real multi-tenant isolation exists today: `OrgContext`,
per-org rate limiting (SHA-256-keyed bearer tokens, not a shared global
pool), and RBAC roles scoped per organization. The target architecture's
`AgentContext.organization_id` and `EvidenceRecord.organization_id` are
designed to compose with this existing boundary, not replace it.

---

## 6. Deterministic vs. probabilistic controls

This distinction is a first-class architectural principle, not an
afterthought — see `DETERMINISTIC_VS_PROBABILISTIC.md` for the full
inventory of which current components are which and why the distinction
matters more for a governance layer than for ordinary application code
(`MIGRATION_WHITEPACT_V2.md` Section 11.5).

**Deterministic** (same input → same output, always, no model call):
identity checks, RBAC role checks, rate limits, `rai_scan`'s
regex/pattern-based PII detection, policy threshold rules, cryptographic
hash-chain verification.

**Probabilistic** (a model or heuristic produces a confidence-scored
judgment): `rai_hallucination`'s risk scoring, `rai_bias_evaluate`'s
probe-based bias detection, semantic policy interpretation (not yet
built).

**Rule**: WhitePact must never present a probabilistic evaluation's
output as a guarantee. Every probabilistic result in `EvidenceRecord`
must carry a confidence/limitation annotation, and the fast, low-risk
decision path (Phase 9's LOW tier) must be satisfiable using
*deterministic* checks alone — an agent should never be forced through
an LLM call just to get a routine, low-risk action approved.

---

## 7. What this spec deliberately does not yet define

Per this project's own engineering discipline (no speculative
architecture beyond what's needed): the following are named in the
migration plan but intentionally left undesigned in this document until
their own phase is reached, so this spec doesn't accumulate unreviewed
speculative detail:

- A richer policy rule language beyond `PolicyRule`'s plain
  risk-tier/action-type/target matching (Phase 10's first version now
  exists — see Section 3.5 — but OPA/Rego or an expression language, if
  ever needed, is still undesigned).
- A richer approval-workflow lifecycle beyond `ApprovalRequest`'s
  `PENDING -> APPROVED`/`DENIED`/`CONSUMED` (Phase 11's first version
  now exists — see Section 3.6's `REQUIRE_APPROVAL` row. The execution-
  binding invariants are real and tested:
  `ApprovalRequest.action_digest` (SHA-256 over action_type/target/
  arguments, `governance/approval.py`) means an approval is valid only
  for the byte-identical action a human reviewed —
  `ApprovalRepository.consume()` is the one atomic operation an
  executor must call before running an approved action, and it
  enforces the mutation invariant (changed arguments raise
  `ApprovalActionMismatchError`), replay protection (a second call,
  whether identical or mutated, raises `ApprovalNotApprovedError`
  because the first call already transitioned the row to `CONSUMED`),
  and `resolve()` separately rejects an identity resolving its own
  request (`SelfApprovalError`) — `tests/test_approval_execution_
  binding.py`. Still undesigned: expiry/timeout, multi-approver
  quorum, and delegation-chain approval).
- A richer MCP Trust/Supply-Chain Scanner than the three checks in
  Section 4.1 (Phase 13's first version now exists — confusable
  characters, tool description content scan, known-incident
  cross-reference — but a full Unicode TR39 confusables implementation,
  publisher/domain identity verification, and actually connecting to a
  remote MCP server to fetch its manifest are all still undesigned).
- OAuth/OIDC scope names for remote MCP authorization (Phase 6) — to be
  designed against the actual current MCP specification, not guessed
  here.

---

## 8. Relationship to existing product documents

- `GAME_CHANGER_STRATEGY.md` / `GAME_CHANGER_BUILD_PLAN.md` — the
  infrastructure-first distribution bet (free public trust registry,
  agent-framework trust-check integrations). Still valid; WhitePact's
  runtime gateway is a superset, not a replacement, of that plan's
  `rai_check_trust` primitive.
- `VERSION_ROADMAP.md` / `STRATEGY_ROADMAP.md` — the pre-WhitePact
  version-numbered and business-phase roadmaps. Superseded in spirit by
  `MIGRATION_WHITEPACT_V2.md` for anything touching product identity;
  still accurate for governance-engine feature history.
- `TRUST_INDEX_SPEC.md`, `LEADERBOARD_METHODOLOGY.md` — unchanged,
  still the authoritative spec for those specific subsystems, which this
  document's Governance Engine section references rather than
  duplicates.

---

## 9. Package identity note

This spec is written using `WhitePact`-facing conceptual names
(`AgentContext`, `GovernanceDecision`, etc.) for the target architecture.
The actual Python package remains `src/responsibleai/` at the time of
this writing (158 files reference the `responsibleai` import path; see
the baseline audit). Phase 8's runtime governance core will land as new
modules; whether they live under a new `src/whitepact/` package or
inside the existing tree during a staged migration is decided in
`MIGRATION_WHITEPACT_V2.md`, not in this spec — this document defines
*what* the architecture is, not the filesystem layout of the migration.
