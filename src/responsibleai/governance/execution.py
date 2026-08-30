"""Decision -> execution binding and the executor abstraction — closes
the gap the WhitePact v3 authority-layer review flagged as the highest
priority after the approval-mutation fix: nothing previously stopped a
caller from running `_dispatch_tool_unchecked()` directly, bypassing whatever
`WhitePactRuntimeGateway.evaluate()` actually decided. That direct-call
path still exists (see `THREAT_MODEL.md`'s "governance gateway is a
chosen integration point, not an unbypassable boundary" entry — this
module doesn't change that for arbitrary Python callers), but the one
path this platform itself controls — `mcp/server.py`'s dispatch of its
own 27 tools — is wired through `InternalToolExecutor` below, which
structurally cannot execute without a matching, unexpired, single-use
`ExecutionAuthorization`.

**Deliberately not cryptographically signed.** `ExecutionAuthorization`
is a structural binding (digest + org + expiry + single-use consumed
flag), not an HMAC-signed token. This is the audited, correct call as
long as the object never crosses a trust boundary — the gateway
constructs it and `InternalToolExecutor.execute()` consumes it within
the same async call stack, in the same process, never serialized or
sent over a network. Signing it would add real complexity (key
management, verification, clock-skew handling) for a threat model that
doesn't exist yet — an attacker able to forge an in-process Python
object already has arbitrary code execution in this process, at which
point HMAC verification protects nothing. If a future executor lives
in a separate process/service (a real `MCPExecutor` proxying to a
different host, per the v3 spec's Section 28), *that* is exactly when
signing becomes load-bearing, and this module says so rather than
signing prematurely — see the module docstring's own "do not invent
cryptography" instruction from the v3 spec review.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from responsibleai.governance.approval import compute_action_digest
from responsibleai.governance.models import ActionRequest, DecisionResult, GovernanceDecision

DEFAULT_AUTHORIZATION_TTL_SECONDS = 30


class ExecutionNotAuthorizedError(Exception):
    """Base class for every reason `Executor.execute()` refuses to run
    an action — callers that only care "was this refused" can catch
    this instead of enumerating every subclass."""


class DecisionNotExecutableError(ExecutionNotAuthorizedError):
    """`authorize_execution()` was called with a decision that isn't
    ALLOW/ALLOW_WITH_REDACTION — DENY, QUARANTINE, and REQUIRE_APPROVAL
    never produce an `ExecutionAuthorization` at all; there is nothing
    for an executor to consume."""

    def __init__(self, decision: GovernanceDecision) -> None:
        self.decision = decision
        super().__init__(f"GovernanceDecision.{decision.value} does not authorize execution.")


class AuthorizationExpiredError(ExecutionNotAuthorizedError):
    def __init__(self, authorization_id: str) -> None:
        self.authorization_id = authorization_id
        super().__init__(f"ExecutionAuthorization {authorization_id!r} has expired.")


class AuthorizationAlreadyConsumedError(ExecutionNotAuthorizedError):
    """Replay protection — the same authorization presented twice."""

    def __init__(self, authorization_id: str) -> None:
        self.authorization_id = authorization_id
        super().__init__(f"ExecutionAuthorization {authorization_id!r} was already consumed.")


class AuthorizationActionMismatchError(ExecutionNotAuthorizedError):
    """The mutation invariant for direct (non-approval) execution: the
    action presented to the executor is not byte-identical to the one
    the gateway authorized — same shape as
    `db.approval_repository.ApprovalActionMismatchError`, for the
    ALLOW/ALLOW_WITH_REDACTION path rather than the REQUIRE_APPROVAL
    path."""

    def __init__(self, authorization_id: str) -> None:
        self.authorization_id = authorization_id
        super().__init__(
            f"ExecutionAuthorization {authorization_id!r} does not match the action "
            "presented for execution."
        )


class AuthorizationOrganizationMismatchError(ExecutionNotAuthorizedError):
    def __init__(self, authorization_id: str) -> None:
        self.authorization_id = authorization_id
        super().__init__(
            f"ExecutionAuthorization {authorization_id!r} belongs to a different organization."
        )


class AuthorizationTargetDriftError(ExecutionNotAuthorizedError):
    """Execution Permit v2 (Authority Everywhere Phase 9): the resolved
    identity of *where this action actually goes* has changed since the
    decision was made. ``action_digest`` binds to the action's own
    shape (agent, action_type, target string, arguments) but never
    captured anything about what a target *string* like
    ``server_id::tool_name`` currently resolves to -- an upstream
    server's URL, enabled state, or credential can change between
    decision time and execution time without the action digest moving
    at all, since ``UpstreamServer.server_id`` stays the same. A permit
    that was granted against one resolved target must not silently
    authorize execution against a different one that now sits behind
    the same target string."""

    def __init__(self, authorization_id: str) -> None:
        self.authorization_id = authorization_id
        super().__init__(
            f"ExecutionAuthorization {authorization_id!r} was granted against a different "
            "resolved target than the one now being executed against (target configuration "
            "drifted between authorization and execution)."
        )


@dataclass
class ExecutionAuthorization:
    """What `authorize_execution()` hands an executor — the structural
    proof that a specific action was actually decided ALLOW or
    ALLOW_WITH_REDACTION, for this exact action, this exact org, within
    a short validity window, and not yet spent.

    `nonce` exists even though nothing currently transmits this object
    anywhere — it's the field that would matter first if a future
    executor did cross a process boundary and this got signed; keeping
    it here now means that change doesn't require touching every
    caller's field list later.

    `target_fingerprint` is Execution Permit v2 (Authority Everywhere
    Phase 9): an optional, executor-supplied hash of whatever the
    action's target string currently resolves to — `None` for executors
    with no external resolution step (`InternalToolExecutor`: the
    action_type *is* the identity, already fully covered by
    `action_digest`). When set, `execute()` must recompute the same
    fingerprint from the target as it exists *right now* and refuse to
    run on any mismatch — see `AuthorizationTargetDriftError`.

    **Enterprise Readiness Phase 3 fields** (`consent_reference`,
    `policy_version`, `heart_legitimacy_digest`, `execution_id`):
    audit/provenance binding, not independently re-validated against a
    "current" value the way `target_fingerprint` is. Unlike a resolved
    upstream target (genuinely external, mutable state that can drift
    between decision and execution), a decision's policy version and
    the consent/legitimacy verdict that produced it are properties of
    the decision itself, computed once, a few lines before
    `authorize_execution()` is called — there is no meaningful "current"
    value to recompute and compare at `execute()` time the way there is
    for a target. Their purpose is completeness of what an
    `EvidenceRecord` can bind to (see `PHASE2_EXECUTION_BOUNDARY_
    ARCHITECTURE.md`'s reasoning for why this stays structural, not
    signed): recording exactly which consent, which policy version, and
    which Heart verdict digest authorized an action, not just the
    action's own shape.

    `revocation_epoch` is deliberately left `None` with no field to
    populate it from yet — `resolve_authority_grant()` does not query
    `RevocationEpochRepository` at grant time (that wiring doesn't
    exist; see `docs/enterprise-readiness/00_MASTER_READINESS_AUDIT.md`'s
    Purpose binding row). This class does not fabricate a value for it.

    `purpose` (Enterprise Readiness Phase 5) is populated by
    `authorize_execution()`'s `purpose` parameter, which callers pass
    as `grant.requested_purpose` — the VALIDATED purpose
    `resolve_authority_grant()` confirmed against consent/policy, never
    the raw, unvalidated `action.purpose`. It participates in
    `compute_action_digest()` (see `governance/approval.py`), so a
    mutated purpose invalidates the authorization the same way a
    mutated argument does — this is the digest-binding mechanism that
    proves authorization(purpose=A) cannot execute as purpose=B.
    """

    action_digest: str
    organization_id: str | None
    decision: GovernanceDecision
    target_fingerprint: str | None = None
    consent_reference: str | None = None
    policy_version: int | None = None
    heart_legitimacy_digest: str | None = None
    revocation_epoch: int | None = None
    purpose: str | None = None
    authorization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    nonce: str = field(default_factory=lambda: uuid.uuid4().hex)
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(
        default_factory=lambda: (
            datetime.now(UTC) + timedelta(seconds=DEFAULT_AUTHORIZATION_TTL_SECONDS)
        )
    )
    consumed: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    def matches_action(self, action: ActionRequest) -> bool:
        return self.action_digest == compute_action_digest(action)


def authorize_execution(
    decision: DecisionResult,
    action: ActionRequest,
    *,
    ttl_seconds: int = DEFAULT_AUTHORIZATION_TTL_SECONDS,
    target_fingerprint: str | None = None,
    consent_reference: str | None = None,
    heart_legitimacy_digest: str | None = None,
    purpose: str | None = None,
) -> ExecutionAuthorization:
    """Turn a gateway decision into an `ExecutionAuthorization` — the
    only place one is ever constructed. Raises `DecisionNotExecutableError`
    for anything other than ALLOW/ALLOW_WITH_REDACTION; DENY/QUARANTINE
    end the flow with nothing to authorize, and REQUIRE_APPROVAL's
    binding is `db.approval_repository.ApprovalRepository.consume()`,
    not this function — that path resolves asynchronously, potentially
    long after the original `ActionRequest` object is gone, which is
    exactly why it needs its own persisted binding (`action_digest` on
    `ApprovalRequest`) rather than a short-lived in-memory object like
    this one.

    *action* must already reflect what will actually execute — for
    `ALLOW_WITH_REDACTION`, that means the caller passes an `ActionRequest`
    built from `decision.redacted_arguments`, not the original
    arguments, so the digest binds to what the executor will really run.

    *target_fingerprint* is Execution Permit v2 (Phase 9) — pass it when
    the caller already resolved the action's target to something
    concrete (e.g. `upstream_executor.compute_upstream_target_fingerprint()`
    for an `UpstreamServer`) at decision time, so `execute()` can detect
    drift between that resolution and what the target resolves to when
    the permit is actually consumed. Leave `None` when there's nothing
    to resolve (internal tools).

    *consent_reference*/*heart_legitimacy_digest* (Enterprise Readiness
    Phase 3) — pass `grant.consent_reference`/`grant.legitimacy.
    canonical_digest` when the caller resolved a real `AuthorityGrant`
    (i.e. `enterprise_mode` + Heart wiring was on for this call); leave
    `None` otherwise, honestly reflecting that no Heart verdict backs
    this authorization. `decision.policy_version` is read directly from
    *decision* — always available, no separate parameter needed.

    *purpose* (Enterprise Readiness Phase 5) — pass `grant.
    requested_purpose` when a consent-backed grant validated one; leave
    `None` otherwise. Callers must never pass the raw, unvalidated
    `action.purpose` here — only a value `resolve_authority_grant()`
    already confirmed compatible gets bound into the authorization.
    """
    if decision.decision not in (GovernanceDecision.ALLOW, GovernanceDecision.ALLOW_WITH_REDACTION):
        raise DecisionNotExecutableError(decision.decision)

    return ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id=action.agent.organization_id,
        decision=decision.decision,
        target_fingerprint=target_fingerprint,
        consent_reference=consent_reference,
        policy_version=decision.policy_version,
        heart_legitimacy_digest=heart_legitimacy_digest,
        purpose=purpose,
        expires_at=datetime.now(UTC) + timedelta(seconds=ttl_seconds),
    )


class Executor(Protocol):
    """What every concrete executor implements. `execute()` must not
    run *action* without first validating *authorization* — see
    `InternalToolExecutor` for the reference implementation of that
    validation; a future `MCPExecutor`/`HTTPExecutor` (v3 spec Section
    28, not built yet) would perform the identical checks before doing
    whatever's specific to that transport."""

    async def execute(
        self, authorization: ExecutionAuthorization, action: ActionRequest
    ) -> Any: ...


def _validate_authorization(authorization: ExecutionAuthorization, action: ActionRequest) -> None:
    """Shared validation every `Executor.execute()` implementation
    must run first — pulled out as its own function so a future
    executor can't accidentally reimplement (and get wrong) the same
    four checks. Deliberately does not check `target_fingerprint` (see
    `check_target_fingerprint()`) — that check needs the *current*
    resolved target, which an executor can only produce after it has
    already looked the target up, and this function's four checks must
    still run (and take precedence) even when that lookup hasn't
    happened yet."""
    if authorization.consumed:
        raise AuthorizationAlreadyConsumedError(authorization.authorization_id)
    if authorization.is_expired:
        raise AuthorizationExpiredError(authorization.authorization_id)
    if authorization.organization_id != action.agent.organization_id:
        raise AuthorizationOrganizationMismatchError(authorization.authorization_id)
    if not authorization.matches_action(action):
        raise AuthorizationActionMismatchError(authorization.authorization_id)


class NonceConsumer(Protocol):
    """Enterprise Readiness Phase 4 (replay protection) -- the durable
    consume-once seam, structurally typed rather than importing
    `db.execution_nonce_repository.ExecutionNonceRepository` directly:
    `governance/` stays free of a compile-time dependency on `db/`, the
    same TCB-minimization discipline `root_authority.py`'s
    `RootResolver` Protocol and `crypto/provider.py`'s `KeyProvider`
    Protocol already establish for every other Heart/execution seam in
    this codebase. `ExecutionNonceRepository` satisfies this Protocol
    by construction (duck typing), no explicit registration needed."""

    async def consume(self, nonce: str, *, authorization_id: str, organization_id: str) -> None: ...


async def consume_nonce_durably(
    authorization: ExecutionAuthorization, nonce_consumer: NonceConsumer | None
) -> None:
    """The opt-in durability layer for replay protection. A complete
    no-op when `nonce_consumer` is `None` -- the in-memory `consumed`
    flag `_validate_authorization()` already checks is unaffected
    either way and keeps stopping same-process replay unconditionally;
    this only adds protection across a process restart or a second
    instance, matching `RevocationEpochRepository`'s own "cache is an
    optimization, durable store is authority" precedent.

    Raises `AuthorizationAlreadyConsumedError` -- the SAME error the
    in-memory check raises -- if the durable store reports this nonce
    already spent, so a caller never needs to distinguish which layer
    caught the replay. Local import (matches this module's own
    `InternalToolExecutor.execute()` convention below) to keep
    `governance/` layered below `db/`, not coupled to it at module-
    import time.
    """
    if nonce_consumer is None:
        return
    from responsibleai.db.execution_nonce_repository import NonceAlreadyConsumedError

    try:
        await nonce_consumer.consume(
            authorization.nonce,
            authorization_id=authorization.authorization_id,
            organization_id=authorization.organization_id or "",
        )
    except NonceAlreadyConsumedError as exc:
        raise AuthorizationAlreadyConsumedError(authorization.authorization_id) from exc


def check_target_fingerprint(
    authorization: ExecutionAuthorization, current_target_fingerprint: str | None
) -> None:
    """Execution Permit v2's drift check — call this *after*
    `_validate_authorization()` has already passed and *after* the
    executor has resolved *action.target* to something concrete (e.g.
    an `UpstreamServer`). Skipped entirely when
    `authorization.target_fingerprint is None` (nothing was resolved at
    decision time — `InternalToolExecutor`'s case), so an executor that
    never sets a fingerprint never needs to call this at all."""
    if authorization.target_fingerprint is None:
        return
    if authorization.target_fingerprint != current_target_fingerprint:
        raise AuthorizationTargetDriftError(authorization.authorization_id)


class InternalToolExecutor:
    """Executes one of this platform's own 27 MCP tools
    (`mcp.tools._dispatch_tool_unchecked`) — the only executor that exists today.
    Named to match the v3 spec's own suggested name for this exact
    case (Section 28 lists `InternalToolExecutor` alongside the
    not-yet-built `MCPExecutor`/`HTTPExecutor` for proxying to
    *external* systems).

    `nonce_repo` defaults `None` (no durable replay protection, just
    the in-memory `consumed` flag below). **Construct this fresh per
    call** — `apply_governance()`/`resume_approval()`
    (`mcp/governance_integration.py`) both do — rather than sharing one
    long-lived instance across calls or processes: an earlier version
    of this class was a module-level singleton reconfigured via a
    setter after the fact, which leaked one app's durable-repo
    reference into a later, independently-constructed app in the same
    process (caught by this branch's own test suite, not shipped).
    `UpstreamMCPExecutor` (`governance/upstream_executor.py`) already
    followed this same per-call-construction convention; this class now
    matches it.
    """

    def __init__(self, nonce_repo: NonceConsumer | None = None) -> None:
        self.nonce_repo = nonce_repo

    async def execute(self, authorization: ExecutionAuthorization, action: ActionRequest) -> Any:
        _validate_authorization(authorization, action)
        await consume_nonce_durably(authorization, self.nonce_repo)
        authorization.consumed = (
            True  # single-use — a second call now hits AuthorizationAlreadyConsumedError
        )

        from responsibleai.mcp.tools import _dispatch_tool_unchecked

        return await _dispatch_tool_unchecked(action.action_type, action.arguments)
