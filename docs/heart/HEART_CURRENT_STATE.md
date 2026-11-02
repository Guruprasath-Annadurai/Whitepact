# WhitePact Heart — Current State Audit (Phase H0)

> Read before writing any Heart code. Classifies every existing
> component the Heart/Sovereignty Kernel design touches, so the
> implementation reuses working code instead of duplicating it. Every
> claim below is sourced from the actual codebase, not memory — file
> paths and line numbers are given so they can be independently
> re-checked as the code moves.

## Classification legend

- **REUSE** — consume as-is, no changes needed.
- **EXTEND** — the Heart adds fields/methods to an existing type without
  changing its existing behavior or breaking existing callers.
- **REFACTOR** — the Heart requires a real internal change to an
  existing component.
- **ABSORB** — an existing component becomes *part of* a new Heart
  concept's implementation, referenced by it rather than duplicated.
- **OUTSIDE HEART** — deliberately not part of the trusted core; stays
  where it is, may call into the Heart but the Heart never depends on it.
- **LEGACY** — works today, has a known real gap, not fixed by this
  audit (documented, not silently left implicit).

## 1. Identity / authentication surface

| Component | File | Classification | Notes |
|---|---|---|---|
| `JWTClaims` (OIDC) | `auth/oidc.py` | **OUTSIDE HEART** | Identity *proof* production is an adapter concern (JWKS fetch, signature verify). The Heart consumes the *result* (a verified identity claim), never re-implements token verification. |
| `SAMLAssertionClaims` | `auth/saml.py` | **OUTSIDE HEART** | Same reasoning; deliberately mirrors `JWTClaims`'s shape per its own docstring, confirming this convention is already established, not something the Heart needs to invent. |
| `VerifiableCredentialClaims` | `auth/verifiable_credential.py` | **OUTSIDE HEART** | Same reasoning. |
| Static API keys | `db/org_repository.py:160` | **OUTSIDE HEART** | Proves possession of a bearer secret only — the Heart's `RootAuthorityRecord` (Phase H3) must treat a bare API key as a *weaker* verification method than OIDC/SAML/VC, not an equal one. |
| `IdentityContext` | `governance/models.py:66-114` | **REUSE** | Already the "any actor kind" abstraction over the above. `RootAuthorityRecord` references an `IdentityContext.identity_id`, it does not replace this type. |

## 2. Authority representation

| Component | File | Classification | Notes |
|---|---|---|---|
| `AuthorityContext` | `governance/models.py:137-296` | **EXTEND** | `permits()`, `constraint_violation()` already implement most of what Phase H2's "Authority Lattice" needs (subset checks over action types + constraint dict). The Heart's `AuthorityEnvelope` (Phase H2) extends the *dimension set* (adding `data_scope`, `frequency`, `jurisdiction`, `environment` as new recognized constraint keys) rather than inventing a parallel lattice type. Reusing `constraints: dict[str, Any]`'s existing open-bag shape avoids a second incompatible authority representation existing side by side. |
| `validate_attenuation()` | `governance/models.py:299-411` | **EXTEND** | Real, tested, property-tested (`tests/test_property_based.py`) attenuation logic already enforces `child ⊆ parent` for every dimension it knows about. Documented, real gap: `allowed_hours_utc` is **not** attenuation-checked today (models.py:344-350, explicit comment). The Heart's constitutional law H3 ("delegation may only attenuate") requires this be closed — Phase H2 extends `validate_attenuation()` to cover every dimension the lattice recognizes, closing this specific documented gap rather than leaving it silently inherited into the Heart. |
| `OrgAuthorityCeiling` | `governance/ceiling.py:22-69` | **REUSE** | Already `A_org` in the Heart's `A_effective` intersection formula. No changes needed — `to_authority_context()` already produces exactly the shape `AuthorityEnvelope` intersects against. |

## 3. Delegation

| Component | File | Classification | Notes |
|---|---|---|---|
| `DelegationRecord` | `governance/delegation.py:27-64` | **REUSE** | Already has everything Phase H6 needs: parent pointer, attenuation-checked grant, expiry, revocation fields. |
| `DelegationRepository` | `db/delegation_repository.py` | **REUSE** (mostly) | `grant()`, `get_active_delegation()`, `get_authority_chain()`, `revoke_branch()`, `get_org_graph()`, `get_descendants()` are all real, tested, and exactly what a "Delegation Kernel" needs. Nothing here is being rebuilt. |
| Cascading revocation latency/concurrency | `db/delegation_repository.py:239` `revoke_branch()` | **LEGACY** | Functionally correct and tested (`tests/test_delegation_graph.py::TestCascadingRevocation`), but **no latency measurement and no dedicated race-condition test exists** for it today. Phase H9 (Revocation Kernel) must add both rather than assume "cascading revocation" is a solved problem — see `tests/test_concurrency.py::TestDelegationGrantConcurrency` for the *grant*-side concurrency pattern to mirror on the *revoke* side. |

## 4. Authority Passport, Intent Contract — nearest existing analogs to new Heart concepts

| Heart concept | Nearest existing component | Classification | Notes |
|---|---|---|---|
| `RootAuthorityRecord` (Phase H3) | *(none)* | **NEW** | No root-of-trust concept exists anywhere in the codebase today (confirmed by grep — zero hits for "root of trust", "root authority" as a formal type). Genuinely new. |
| `ConsentProof` (Phase H4) | *(none)* | **NEW** | No consent-distinct-from-authentication concept exists. `DelegationRecord.purpose: str` is free text, not a structured, digest-bound consent object. Genuinely new. |
| `PurposeBinding` (Phase H5) | `governance/intent.py`'s `IntentContract` | **ABSORB** | `IntentContract` already does almost exactly this: `allowed_action_types`, `allowed_targets`/`denied_targets`, `max_value_usd`, `intent_violation()`. Per the master prompt's own instruction not to duplicate working features, `PurposeBinding` **wraps and references** `IntentContract` (via `intent_ref`) rather than reimplementing a second, parallel purpose-scoping mechanism. The one genuine gap: `IntentContract.goal` is explicitly never machine-parsed (intent.py:24-28) — `PurposeBinding` doesn't change that; it stays a deterministic constraint check exactly like `IntentContract` already is, never an LLM-interpreted one. |
| `AuthorityPassport` | `governance/authority_passport.py` | **ABSORB (as evidence)** | Not replaced by the Heart's `LegitimacyEnvelope` — a passport is a portable *export* of held authority; `LegitimacyEnvelope` is a *point-in-time decision record*. They can reference each other but serve different purposes. Passport's own "not cryptographically signed, here's exactly why" reasoning (authority_passport.py:15-26) is the direct precedent the Heart's own signing decision (Phase H12/H13) should follow or explicitly diverge from with equal rigor. |

## 5. Execution / permit layer

| Component | File | Classification | Notes |
|---|---|---|---|
| `ExecutionAuthorization` | `governance/execution.py:123-165` | **OUTSIDE HEART, downstream consumer** | This is `EXECUTABLE_AUTHORITY` in the master prompt's own canonical relationship (`EXECUTABLE_AUTHORITY ⊆ BRAIN_AUTHORITY ⊆ HEART_AUTHORITY`). The Heart produces a `LegitimacyEnvelope`; the existing Brain/gateway pipeline still produces `ExecutionAuthorization` from a `DecisionResult` exactly as it does today. The Heart does not replace this layer, it bounds what the Brain is allowed to authorize. |
| "Why not signed" reasoning | `execution.py:14-30` | **REUSE (as precedent)** | Direct, adaptable reasoning for the Heart's own signing question — see `docs/heart/HEART_SIGNING_DECISION.md` (Phase H1 deliverable) for how this precedent applies (or doesn't) to constitutional digests. |

## 6. Revocation — the real gap

Confirmed by grep: **no unifying revocation-state primitive exists today.** Five independent mechanisms, each scoped to its own object type, none sharing an epoch or counter:

1. Delegation cascading revocation — `db/delegation_repository.py:239`
2. Delegation natural expiry — `governance/delegation.py:47`
3. Authority Passport revocation — `db/authority_passport_repository.py:128`
4. Authority Passport drift detection — `governance/authority_passport.py:245` (functions as a revocation signal, not literally one)
5. API key revocation — `db/org_repository.py:189`

**Classification: NEW** (Phase H9, `RevocationEpoch`). This is not a REFACTOR of the above — each keeps its own existing revocation mechanism exactly as-is (all are correct for their own object type). `RevocationEpoch` is a new, thin, additive concept: a monotonically increasing counter (per-org, per-scope) that a `LegitimacyEnvelope` is stamped with at issuance, so "was anything revoked since this envelope was issued" becomes one cheap comparison instead of five separate live re-checks. This is squarely in the "keep the Heart deliberately small" spirit — it adds one integer and one comparison, not a rewrite of five working systems.

## 7. Policy / constitution versioning — the real gap

`Policy.version` (`governance/policy.py:88`) and `governance_policy_versions` (`db/policy_repository.py:51-80`) are real, but **only track a monotonic ordinal for the current org-mutable rule set — there is no immutable, historically-replayable snapshot.** `DecisionResult.policy_version` records *which ordinal* was active, never *what that ordinal actually contained*.

**Classification: NEW** (Phase H1, `AuthorityConstitution`). Deliberately distinct from `Policy` — the master prompt's own distinction ("WhitePact Constitution" vs. "customer policy") maps directly onto the existing "Policy is org-mutable, admin-configurable" reality (`policy.py`'s own docstring) vs. a new, smaller, WhitePact-owned, non-customer-mutable law set. `Policy` stays exactly as it is; `AuthorityConstitution` sits above it, not replacing it.

## 8. Gateway evaluation order — where the Heart sits

`WhitePactRuntimeGateway.evaluate()` (`governance/gateway.py:169-306`) has a real, documented, first-match-wins precedence order today: quarantine → workflow composition → parent-authority attenuation → intent → `authority.permits()` → `require_approval_for` → `constraint_violation()` → policy → content scan → autonomy budget → PII redaction → trust.

**Classification: the Heart sits *before* this entire chain, not inside it.** Every one of `evaluate()`'s existing checks presupposes a caller already has *some* `AuthorityContext` object to evaluate. The Heart answers a logically prior question — does this identity have *any* legitimate authority to construct that object from at all. This mirrors how the existing continuous-delegation-reauthorization check already runs in `mcp/governance_integration.py`, ahead of `gateway.evaluate()` being called (`MACHINE_AUTHORITY_V1.md:61-67`) — the Heart generalizes an already-established architectural pattern, it doesn't invent a new insertion point.

`WhitePactRuntimeGateway.evaluate()` itself: **REUSE, unmodified.** `SovereigntyKernel.evaluate()` (Phase H13) is a new, separate entry point called *before* the existing gateway path, not a change to the gateway's own internals.

## 9. Testing infrastructure

- **Hypothesis** (`hypothesis>=6.100.0`, real `pyproject.toml` dependency) is already used for `tests/test_property_based.py::TestAttenuationProperties`. **REUSE this exact pattern** for every new Heart pure function (lattice comparison, attenuation, revocation-epoch comparison) — do not introduce a second property-testing convention.
- **Concurrency tests** — `tests/test_concurrency.py::TestDelegationGrantConcurrency` establishes the pattern for testing concurrent `grant()`. **REUSE this pattern** for Phase H9's revocation race-condition tests (revoke-before-evaluation, revoke-during-evaluation, concurrent revocation).
- **Formal verification (TLA+/Alloy)** — **NOT started, not claimed.** Per the master prompt's own instruction ("do not call anything formally verified until actual formal verification exists"), no TLA+/Alloy model exists in this repo, and building one is genuinely separate, specialized work this audit does not scope as achievable within the current implementation pass. Documented honestly as a gap in Phase H14's own deliverable, not silently skipped.

## 10. Canonical serialization / digests

`governance/approval.py`'s canonical-JSON + SHA-256 digest pattern (used by `ExecutionAuthorization.matches_action()` and `ApprovalRequest`) and `db/evidence_repository.py`'s per-org hash chain (`_compute_entry_hash()`) are **REUSE** candidates for the Heart's own `canonical_digest` fields (`RootAuthorityRecord`, `ConsentProof`, `PurposeBinding`, `LegitimacyEnvelope` all need one per the master prompt). Real, honest limitation to carry forward: `evidence_repository.py`'s hash covers only a fixed subset of fields (id/org_id/action_id/decision/evaluated_at/recorded_at), not the full record — the Heart's own digest functions must be explicit and complete about exactly which fields are covered, not silently narrower than a reader would assume.

## Summary verdict

The Heart is genuinely a *new, thin layer* over substantial existing correct infrastructure, not a rebuild. Real net-new surface: `AuthorityConstitution`, `RootAuthorityRecord`, `ConsentProof`, `RevocationEpoch`, `SovereigntyVeto`, `LegitimacyEnvelope`, `SovereigntyKernel.evaluate()`. Everything else — attenuation, delegation, ceilings, intent/purpose scoping, execution permits, canonical digests — already exists, is tested, and is reused or extended, never duplicated.

**PHASE H0 STATUS: PASS**
