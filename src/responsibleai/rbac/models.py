# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""RBAC domain models — Organizations, API keys, roles, audit entries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    VIEWER = "VIEWER"


class Plan(StrEnum):
    """Billing tier — gates which MCP tools and API endpoints an org can use."""

    FREE = "FREE"
    PRO = "PRO"
    ENTERPRISE = "ENTERPRISE"


PLAN_RANK: dict[Plan, int] = {
    Plan.FREE: 0,
    Plan.PRO: 1,
    Plan.ENTERPRISE: 2,
}

ACTIVE_LIKE_STATUSES: frozenset[str] = frozenset({"active", "trialing"})
RESTRICTIVE_STATUSES: frozenset[str] = frozenset(
    {"canceled", "paused", "past_due", "inactive", "dissolved"}
)


def get_plan_rank(plan: Plan | str) -> int:
    """Return the integer rank for a Plan (FREE < PRO < ENTERPRISE)."""
    if isinstance(plan, Plan):
        return PLAN_RANK.get(plan, 0)
    try:
        return PLAN_RANK.get(Plan(str(plan).upper()), 0)
    except (ValueError, KeyError):
        return 0


def is_equal_timestamp_transition_allowed(
    current_plan: Plan | str,
    current_status: str,
    incoming_plan: Plan | str,
    incoming_status: str,
) -> bool:
    """Evaluate whether an entitlement update with equal occurred_at is permissible.

    Equal occurred_at timestamps represent ambiguous provider chronology. Under WhitePact's
    zero-trust commercial invariant, equal timestamp events must NEVER widen commercial entitlement:
    1. Upward plan elevation (e.g. FREE -> PRO, PRO -> ENTERPRISE) is strictly rejected.
    2. Restrictive -> active-like status transitions (e.g. canceled -> active) are strictly rejected.
    3. Idempotent same-state events (same plan and status) and downward narrowing transitions are permitted.
    """
    c_rank = get_plan_rank(current_plan)
    i_rank = get_plan_rank(incoming_plan)

    # 1. Reject upward plan elevation (widening)
    if i_rank > c_rank:
        return False

    c_norm_status = (current_status or "inactive").casefold()
    i_norm_status = (incoming_status or "inactive").casefold()

    c_active = c_norm_status in ACTIVE_LIKE_STATUSES
    i_active = i_norm_status in ACTIVE_LIKE_STATUSES

    # 2. Reject restrictive -> active-like reactivation
    if not c_active and i_active:
        return False

    # 3. Non-widening transition (downward plan, same plan, narrowing status, or idempotent)
    return True


@dataclass
class Organization:
    name: str
    slug: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    monthly_budget_usd: float = 10_000.0
    created_at: str = ""
    plan: Plan = Plan.FREE
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None
    paddle_customer_id: str | None = None
    paddle_subscription_id: str | None = None
    entitlement_version: int = 0
    entitlement_updated_at: str | None = None
    paddle_last_occurred_at: str | None = None
    plan_renews_at: str | None = None
    subscription_status: str = "inactive"
    sso_required: bool = False
    mfa_required: bool = False
    # Internal bootstrap-ownership binding. Never serialized to clients.
    provisioner_key_id: str | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "monthly_budget_usd": self.monthly_budget_usd,
            "created_at": self.created_at,
            "plan": self.plan.value if isinstance(self.plan, Plan) else self.plan,
            "stripe_customer_id": self.stripe_customer_id,
            "paddle_customer_id": self.paddle_customer_id,
            "plan_renews_at": self.plan_renews_at,
            "subscription_status": self.subscription_status,
            "entitlement_version": self.entitlement_version,
            "entitlement_updated_at": self.entitlement_updated_at,
            "sso_required": self.sso_required,
            "mfa_required": self.mfa_required,
        }


@dataclass
class OrgApiKey:
    org_id: str
    name: str
    role: Role
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = ""
    last_used_at: str | None = None
    revoked: bool = False
    mfa_enrolled: bool = False
    # Carried in-process between repo <-> app layer for enroll/verify only —
    # deliberately excluded from to_dict() so it's never serialized to a
    # response body, same discipline as the raw API key itself.
    mfa_secret: str | None = field(default=None, repr=False)
    mfa_backup_codes: list[str] | None = field(default=None, repr=False)
    prefix: str = "rai_"
    environment: str = "legacy"
    scopes: tuple[str, ...] = ()
    expires_at: str | None = None
    rotated_from_id: str | None = None

    def to_dict(self, include_key: str | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "org_id": self.org_id,
            "name": self.name,
            "role": self.role.value,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "revoked": self.revoked,
            "mfa_enrolled": self.mfa_enrolled,
            "prefix": self.prefix,
            "environment": self.environment,
            "scopes": list(self.scopes),
            "expires_at": self.expires_at,
        }
        if include_key is not None:
            d["key"] = include_key  # Only set on key creation; never stored
        return d


@dataclass
class OrgContext:
    """Auth context injected into every authenticated request via Depends."""

    key_id: str
    role: Role
    org_id: str | None = None
    org_name: str | None = None
    key_name: str | None = None
    mfa_enrolled: bool = False
    is_legacy: bool = False  # True for flat RAI_API_KEYS entries
    plan: Plan = Plan.ENTERPRISE  # legacy/anon keys default to unrestricted for backward compat
    scopes: frozenset[str] = frozenset()
    # Set only by the credential verifier that constructed this context.
    # Downstream governance records it as authentication evidence; it never
    # becomes an authority grant.
    authentication_method: str = "api_key"


@dataclass
class AuditEntry:
    endpoint: str
    method: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = ""
    org_id: str | None = None
    key_id: str | None = None
    status_code: int | None = None
    ip_address: str | None = None
    request_id: str | None = None
    duration_ms: float | None = None
    user_agent: str | None = None
    entry_hash: str | None = None
    prev_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "org_id": self.org_id,
            "key_id": self.key_id,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "ip_address": self.ip_address,
            "request_id": self.request_id,
            "duration_ms": self.duration_ms,
            "user_agent": self.user_agent,
            "entry_hash": self.entry_hash,
            "prev_hash": self.prev_hash,
        }
