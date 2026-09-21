# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM Core Domain Models."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from responsibleai.iam.enums import (
    BreakGlassCapability,
    FourEyesStatus,
    JitGrantStatus,
    PrivilegedAction,
    PrivilegeRiskTier,
    StepUpMethod,
)
from responsibleai.rbac.models import Role


def canonical_hash(data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of dictionary."""
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass
class StepUpProof:
    """Proof of fresh reauthentication presented with a privileged request."""

    nonce: str
    method: StepUpMethod
    auth_time: str
    token_or_code: str
    user_agent: str | None = None
    ip_address: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)


@dataclass
class PrivilegedCallerContext:
    """Context of the principal invoking a privileged control-plane operation."""

    principal_id: str
    org_id: str
    role: Role
    is_root: bool = False
    is_platform_operator: bool = False
    session_id: str | None = None
    credential_id: str | None = None
    credential_epoch: int = 0
    active_jit_grants: list[str] = field(default_factory=list)


@dataclass
class PrivilegedAuthorizationResult:
    """Outcome of evaluating a privileged operation against the surface guard."""

    allowed: bool
    risk_tier: PrivilegeRiskTier
    action: PrivilegedAction
    principal_id: str
    org_id: str
    evaluation_time: str
    audit_hash: str
    reason: str | None = None
    step_up_verified: bool = False
    four_eyes_verified: bool = False
    break_glass_active: bool = False


@dataclass
class JitGrant:
    """Time-bounded, capability-scoped Just-In-Time access grant."""

    id: str = field(default_factory=lambda: f"jit_{uuid.uuid4().hex}")
    org_id: str = ""
    principal_id: str = ""
    target_role: Role = Role.ADMIN
    allowed_actions: list[PrivilegedAction] = field(default_factory=list)
    justification: str = ""
    status: JitGrantStatus = JitGrantStatus.REQUESTED
    requested_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    approved_at: str | None = None
    approver_principal_id: str | None = None
    expires_at: str = ""
    revoked_at: str | None = None


@dataclass
class FourEyesRequest:
    """Dual-custody request requiring independent approval before execution."""

    id: str = field(default_factory=lambda: f"fe_{uuid.uuid4().hex}")
    org_id: str = ""
    requester_principal_id: str = ""
    action: PrivilegedAction = PrivilegedAction.MODIFY_POLICY_RULE
    target_resource_id: str | None = None
    parameters_json: str = "{}"
    request_digest: str = ""
    status: FourEyesStatus = FourEyesStatus.PENDING
    approver_principal_id: str | None = None
    approval_time: str | None = None
    rejection_reason: str | None = None
    executed_at: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str = ""


@dataclass
class BreakGlassSession:
    """Emergency privileged session bound to an active operational incident."""

    id: str = field(default_factory=lambda: f"bg_{uuid.uuid4().hex}")
    org_id: str = ""
    principal_id: str = ""
    incident_id: str = ""
    capabilities: list[BreakGlassCapability] = field(default_factory=list)
    justification: str = ""
    status: str = "ACTIVE"
    started_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    expires_at: str = ""
    terminated_at: str | None = None


@dataclass
class SovereignRecoveryPolicy:
    """Customer-held N-of-M guardian configuration for sovereign root recovery."""

    id: str = field(default_factory=lambda: f"rec_pol_{uuid.uuid4().hex}")
    org_id: str = ""
    threshold: int = 2
    guardians: list[dict[str, str]] = field(
        default_factory=list
    )  # list of {"name": str, "public_key": str}
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    active: bool = True
