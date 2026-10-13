# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Immutable admin grant claims (mutable lifecycle lives in PostgreSQL)."""

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

MAX_ADMIN_GRANT_TTL_SECONDS = 14_400  # 4 hours — hard ceiling for JIT admin grants


class GrantDecision(StrEnum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    PENDING = "PENDING"


@dataclass(frozen=True)
class AdminGrantClaim:
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

    def to_canonical_bytes(self) -> bytes:
        payload = asdict(self)
        payload["expires_at"] = self.expires_at.isoformat()
        payload["issued_at"] = self.issued_at.isoformat()
        payload["role"] = str(self.role)
        payload["approval_decision"] = str(self.approval_decision)
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


# Backward-compatible alias for in-memory tests
AdminExecutionGrant = AdminGrantClaim


def _sign(claim: AdminGrantClaim, signing_key: bytes) -> str:
    return hmac.new(signing_key, claim.to_canonical_bytes(), hashlib.sha256).hexdigest()


def verify_claim_signature(claim: AdminGrantClaim, signature: str, signing_key: bytes) -> bool:
    expected = _sign(claim, signing_key)
    return hmac.compare_digest(expected, signature)


def issue_admin_grant_claim(
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
) -> tuple[AdminGrantClaim, str]:
    if ttl_seconds <= 0 or ttl_seconds > MAX_ADMIN_GRANT_TTL_SECONDS:
        raise ValueError(f"ttl_seconds must be 1..{MAX_ADMIN_GRANT_TTL_SECONDS}")

    for perm in permissions:
        if not role_allows(role, perm):
            raise PermissionError(f"role {role} cannot receive permission {perm}")

    if approval != GrantDecision.APPROVED:
        raise ValueError("only APPROVED grants may be issued")

    sensitive = any(is_sensitive_permission(p) for p in permissions)
    if sensitive and approved_by is None and not founder_only_exception:
        raise ValueError("sensitive operations require approved_by or documented founder exception")

    now = datetime.now(UTC)
    claim = AdminGrantClaim(
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
    return claim, _sign(claim, signing_key)


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
) -> tuple[AdminGrantClaim, str]:
    return issue_admin_grant_claim(
        employee_id=employee_id,
        role=role,
        operation=operation,
        provider=provider,
        resource_target=resource_target,
        permissions=permissions,
        policy_id=policy_id,
        approval=approval,
        approved_by=approved_by,
        ttl_seconds=ttl_seconds,
        signing_key=signing_key,
        audit_correlation_id=audit_correlation_id,
        founder_only_exception=founder_only_exception,
    )


def verify_admin_grant(
    grant: AdminGrantClaim,
    signature: str,
    signing_key: bytes,
    *,
    expected_operation: str | None = None,
    now: datetime | None = None,
    revoked: bool = False,
    consumed: bool = False,
) -> dict[str, Any]:
    """In-memory verification only — production must use AdminGrantService + PostgreSQL."""
    now = now or datetime.now(UTC)
    if revoked:
        return {"ok": False, "reason": "revoked"}
    if consumed:
        return {"ok": False, "reason": "replay"}
    if now >= grant.expires_at:
        return {"ok": False, "reason": "expired"}
    if not verify_claim_signature(grant, signature, signing_key):
        return {"ok": False, "reason": "bad_signature"}
    if expected_operation is not None and grant.operation != expected_operation:
        return {"ok": False, "reason": "operation_mismatch"}
    return {"ok": True, "grant_id": grant.grant_id, "execution_id": grant.execution_id}
