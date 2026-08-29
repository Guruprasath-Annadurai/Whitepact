"""Authority Resolver (Heart → WhitePact Production Integration, Phase
5). See `docs/heart-production/04_AUTHORITY_RESOLVER.md` for the full
design rationale, and this module's own "What this module does not
do" section below for its honest scope limits.

**The job**: turn an already-authenticated `IdentityContext` + real DB
state into the inputs `sovereignty_kernel.evaluate()` needs, and wrap
the result in a real `AuthorityGrant` (`governance/authority_grant.py`,
Phase 1) -- the one thing `01_AUTHORITY_CONTRACT.md` names as this
phase's exclusive job ("the resolver is the only code allowed to
construct an `AuthorityGrant`").

**What becomes real for the first time**: `00_CURRENT_RUNTIME_MAP.md`
§12 names the core gap this module closes -- "the entire root of the
delegation graph is a DB insert by an authenticated admin, full stop."
`resolve_root_for_identity()` below is what finally asks Heart Phase
H3's own question ("is this identity's claimed root legitimate,
tracing to a real human/organization root") about a live identity,
instead of trusting an `AuthorityContext` synthesized straight from
authentication with no root-of-trust check at all.

**The sync/async `RootResolver` bridge**: `root_authority.
validate_root_chain()`'s `RootResolver` Protocol is a plain
synchronous callable (by design -- Heart TCB-minimization, no DB
dependency baked into H3 itself), but this codebase's DB repositories
are all async. `prefetch_root_chain()` below walks the chain with real
`await`s first, into a plain `dict[str, RootAuthorityRecord]`, then
wraps that dict in a trivial synchronous closure -- the sync callback
itself never awaits anything, so no `asyncio.run()`/nested-event-loop
hazard exists. Bounded to the same `_MAX_CHAIN_DEPTH` as
`validate_root_chain()` itself, for the same reason (a defensive
circuit breaker against a misconfigured or adversarial chain).

**What this module does not do -- named honestly**:

- **Does not run consent, purpose-binding, or delegation-legitimacy
  checks.** `sovereignty_kernel.evaluate()` only runs each H4/H5/H6
  check when its prerequisite inputs are all supplied -- and this
  codebase has no live path that produces a real `ConsentProof`
  (`consent_proof.py`'s own docstring: "not built here: real wiring
  from an actual consent-capture UI/flow"). Fabricating a synthetic
  `ConsentProof` to make those checks "run" would be exactly the kind
  of fabricated capability this whole remediation exists to prevent --
  worse than not running them at all, since a fake-but-passing check
  reads as a real guarantee. `resolve_authority_grant()` therefore
  supplies only `root`/`root_resolver`/`requested_action_types` to
  `evaluate()`; the resulting `LegitimacyEnvelope`'s consent/purpose/
  delegation-legitimacy sub-results are always absent (not evaluated),
  never fabricated as passing.
- **Does not run revocation-epoch checking.** `RevocationEpoch`
  (`revocation_kernel.py`) is purely in-memory today -- confirmed, no
  DB repository exists for it, and that module's own docstring states
  none of the five candidate call sites are wired to `bump_epoch()`
  yet. Persisting and wiring real revocation epochs is separate,
  future work.
- **Does not change what `AuthorityContext`/`gateway.evaluate()`
  actually grants.** `effective_authority` is derived from the
  existing, already-tested `AuthorityContext` (ceiling + delegation
  authority determination, unchanged) via the existing
  `authority_context_to_envelope()` adapter -- this phase adds a real
  root-of-trust check *on top of* today's authority determination, it
  does not replace or reimplement it.
- **Is not wired into `apply_governance()`/`apply_upstream_governance()`
  (Phase 6).** Calling this resolver on every live governed request is
  a safety-critical hot-path change deserving its own dedicated
  verification pass, deliberately scoped out of this phase -- see
  `docs/heart-production/04_AUTHORITY_RESOLVER.md`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from responsibleai.governance.authority_grant import AuthorityGrant, build_authority_grant
from responsibleai.governance.authority_lattice import authority_context_to_envelope
from responsibleai.governance.identity_authority_adapter import (
    build_root_authority_record_from_identity,
)
from responsibleai.governance.root_authority import RootAuthorityRecord
from responsibleai.governance.sovereignty_kernel import evaluate as sovereignty_evaluate

if TYPE_CHECKING:
    from responsibleai.db.root_authority_repository import RootAuthorityRepository
    from responsibleai.governance.models import (
        ActionRequest,
        AgentContext,
        AuthorityContext,
        IdentityContext,
    )
    from responsibleai.governance.root_authority import RootResolver

# Same bound validate_root_chain() itself uses -- a legitimate chain
# should never be long; this exists purely as a defensive circuit
# breaker, duplicated (not imported) since root_authority.py's own
# constant is module-private by convention (leading underscore).
_MAX_CHAIN_DEPTH = 32


async def resolve_root_for_identity(
    identity: IdentityContext,
    repo: RootAuthorityRepository,
    *,
    issuer: str,
    verification_method: str,
) -> RootAuthorityRecord:
    """Get-or-create: the latest root record already issued for
    `identity.identity_id` (via `RootAuthorityRepository.
    get_latest_for_subject()`), or a freshly built and persisted one if
    none exists yet. Deliberately does not re-issue a fresh root just
    because the existing one is revoked or expired -- returning the
    existing (invalid) record and letting `validate_root_chain()`
    report `REVOKED`/`EXPIRED` is the fail-closed behavior; silently
    minting a new root to paper over a revocation would defeat the
    revocation entirely."""
    existing = await repo.get_latest_for_subject(
        identity.identity_id, organization_id=identity.org_id
    )
    if existing is not None:
        return existing

    record = build_root_authority_record_from_identity(
        identity, issuer=issuer, verification_method=verification_method
    )
    return await repo.create(record)


async def prefetch_root_chain(
    root: RootAuthorityRecord,
    repo: RootAuthorityRepository,
    *,
    max_depth: int = _MAX_CHAIN_DEPTH,
) -> dict[str, RootAuthorityRecord]:
    """Walks `authority_source` pointers via real, awaited DB lookups,
    into a plain dict a synchronous `RootResolver` closure can then
    serve without awaiting anything itself (see module docstring).
    Bounded and cycle-safe, mirroring `validate_root_chain()`'s own
    walk -- this function does not itself validate anything (that
    stays `validate_root_chain()`'s job when `sovereignty_kernel.
    evaluate()` calls it), it only makes the chain available to walk."""
    prefetched: dict[str, RootAuthorityRecord] = {root.root_id: root}
    current = root
    seen: set[str] = {root.root_id}
    depth = 0
    while not current.is_terminal() and depth < max_depth:
        source_id = current.authority_source
        if source_id is None or source_id in seen:
            break
        source = await repo.get(source_id)
        if source is None:
            break
        prefetched[source_id] = source
        seen.add(source_id)
        current = source
        depth += 1
    return prefetched


def _sync_resolver_from_prefetch(prefetched: dict[str, RootAuthorityRecord]) -> RootResolver:
    def _resolve(root_id: str) -> RootAuthorityRecord | None:
        return prefetched.get(root_id)

    return _resolve


async def resolve_authority_grant(
    identity: IdentityContext,
    agent: AgentContext,
    action: ActionRequest,
    authority_context: AuthorityContext,
    root_repo: RootAuthorityRepository,
    *,
    issuer: str,
    verification_method: str,
) -> AuthorityGrant:
    """The main entrypoint. Builds a real `AuthorityGrant` for one
    action request:

    1. Get-or-create this identity's root of trust
       (`resolve_root_for_identity()`).
    2. Prefetch its chain and wrap it as a sync `RootResolver`
       (`prefetch_root_chain()` + `_sync_resolver_from_prefetch()`).
    3. Run `sovereignty_kernel.evaluate()` -- **root validation and
       non-delegable-authority checking only**, this phase's honest
       scope (see module docstring's "what this does not do" for
       exactly why consent/purpose/delegation checks are not run).
    4. Convert the already-existing, already-correct
       `AuthorityContext` (ceiling + delegation authority determination
       -- unchanged, not reimplemented here) into an `AuthorityEnvelope`
       via the existing `authority_context_to_envelope()` adapter.
    5. Wrap both in an `AuthorityGrant` via `build_authority_grant()`.

    Raises `UnrepresentableConstraintError` (propagated from
    `authority_context_to_envelope()`) if `authority_context.
    constraints` contains a key the Heart's lattice has no dimension
    for (e.g. `memory_scope`) -- a hard failure, not a silently
    narrowed grant, per constitutional law H10.
    """
    root = await resolve_root_for_identity(
        identity, root_repo, issuer=issuer, verification_method=verification_method
    )
    prefetched = await prefetch_root_chain(root, root_repo)
    resolver = _sync_resolver_from_prefetch(prefetched)

    legitimacy = sovereignty_evaluate(
        agent.organization_id or "",
        identity.identity_id,
        root=root,
        root_resolver=resolver,
        requested_action_types=frozenset({action.action_type}),
    )

    effective_authority = authority_context_to_envelope(authority_context)

    return build_authority_grant(
        organization_id=agent.organization_id or "",
        principal_id=identity.identity_id,
        acting_agent_id=agent.agent_id,
        requested_action_type=action.action_type,
        requested_target=action.target,
        effective_authority=effective_authority,
        legitimacy=legitimacy,
        root_reference=root.root_id,
    )
