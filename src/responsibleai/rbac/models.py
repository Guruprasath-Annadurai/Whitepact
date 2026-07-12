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
    plan_renews_at: str | None = None
    sso_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "monthly_budget_usd": self.monthly_budget_usd,
            "created_at": self.created_at,
            "plan": self.plan.value if isinstance(self.plan, Plan) else self.plan,
            "stripe_customer_id": self.stripe_customer_id,
            "plan_renews_at": self.plan_renews_at,
            "sso_required": self.sso_required,
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

    def to_dict(self, include_key: str | None = None) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id,
            "org_id": self.org_id,
            "name": self.name,
            "role": self.role.value,
            "created_at": self.created_at,
            "last_used_at": self.last_used_at,
            "revoked": self.revoked,
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
    is_legacy: bool = False  # True for flat RAI_API_KEYS entries
    plan: Plan = Plan.ENTERPRISE  # legacy/anon keys default to unrestricted for backward compat


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
