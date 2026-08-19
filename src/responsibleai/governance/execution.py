"""Decision -> execution binding and the executor abstraction — closes
the gap the WhitePact v3 authority-layer review flagged as the highest
priority after the approval-mutation fix: nothing previously stopped a
caller from running `dispatch_tool()` directly, bypassing whatever
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
    """

    action_digest: str
    organization_id: str | None
    decision: GovernanceDecision
    authorization_id: str = field(default_factory=lambda: str(uuid.uuid4()))
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
    """
    if decision.decision not in (GovernanceDecision.ALLOW, GovernanceDecision.ALLOW_WITH_REDACTION):
        raise DecisionNotExecutableError(decision.decision)

    return ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id=action.agent.organization_id,
        decision=decision.decision,
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
    four checks."""
    if authorization.consumed:
        raise AuthorizationAlreadyConsumedError(authorization.authorization_id)
    if authorization.is_expired:
        raise AuthorizationExpiredError(authorization.authorization_id)
    if authorization.organization_id != action.agent.organization_id:
        raise AuthorizationOrganizationMismatchError(authorization.authorization_id)
    if not authorization.matches_action(action):
        raise AuthorizationActionMismatchError(authorization.authorization_id)


class InternalToolExecutor:
    """Executes one of this platform's own 27 MCP tools
    (`mcp.tools.dispatch_tool`) — the only executor that exists today.
    Named to match the v3 spec's own suggested name for this exact
    case (Section 28 lists `InternalToolExecutor` alongside the
    not-yet-built `MCPExecutor`/`HTTPExecutor` for proxying to
    *external* systems).
    """

    async def execute(self, authorization: ExecutionAuthorization, action: ActionRequest) -> Any:
        _validate_authorization(authorization, action)
        authorization.consumed = (
            True  # single-use — a second call now hits AuthorizationAlreadyConsumedError
        )

        from responsibleai.mcp.tools import dispatch_tool

        return await dispatch_tool(action.action_type, action.arguments)
