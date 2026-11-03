"""Single-use local execution authorizations with expiry and replay protection.

Community Core keeps authorizations in-process. Cryptographic signing of
cross-host permits is an enterprise capability and is explicitly unavailable
here — not simulated.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from whitepact_community.errors import AuthorizationError, CommunityCapabilityUnavailable
from whitepact_community.models import ActionRequest, DecisionResult, GovernanceDecision
from whitepact_community.reason_codes import ReasonCode, format_reason

DEFAULT_AUTHORIZATION_TTL_SECONDS = 30


def compute_action_digest(action: ActionRequest) -> str:
    material = {
        "action_type": action.action_type,
        "target": action.target,
        "arguments": action.arguments,
        "agent_id": action.agent_id,
        "identity_id": action.identity.identity_id,
        "action_id": action.action_id,
    }
    blob = json.dumps(material, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(blob).hexdigest()


@dataclass
class ExecutionAuthorization:
    authorization_id: str
    action_digest: str
    decision: GovernanceDecision
    organization_id: str | None
    expires_at: datetime
    consumed: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "authorization_id": self.authorization_id,
            "action_digest": self.action_digest,
            "decision": self.decision.value,
            "organization_id": self.organization_id,
            "expires_at": self.expires_at.isoformat(),
            "consumed": self.consumed,
            "created_at": self.created_at.isoformat(),
        }


class AuthorizationStore:
    def __init__(self) -> None:
        self._items: dict[str, ExecutionAuthorization] = {}

    def put(self, auth: ExecutionAuthorization) -> ExecutionAuthorization:
        self._items[auth.authorization_id] = auth
        return auth

    def get(self, authorization_id: str) -> ExecutionAuthorization | None:
        return self._items.get(authorization_id)


def authorize_execution(
    action: ActionRequest,
    decision: DecisionResult,
    *,
    organization_id: str | None = None,
    ttl_seconds: int = DEFAULT_AUTHORIZATION_TTL_SECONDS,
    store: AuthorizationStore | None = None,
    now: datetime | None = None,
) -> ExecutionAuthorization:
    if decision.decision not in {
        GovernanceDecision.ALLOW,
        GovernanceDecision.ALLOW_WITH_REDACTION,
    }:
        raise AuthorizationError(
            f"GovernanceDecision.{decision.decision.value} does not authorize execution."
        )
    clock = now or datetime.now(UTC)
    auth = ExecutionAuthorization(
        authorization_id=str(uuid.uuid4()),
        action_digest=compute_action_digest(action),
        decision=decision.decision,
        organization_id=organization_id,
        expires_at=clock + timedelta(seconds=ttl_seconds),
        created_at=clock,
    )
    if store is not None:
        store.put(auth)
    return auth


def consume_authorization(
    auth: ExecutionAuthorization,
    action: ActionRequest,
    *,
    now: datetime | None = None,
) -> ExecutionAuthorization:
    clock = now or datetime.now(UTC)
    if auth.consumed:
        raise AuthorizationError(
            format_reason(ReasonCode.AUTHORIZATION_REPLAY, authorization_id=auth.authorization_id)
        )
    expires = auth.expires_at
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    if clock >= expires:
        raise AuthorizationError(
            format_reason(
                ReasonCode.AUTHORIZATION_EXPIRED, authorization_id=auth.authorization_id
            )
        )
    digest = compute_action_digest(action)
    if digest != auth.action_digest:
        raise AuthorizationError(
            format_reason(
                ReasonCode.AUTHORIZATION_MISMATCH, authorization_id=auth.authorization_id
            )
        )
    auth.consumed = True
    return auth


def require_signed_cross_host_permit() -> None:
    """Enterprise-only capability — fail closed, never simulate success."""
    raise CommunityCapabilityUnavailable(
        "signed_cross_host_execution_permit",
        "Cross-host HMAC/Ed25519 execution permits require enterprise infrastructure.",
    )
