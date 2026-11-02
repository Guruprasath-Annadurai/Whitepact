# Authority Contract — `AuthorityGrant` (Phase 1)

> Defines the boundary object between the Heart and the rest of
> WhitePact's live decision path. This is the one canonical production
> type representing "legitimate delegated authority to do this
> specific thing, right now" — everything downstream of Phase 5's
> Authority Resolver consumes this type, never raw Heart internals or
> raw DB rows directly.

## Why a new type, not a reused Heart type as-is

The Heart already has two candidate types, and this contract
deliberately **does not rewrite either** — it composes them:

- **`AuthorityEnvelope`** (`governance/authority_lattice.py`, Phase H2)
  — the *what*: effective granted authority across 15 dimensions
  (action types, targets, resources, value ceilings, hour windows,
  etc.), already the correct type for "what is this identity actually
  allowed to do."
- **`LegitimacyEnvelope`** (`governance/legitimacy_envelope.py`, Phase
  H12) — the *why/proof*: the Heart's final, portable verdict on
  whether the authority behind an action is legitimate (root traced,
  consented, purpose-bound, not revoked, not vetoed).

Neither type alone is what WhitePact's live decision path needs.
`AuthorityEnvelope` says nothing about *why* that authority is
legitimate; `LegitimacyEnvelope` says nothing about *what* is actually
granted. `AuthorityGrant` (`governance/authority_grant.py`, this
phase) is the production-layer object that bundles both, plus the
minimal request-context WhitePact's existing `gateway.evaluate()`
already needs (it is *not* a new decision engine — it's the shape that
lets a real request assemble a real `AuthorityContext`
(`governance/models.py`) honestly, instead of the synthesize-from-
authentication pattern `00_CURRENT_RUNTIME_MAP.md` §12 documented).

**Naming note**: not called `AuthorityEnvelope` (that name is already
the Heart's own H2 type) or `LegitimacyEnvelope` (already H12's type).
`AuthorityGrant` was chosen to match this codebase's own existing
vocabulary — `DelegationRecord.grant()`, `governance/delegation.py` —
rather than inventing new terminology for an old concept.

## Field classification

Every field below is tagged with what kind of claim it represents.
**WhitePact must never treat an unverified claim as verified
authority** — concretely, this means the `effective_authority` and
`legitimacy` fields (verified) are never derived from
`requested_action_type`/`requested_target`/`requested_purpose`
(user-provided) without passing through Heart validation first. The
resolver (Phase 5) is the only code allowed to construct an
`AuthorityGrant` — this module's constructor takes already-verified
inputs, the same "abstract input, not a live resolution" discipline
every Heart phase already established.

| Field | Classification | Source |
|---|---|---|
| `grant_id` | Derived | Generated at construction (nonce/unique identifier) |
| `organization_id` | Authenticated fact | `OrgContext.org_id` (§2/§3 of the runtime map) |
| `principal_id` | Authenticated fact | The authenticated identity (`IdentityContext.identity_id`) |
| `acting_agent_id` | Authenticated fact | `AgentContext.agent_id` — today equals `principal_id` in live code (§4), kept as a distinct field since the Heart's own model (H3-H6) treats "who authenticated" and "who is delegated to act" as separable |
| `requested_action_type` | User-provided claim | The caller's `ActionRequest.action_type` — what they're *asking* to do |
| `requested_target` | User-provided claim | The caller's `ActionRequest.target` |
| `requested_purpose` | User-provided claim | Free text until bound; becomes an authorization fact only once matched against a `PurposeBinding` |
| `effective_authority` | Authorization fact (verified) | The Heart's `AuthorityEnvelope` (H2) — the actual, lattice-intersected granted authority. **Never** a copy of the request |
| `legitimacy` | Authorization fact (verified) | The Heart's `LegitimacyEnvelope` (H12) — root/consent/purpose/delegation/revocation verdict |
| `root_reference` | Derived (audit pointer) | `RootAuthorityRecord.root_id`, opaque string, not the full record |
| `consent_reference` | Derived (audit pointer) | `ConsentProof.consent_id`, opaque string |
| `delegation_reference` | Derived (audit pointer) | `DelegationRecord.delegation_id`, opaque string |
| `policy_constraints` | Policy-derived constraint | Whatever `OrgAuthorityCeiling`/org policy narrows the effective authority to — distinct from what the Heart itself verified |
| `issued_at` | Derived | Construction time |
| `expires_at` | Derived | Short TTL, mirrors `ExecutionAuthorization`'s existing 30s pattern (`governance/execution.py`) — an `AuthorityGrant` is not meant to be a long-lived credential |
| `canonical_digest` | Derived (integrity) | SHA-256 over every field above, same canonicalization discipline every Heart record already uses |

## Invariants this contract enforces

1. **`is_legitimate` is a pure function of `legitimacy.is_legitimate`** — `AuthorityGrant` never overrides or second-guesses the Heart's own verdict; it is read-only with respect to legitimacy, exactly as `LegitimacyEnvelope` itself is read-only with respect to `HeartVetoRecord`.
2. **`effective_authority` is never derived from the request fields** — it comes only from the Heart's own `AuthorityEnvelope` composition (H2's `intersect_envelopes()`), so a caller cannot smuggle a wider grant through by simply asking for one.
3. **No field here is signed or independently verifiable at rest** — same, explicitly inherited limitation every Heart record has (`docs/heart/HEART_SIGNING_DECISION.md`). `canonical_digest` is an integrity aid (tamper-*evidence*, detectable on comparison), not tamper-*proof* cryptographic authentication. This is named honestly, not glossed over, consistent with the whole Heart initiative's own discipline.
4. **A grant with `is_legitimate=False` must never reach `gateway.evaluate()` as an `ALLOW`-eligible `AuthorityContext`** — enforced structurally in Phase 6 (the wiring phase), not by this contract type alone; this type only carries the data, it does not enforce the veto itself (that remains `heart_veto.enforce_heart_veto()`'s job, unchanged).

## Conversion to the existing `AuthorityContext`

WhitePact's `gateway.evaluate()` is explicitly **not** being rewritten
(per the master prompt's own rule #2 and #3). `AuthorityGrant` provides
`to_authority_context()`, converting `effective_authority` (the Heart's
`AuthorityEnvelope`) into a `governance/models.py` `AuthorityContext`
via the already-existing, already-tested `envelope_to_authority_context()`
(H2, `authority_lattice.py`) — reused, not reimplemented. This is the
one place old and new meet: everything upstream is new (Heart-derived,
verified); everything downstream (`gateway.evaluate()` onward) is the
existing, unmodified WhitePact decision path.

## What this phase does not do

- Does not resolve a real `AuthorityGrant` from live identity/DB state
  (Phase 5, the Authority Resolver).
- Does not persist `AuthorityGrant` (no new table this phase — Phase 3).
- Does not wire this into `apply_governance()`/`apply_upstream_governance()`
  (Phase 6).
- Does not change `gateway.evaluate()`, `AuthorityContext`,
  `ExecutionAuthorization`, or any existing Heart module.
