# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Short-lived administrative execution grants (JIT), bound to employee identity."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from responsibleai.whitepact_cloud.roles import CloudRole, is_sensitive_permission, role_allows


class GrantDecision(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    PENDING = "PENDING"


@dataclass(frozen=True)
class AdminExecutionGrant:
    grant_id: str
    employee_id: str
    role: CloudRole
    operation: str
    provider: str
    resource_target: str
    permissions: tuple[str, ...]
    policy_id: str
    approval_decision: GrantDecision
    approved_by: str | None
    expires_at: datetime
    execution_id: str
    audit_correlation_id: str
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    revoked: bool = False
    consumed: bool = False

    def to_canonical_bytes(self) -> bytes:
        payload = asdict(self)
        payload["expires_at"] = self.expires_at.isoformat()
        payload["issued_at"] = self.issued_at.isoformat()
        payload["role"] = str(self.role)
        payload["approval_decision"] = str(self.approval_decision)
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign(grant: AdminExecutionGrant, signing_key: bytes) -> str:
    digest = hmac.new(signing_key, grant.to_canonical_bytes(), hashlib.sha256).hexdigest()
    return digest


def issue_admin_grant(
    *,
    employee_id: str,
    role: CloudRole,
    operation: str,
    provider: str,
    resource_target: str,
    permissions: list[str],
    policy_id: str,
    approval: GrantDecision,
    approved_by: str | None,
    ttl_seconds: int,
    signing_key: bytes,
    audit_correlation_id: str | None = None,
    founder_only_exception: bool = False,
) -> tuple[AdminExecutionGrant, str]:
    """Mint a constrained grant. Founder-only stage may self-approve with explicit flag."""
    for perm in permissions:
        if not role_allows(role, perm):
            raise PermissionError(f"role {role} cannot receive permission {perm}")

    if approval != GrantDecision.APPROVED:
        raise ValueError("only APPROVED grants may be issued")

    if is_sensitive_permission(permissions[0]) if len(permissions) == 1 else any(
        is_sensitive_permission(p) for p in permissions
    ):
        if approved_by is None and not founder_only_exception:
            raise ValueError("sensitive operations require approved_by or documented founder exception")

    now = datetime.now(UTC)
    grant = AdminExecutionGrant(
        grant_id=str(uuid.uuid4()),
        employee_id=employee_id,
        role=role,
        operation=operation,
        provider=provider,
        resource_target=resource_target,
        permissions=tuple(permissions),
        policy_id=policy_id,
        approval_decision=approval,
        approved_by=approved_by,
        expires_at=now + timedelta(seconds=ttl_seconds),
        execution_id=secrets.token_hex(16),
        audit_correlation_id=audit_correlation_id or str(uuid.uuid4()),
    )
    return grant, _sign(grant, signing_key)


def verify_admin_grant(
    grant: AdminExecutionGrant,
    signature: str,
    signing_key: bytes,
    *,
    expected_operation: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify grant integrity, expiry, and revocation before provider automation runs."""
    now = now or datetime.now(UTC)
    if grant.revoked:
        return {"ok": False, "reason": "revoked"}
    if grant.consumed:
        return {"ok": False, "reason": "replay"}
    if now >= grant.expires_at:
        return {"ok": False, "reason": "expired"}
    expected_sig = _sign(grant, signing_key)
    if not hmac.compare_digest(expected_sig, signature):
        return {"ok": False, "reason": "bad_signature"}
    if expected_operation is not None and grant.operation != expected_operation:
        return {"ok": False, "reason": "operation_mismatch"}
    return {"ok": True, "grant_id": grant.grant_id, "execution_id": grant.execution_id}


def revoke_grant(grant: AdminExecutionGrant) -> AdminExecutionGrant:
    return AdminExecutionGrant(**{**asdict(grant), "revoked": True})


def consume_grant(grant: AdminExecutionGrant) -> AdminExecutionGrant:
    return AdminExecutionGrant(**{**asdict(grant), "consumed": True})
