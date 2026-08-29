# Authority Resolver — Phase 5

> Continues `docs/heart-production/`'s own numbered series (`00`
> runtime audit, `01` `AuthorityGrant` contract, `02` identity
> resolution, `03` — used by Zero-Trust Identity's `IdentityKind`
> work, a related but separately-tracked gap; this file is `04`). Both
> `00_CURRENT_RUNTIME_MAP.md` and `01_AUTHORITY_CONTRACT.md` already
> named "Phase 5, the Authority Resolver" as this initiative's next
> unbuilt step — this is that step.

## Reproduction

Re-verified against the current codebase, not assumed from the older
docs: `sovereignty_kernel.evaluate()` (`governance/sovereignty_kernel.py:104`)
is real and already composes H3 (root) through H12 (legitimacy
envelope) — but nothing in `src/` calls it. `root_authority.
validate_root_chain()`'s `RootResolver` Protocol
(`governance/root_authority.py:230`) is a plain **synchronous**
callable; this codebase's DB repositories, including the
`RootAuthorityRepository` this remediation built in Gap 3 Phase 3, are
all **async**. No existing pattern in this codebase bridges a
synchronous callback to an async repository lookup without either
`asyncio.run()` (unsafe if already inside a running event loop, which
every live request handler is) or a prefetch-then-wrap approach — the
latter is what this phase implements.

## What this phase builds

`src/responsibleai/governance/authority_resolver.py`:

- **`resolve_root_for_identity()`** — get-or-create: returns the
  latest `RootAuthorityRecord` already issued for an identity (via a
  new `RootAuthorityRepository.get_latest_for_subject()` method, added
  this phase, mirroring `AuthorityPassportRepository.
  get_active_for_principal()`'s existing "latest wins" convention), or
  builds and persists a fresh one via the already-existing
  `identity_authority_adapter.build_root_authority_record_from_identity()`
  if none exists yet. Deliberately does **not** re-issue a new root
  just because an existing one is revoked/expired — a revoked identity
  must stay revoked, not get a fresh root that silently bypasses it.
- **`prefetch_root_chain()`** — walks `authority_source` pointers via
  real, awaited DB lookups into a plain dict, bounded and cycle-safe
  (mirroring `validate_root_chain()`'s own walk), so a synchronous
  `RootResolver` closure can serve the chain without awaiting anything
  itself.
- **`resolve_authority_grant()`** — the main entrypoint: resolves the
  root, prefetches its chain, calls `sovereignty_kernel.evaluate()`
  (root + non-delegable-authority checks only — see below), converts
  the existing `AuthorityContext` into an `AuthorityEnvelope` via the
  already-existing `authority_context_to_envelope()` adapter, and
  wraps both in a real `AuthorityGrant` via the already-existing
  `build_authority_grant()`.

This is the first code in this codebase that actually asks Heart Phase
H3's question — "does this identity's authority trace to a legitimate
human/organization root" — about a real, live identity, closing the
core gap `00_CURRENT_RUNTIME_MAP.md` §12 named: "the entire root of
the delegation graph is a DB insert by an authenticated admin, full
stop."

## What this phase honestly does not do

- **Does not run consent, purpose-binding, or delegation-legitimacy
  checks.** These three Heart checks (H4/H5/H6) all require a real
  `ConsentProof`, and no live path in this codebase produces one —
  `consent_proof.py`'s own docstring states real consent-capture
  wiring is "not built here." `resolve_authority_grant()` correctly
  leaves these `None` in the `sovereignty_kernel.evaluate()` call
  rather than fabricating a synthetic `ConsentProof` to make them
  "run" — a fake-but-passing check would be worse than an honestly
  absent one, since it reads as a real guarantee it isn't. Building a
  live consent-capture flow is separate, future, largely
  product-shaped work (a UI/API surface, not a governance-engine
  change), not scoped into this phase.
- **Does not run revocation-epoch checking.** `RevocationEpoch`
  (`revocation_kernel.py`) is confirmed purely in-memory today — no DB
  repository exists, and that module's own docstring states none of
  its five candidate call sites are wired to `bump_epoch()` yet.
  Persisting and wiring real revocation epochs is a distinct follow-up.
- **Does not change what authority is actually granted.**
  `effective_authority` is derived from the existing, already-tested
  `AuthorityContext` (ceiling + delegation determination — unchanged)
  via the existing `authority_context_to_envelope()` adapter. This
  phase adds a root-of-trust check *on top of* today's authority
  determination; it does not replace or reimplement how much authority
  a request actually has.
- **Is not wired into `apply_governance()`/`apply_upstream_governance()`
  (Phase 6).** Calling this resolver on every live governed request —
  the single hottest, most safety-critical path in the codebase — is a
  distinct, higher-risk change deserving its own dedicated
  verification pass (real-request-shaped tests, careful thought about
  what happens when `resolve_authority_grant()` itself fails, whether
  it should be fail-closed or fail-open pending further design). This
  phase deliberately ships a resolver that is real, tested, and
  callable, but not yet load-bearing for any live decision.

## What happens if this were wired in naively (why Phase 6 is separate)

Worth stating plainly: as things stand, a request from an identity
whose root doesn't resolve (e.g. an `"oidc"`-kind identity with no
`authority_source` supplied) would get a `LegitimacyEnvelope` with
`root_result.status = ROOT_TYPE_CANNOT_SELF_ORIGINATE`, and — per
`heart_veto.py`'s conflict-resolution composition — this may or may
not actually veto the grant depending on exactly how
`resolve_authority_conflicts()`/`apply_heart_veto()` treat a
non-terminal, unresolved root result versus an *absent* one. This
phase does not resolve that ambiguity by testing it end-to-end against
live traffic; it is exactly the kind of question Phase 6's own
dedicated pass needs to settle carefully, with real tests against real
identity kinds, before any live request's outcome depends on it.

## Verification

- New tests in `tests/test_authority_resolver.py` (see commit for
  count), covering: get-or-create root resolution, chain prefetching
  (linear chain, cycle, missing source, depth bound), the sync
  resolver wrapper's correctness against a prefetched dict, and
  `resolve_authority_grant()` end-to-end against a real (`:memory:`)
  `RootAuthorityRepository` — for both a terminal identity (grant's
  legitimacy is immediately valid) and a non-terminal one with no
  resolvable source (legitimacy correctly reports the chain as
  unresolved, not silently valid).
- `ruff check` / `ruff format --check` clean.
- `mypy src/responsibleai`: clean, 168 source files.
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.
