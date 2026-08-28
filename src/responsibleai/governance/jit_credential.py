# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""JIT Credential Broker (Authority Everywhere Phase 10) — the step
between "an `ExecutionAuthorization` says this action may run" and "the
executor actually holds a credential for the destination."

**What this honestly is, and is not.** The target architecture's own
language ("mint narrowly scoped, time-boxed credentials") can read like
this module performs OAuth token exchange or asks an upstream server to
issue a new, narrower-scoped token. It does not, and — for a
third-party MCP server this platform doesn't operate — usually cannot:
most upstream servers have no delegation/token-exchange protocol for a
caller to request a scoped-down credential on demand. What this module
*does* do, honestly: it takes the standing credential an org already
configured for a registered `UpstreamServer`
(`governance/upstream.py`'s `auth_token`, encrypted at rest) and
mediates *access* to it — no executor gets to read `server.auth_token`
directly anymore (see `governance/upstream_executor.py`'s `execute()`).
Instead, it must ask this module for a `JITCredential` bound to one
specific, already-validated `ExecutionAuthorization`, good for a short
window, usable exactly once, with every issuance recorded to an audit
trail (`db/credential_issuance_repository.py`) independent of whether
the call that used it succeeded. That is real, meaningful narrowing —
"held indefinitely by whatever code path can reach the DB row" becomes
"issued once, per permit, and logged" — even though the underlying
secret value itself is unchanged. If a future upstream server supports
real token exchange, this is the module that would grow that capability
without changing any caller.

**Why this is a separate module from `governance/execution.py`,** not
another field on `ExecutionAuthorization` the way Phase 9's
`target_fingerprint` was: an `ExecutionAuthorization` answers "may this
action run at all," a `JITCredential` answers "here is what to
authenticate the network call with, once" — different lifetimes (a
credential's window can be shorter than the permit's, never longer),
different consumption points (the permit is consumed the instant
execution starts; the credential is consumed only once the outbound
call is actually about to fire), and different audit needs (only
credential issuance needs a persisted trail — the permit itself is
already covered by `EvidenceRecord`).

**Deliberately not cryptographically signed**, for the identical reason
`ExecutionAuthorization` isn't (see that module's docstring): this
object never crosses a process boundary, is constructed and consumed
within the same async call stack, and an attacker with the ability to
forge an in-process Python object already has arbitrary code execution
in this process.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from responsibleai.governance.execution import ExecutionAuthorization

if TYPE_CHECKING:
    from responsibleai.governance.upstream import UpstreamServer

# A JIT credential's own window is intentionally short and independent
# of the permit's TTL -- see issue_jit_credential()'s min() below for
# why a credential can never outlive the authorization that produced
# it, only ever expire sooner.
DEFAULT_CREDENTIAL_TTL_SECONDS = 15


class CredentialNotIssuableError(Exception):
    """Base class for every reason `issue_jit_credential()` refuses to
    mint a credential — mirrors `execution.ExecutionNotAuthorizedError`'s
    shape so callers that only care "was this refused" can catch this
    instead of enumerating every subclass."""


class AuthorizationNotYetValidatedError(CredentialNotIssuableError):
    """`issue_jit_credential()` was called with an authorization that
    is already consumed or expired — a credential must never be issued
    against a permit that is not itself still good, since the
    credential's own trust rests entirely on the permit's validity."""

    def __init__(self, authorization_id: str) -> None:
        self.authorization_id = authorization_id
        super().__init__(
            f"ExecutionAuthorization {authorization_id!r} is consumed or expired; "
            "refusing to issue a credential against it."
        )


class CredentialAlreadyConsumedError(Exception):
    """Replay protection — the same `JITCredential` presented to
    `consume_jit_credential()` twice."""

    def __init__(self, credential_id: str) -> None:
        self.credential_id = credential_id
        super().__init__(f"JITCredential {credential_id!r} was already consumed.")


class CredentialExpiredError(Exception):
    def __init__(self, credential_id: str) -> None:
        self.credential_id = credential_id
        super().__init__(f"JITCredential {credential_id!r} has expired.")


@dataclass
class JITCredential:
    """One single-use, time-boxed grant of an upstream server's standing
    credential, bound to exactly one `ExecutionAuthorization`. `token`
    is the actual secret value — held only in memory for the lifetime
    of this object, never logged, never persisted (the audit trail in
    `db/credential_issuance_repository.py` records that this credential
    was issued and when, never the value itself)."""

    credential_id: str
    authorization_id: str
    server_id: str
    org_id: str | None
    token: str | None
    issued_at: datetime
    expires_at: datetime
    consumed: bool = False

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at


def issue_jit_credential(
    authorization: ExecutionAuthorization,
    server_id: str,
    server: UpstreamServer,
    *,
    ttl_seconds: int = DEFAULT_CREDENTIAL_TTL_SECONDS,
) -> JITCredential:
    """Mint a `JITCredential` bound to *authorization* and the resolved
    *server*. *server_id* is taken as its own parameter (not read off
    *server*) since the caller (`UpstreamMCPExecutor.execute()`) already
    has it from `parse_upstream_target()` — the same reasoning
    `compute_upstream_target_fingerprint()` gives for leaving
    `server_id` out of the fingerprint itself.

    Raises `AuthorizationNotYetValidatedError` if *authorization* is
    already consumed or expired — callers must run
    `governance.execution._validate_authorization()` (and, for upstream
    targets, `check_target_fingerprint()`) first; this function does
    not repeat those checks, it only refuses to issue against an
    authorization already known to be bad.

    The credential's own `expires_at` is `min(authorization.expires_at,
    now + ttl_seconds)` — it can never outlive the permit that produced
    it, only ever expire sooner. `token=None` when *server* has no
    standing credential configured (a legitimately unauthenticated
    upstream server) — callers treat that as "proceed without a bearer
    token," not as an error.
    """
    if authorization.consumed or authorization.is_expired:
        raise AuthorizationNotYetValidatedError(authorization.authorization_id)

    now = datetime.now(UTC)
    expires_at = min(authorization.expires_at, now + timedelta(seconds=ttl_seconds))

    return JITCredential(
        credential_id=str(uuid.uuid4()),
        authorization_id=authorization.authorization_id,
        server_id=server_id,
        org_id=server.org_id,
        token=server.auth_token,
        issued_at=now,
        expires_at=expires_at,
    )


def consume_jit_credential(credential: JITCredential) -> str | None:
    """The one place a `JITCredential`'s `token` is ever read for actual
    use — validates single-use and expiry, marks it consumed, and
    returns the token (or `None` for an unauthenticated server). A
    second call on the same credential raises
    `CredentialAlreadyConsumedError` rather than silently returning the
    cached value again."""
    if credential.consumed:
        raise CredentialAlreadyConsumedError(credential.credential_id)
    if credential.is_expired:
        raise CredentialExpiredError(credential.credential_id)
    credential.consumed = True
    return credential.token
