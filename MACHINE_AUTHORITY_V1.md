# Machine Authority Infrastructure — V1

Last reviewed: 2026-08-17 · Platform version: 1.2.0

This is the authoritative inventory of WhitePact's v3 authority-layer work
— the concrete answer to the problem stated in `MACHINE_AUTHORITY_PROBLEM.md`.
Every primitive below is real, shipped code with real tests; nothing here is
aspirational. `SPEC.md` remains the broader architecture document (the full
governance pipeline, risk tiering, policy engine, MCP tool surface);
this document is the focused index of the machine-authority primitives
specifically, cross-referenced rather than duplicated. `ENFORCEMENT_BOUNDARY.md`
states precisely where each primitive's authority stops — read that before
relying on any claim here in a specific deployment.

## The eight core invariants

| # | Invariant | Module | Enforced at |
|---|---|---|---|
| 1 | Authority attenuation — a delegated grant never exceeds its delegator's | `governance/models.py::validate_attenuation()` | Gateway step 0 (`gateway.py`), and at delegation-grant time (`db/delegation_repository.py::grant()`) |
| 2 | Delegation Graph — persisted, queryable, cascade-revocable | `governance/delegation.py`, `db/delegation_repository.py` | Continuous re-authorization on every governed call (`mcp/governance_integration.py`) |
| 3 | Workflow composition — a forbidden *sequence* of individually-permitted actions | `governance/workflow.py::check_composition_violation()` | Gateway step -1 |
| 4 | Org Authority Ceiling — a structural cap no per-call grant can exceed | `governance/ceiling.py` | Gateway attenuation check, via `parent_authority` |
| 5 | Continuous MCP Trust — bounded-staleness re-verification, not check-once-cache-forever | `integrations/client.py::TrustClient` | Gateway `_trust_reason()` |
| 6 | Memory Authority / Memory Firewall — injection-pattern scan + scope isolation for persistent memory | `governance/memory_firewall.py`, `AuthorityContext.constraints["memory_scope"]` | Gateway content-scan step; `rai_memory_write_check`/`rai_memory_read_check` MCP tools |
| 7 | Autonomy Budget — a rolling-window cap on unsupervised action volume | `governance/autonomy_budget.py` | Gateway step, right after the hard-block check |
| 8 | Evidence Bundle — offline-verifiable, tamper-evident export | `governance/evidence_bundle.py` | `GET`/`POST /api/governance/evidence/bundle*` |

Plus one cross-boundary primitive that governs a different trust edge
entirely (agent-to-agent, not agent-to-tool):

| — | A2A Trust Gate — outbound agent-to-agent calls gated on remote-agent trust + memory-firewall scan of the message | `integrations/a2a_adapter.py::A2ATrustGate` | Caller-invoked, before sending a Task/Message |

## 1. Authority Attenuation

`validate_attenuation(parent, child)` checks, first-violation-wins:
`granted_action_types` (child ⊆ parent), `constraints["max_value_usd"]`
(child ≤ parent, if parent has one), `constraints["denied_targets"]` (every
parent denial preserved), `constraints["allowed_targets"]` (exact-string
subset, not glob-algebra), `constraints["max_delegation_depth"]`, and
`require_approval_for` (a parent-required approval can't be silently
dropped). Deliberately not checked: `allowed_hours_utc` (real interval math
not attempted) and `delegation_chain` depth (handled by
`constraint_violation()`'s own `max_delegation_depth` check).

Property-tested (`tests/test_property_based.py::TestAttenuationProperties`):
across generated action-type sets and value limits, a genuine narrowing
never escalates and any widening is always caught.

## 2. Delegation Graph

`DelegationRecord` (`org_id`, `from_identity_id` — `None` for a root grant,
`to_identity_id`, `constraints`, `expires_at`, `revoked_at`) persisted via
`DelegationRepository`. `grant()` enforces attenuation against the
delegator's own currently-active grant at write time (raises
`DelegationEscalationError`, not a silent narrowing). `revoke_branch()`
cascades: revoking an identity's delegation also invalidates every
descendant transitively (BFS over the graph). `get_authority_chain()` walks
root-first; `explain_authority()` gives a deterministic, non-LLM structured
explanation of a chain.

**Continuous re-authorization**: `mcp/governance_integration.py` checks the
calling identity's *latest* delegation fresh on every governed call — a
grant valid an hour ago that's since been revoked or expired is denied now,
with `AUTHORITY_REVOKED`/`AUTHORITY_EXPIRED`, before the gateway's normal
pipeline even runs. An identity that was never granted a delegation via
this graph at all is unaffected (falls through to normal evaluation) —
identical to behavior before this feature existed.

One deliberate scope limit, stated honestly: a delegation's `constraints`
are recorded and used for the attenuation-at-grant-time and
continuous-reauth checks, but are **not** currently merged into the
per-call `AuthorityContext.constraints` the gateway evaluates (that role is
filled today by the Org Authority Ceiling). A future increment could wire
delegation constraints directly into per-call enforcement; not attempted in
V1.

## 3. Workflow Authority Engine

`check_composition_violation(recent_actions, new_action_type, new_action_at, rules)`
fires only when `new_action_type` is the step that *completes* a forbidden
`WorkflowSequenceRule.action_types` ordered subsequence — checked as "the
pattern doesn't already match history alone, but does once this action is
appended," so a rule fires exactly once, on the completing action, not on
every action afterward. Each rule carries its own `window_minutes`; a
single fetched history (`EvidenceRepository.list_recent_actions()`, widest
window across an org's configured rules) serves all of them.

## 4. Org Authority Ceiling

`OrgAuthorityCeiling` (one row per org) is a structural envelope every
per-call `AuthorityContext` is checked against via `validate_attenuation()`
as the live `parent_authority`. Value/target/depth constraints are also
copied directly onto the per-call authority so the existing,
action-aware `constraint_violation()` path does the actual value-limit
denial (a call with no dollar argument at all is correctly a no-op, not a
false escalation — see the code comment in `mcp/governance_integration.py`
explaining the bug this design avoids). `allowed_action_types: None`
synthesizes a ceiling that grants exactly whatever's requested, so an
unconfigured ceiling never blocks anything — additive, not a new default
restriction.

## 5. Continuous MCP Trust

`TrustClient` caches a Trust Index result per `(model, provider)` for a
configurable TTL (`DEFAULT_CACHE_TTL_MINUTES`, opted into only by the
governed hosted-dispatch path — every other caller, including the
LangChain/LangGraph/ADK integrations, keeps the pre-existing always-live
behavior). Past the TTL, a live re-fetch is attempted; if it fails, the
prior cached result is served with `stale=True` rather than silently
treated as fresh. The gateway downgrades any decision to
`REQUIRE_APPROVAL` when `trust_state.stale` is set, **regardless of the
score it carries** — staleness is about how the data was obtained, not
what it says.

## 6. Memory Authority / Memory Firewall

`scan_memory_write(content)` is a deterministic regex scan (no LLM call)
for prompt-injection patterns aimed specifically at persistent memory —
fake role markers (`system:`/`assistant:` at line start), instruction
overrides ("ignore all previous instructions"), role hijacks ("you are now
a..."), prompt-leak attempts. Distinct from and additional to
`GuardrailsEngine`'s general PII/toxicity scan, because the risk is
specific: a poisoned memory write is replayed as trusted context in every
future session that reads it back, not seen once like a normal argument.

`AuthorityContext.constraints["memory_scope"]` (a namespace prefix, e.g.
`"org:acme:agent:bot1"`) enforces cross-tenant/cross-agent memory
isolation — a call's `memory_scope` argument must equal or nest under the
authority's configured scope.

Two MCP tools (`rai_memory_write_check`, `rai_memory_read_check`) let any
external memory system — WhitePact hosts no memory store of its own — gate
a write/read through this scanner before actually persisting or serving
content, the same pattern `rai_check_trust` established for third-party
model trust lookups.

## 7. Autonomy Budget

`AutonomyBudgetPolicy(max_autonomous_actions, window_minutes)`, one per
org, optional (no default — unlike quarantine, this is a genuine per-org
policy choice, not a circuit breaker every org gets for free).
`recent_autonomous_action_count()` sums `ALLOW` + `ALLOW_WITH_REDACTION`
decisions in the window (both executed with no human in the loop; `DENY`/
`QUARANTINE`/`REQUIRE_APPROVAL` don't count). Checked in the gateway right
after the hard-block step, before PII-redaction and trust — an exhausted
budget forces `REQUIRE_APPROVAL` regardless of what the call would
otherwise have decided, including overriding what would've been a
redaction-only `ALLOW_WITH_REDACTION`.

## 8. Evidence Bundle

Every governance decision is already hash-chained per-org
(`db/evidence_repository.py`, sha256 over `prev_hash` + immutable fields).
`build_evidence_bundle()` packages a chronological slice of that chain (via
the new `EvidenceRepository.list_for_bundle()`) into one artifact with a
**bundle-level digest** — sha256 over every included record's own hash, in
order — so the export itself is tamper-evident as a single unit, not just
link-by-link. `verify_evidence_bundle()` recomputes everything purely from
the bundle's own serialized dict: no DB import, no live
`EvidenceRepository` call. A time-scoped bundle's first record's
`prev_hash` is an honest external anchor, not something the bundle alone
proves back to genesis — see the module's own docstring.

## A2A Trust Gate

`A2ATrustGate.check()`/`check_async()` gate an *outbound* agent-to-agent
call on two dimensions: the remote agent's Trust Index score (reusing
`TrustClient`), and a Memory Firewall scan of the outbound message (reusing
`scan_memory_write()` — an A2A message becomes part of the receiving
agent's context, the identical risk a memory write poses). Framework-
agnostic core (plain strings, no `a2a-sdk` dependency); an optional,
explicitly best-effort duck-typed extraction helper pulls those strings out
of real SDK objects when the `a2a` extra is installed.

## Identity Bridge — Entra ID, Google Workspace, Okta, AWS

`integrations/identity_bridge.py` maps each provider's own ID token claim
shape into `IdentityContext` — `entra_claims_to_identity()`,
`google_claims_to_identity()`, `okta_claims_to_identity()`,
`aws_claims_to_identity()` — plus `map_groups_to_authority()`, which turns
an IdP's group/role identifiers into a granted-action-types
`AuthorityContext` via a caller-supplied mapping (this codebase has no
opinion on what any given group *should* grant).

**Honestly scoped, same discipline as everywhere else in this document**:
these are pure claims-mapping functions over an already-validated JWT
payload (they don't validate a token or call a network endpoint
themselves — `auth/oidc.py::OIDCProvider` still does that). Each mapping
is verified against that provider's own *publicly documented* ID token
shape (`tests/test_identity_bridge.py`'s sample payloads) — not against a
live tenant of any of these four providers, since this project has no
real Entra/Google Workspace/Okta/AWS account to test against. Three real,
named gaps: Entra's `groups` claim carries group *object GUIDs*, not
names — resolving those needs a live Microsoft Graph API call, not made
here; Google Workspace group membership isn't in the ID token at all —
needs the Admin SDK Directory API, not implemented; AWS is covered for
OIDC-issued tokens only (Cognito, IAM Identity Center) — the SigV4-signed
`AssumeRoleWithWebIdentity`/STS mechanism is a different, non-bearer-JWT
integration this module does not attempt.

## Verification

- `tests/test_property_based.py` — Hypothesis property tests for the pure
  invariant functions (attenuation, constraint violation, workflow
  composition, memory firewall) across generated inputs, not just
  hand-picked examples.
- `tests/test_whitepact_gauntlet.py` — one live, end-to-end adversarial
  test proving all eight invariants above hold *together* against a single
  real governed org/session, not just individually.
- Each primitive's own `tests/test_*.py` file (unit, gateway wiring, live
  MCP dispatch, REST API) — see `MIGRATION_WHITEPACT_V2.md` and this
  repository's commit history for the itemized build sequence.
