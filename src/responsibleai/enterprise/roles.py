# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical enterprise RBAC permission matrix.

Administrative authorization only. Possession of any permission here
never manufactures WhitePact execution authority.
"""

from __future__ import annotations

from enum import StrEnum

from responsibleai.rbac.models import Role


class Permission(StrEnum):
    ORG_VIEW = "org.view"
    ORG_UPDATE_SETTINGS = "org.update_settings"
    ORG_DEACTIVATE = "org.deactivate"
    ORG_TRANSFER_OWNERSHIP = "org.transfer_ownership"
    MEMBERS_INVITE = "members.invite"
    MEMBERS_UPDATE_ROLE = "members.update_role"
    MEMBERS_REVOKE = "members.revoke"
    ENV_READ = "environments.read"
    ENV_WRITE = "environments.write"
    API_KEYS_READ = "api_keys.read"
    API_KEYS_CREATE = "api_keys.create"
    API_KEYS_ROTATE = "api_keys.rotate"
    API_KEYS_REVOKE = "api_keys.revoke"
    SA_READ = "service_accounts.read"
    SA_CREATE = "service_accounts.create"
    SA_UPDATE = "service_accounts.update"
    SA_REVOKE = "service_accounts.revoke"
    CREDENTIALS_EMERGENCY_REVOKE = "credentials.emergency_revoke"
    EVIDENCE_READ = "evidence.read"
    AUDIT_READ = "audit.read"
    APPROVALS_READ = "approvals.read"
    APPROVALS_WRITE = "approvals.write"
    BILLING_MANAGE = "billing.manage"
    SESSIONS_READ = "sessions.read"
    SESSIONS_REVOKE = "sessions.revoke"
    VERIFICATION_READ = "verification.read"
    VERIFICATION_MANAGE = "verification.manage"
    USAGE_READ = "usage.read"


# Keep ANALYST as the historical eval/read role. New enterprise names sit
# beside it; they are not aliases that rewrite stored ANALYST rows.
_OWNER = frozenset(Permission)
_ADMIN = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.ORG_UPDATE_SETTINGS,
        Permission.MEMBERS_INVITE,
        Permission.MEMBERS_UPDATE_ROLE,
        Permission.MEMBERS_REVOKE,
        Permission.ENV_READ,
        Permission.ENV_WRITE,
        Permission.API_KEYS_READ,
        Permission.API_KEYS_CREATE,
        Permission.API_KEYS_ROTATE,
        Permission.API_KEYS_REVOKE,
        Permission.SA_READ,
        Permission.SA_CREATE,
        Permission.SA_UPDATE,
        Permission.SA_REVOKE,
        Permission.SESSIONS_READ,
        Permission.VERIFICATION_READ,
        Permission.USAGE_READ,
        Permission.APPROVALS_READ,
        Permission.AUDIT_READ,
        Permission.EVIDENCE_READ,
    }
)
_SECURITY_ADMIN = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.ENV_READ,
        Permission.API_KEYS_READ,
        Permission.API_KEYS_REVOKE,
        Permission.API_KEYS_ROTATE,
        Permission.SA_READ,
        Permission.SA_REVOKE,
        Permission.SA_UPDATE,
        Permission.CREDENTIALS_EMERGENCY_REVOKE,
        Permission.SESSIONS_READ,
        Permission.SESSIONS_REVOKE,
        Permission.VERIFICATION_READ,
        Permission.VERIFICATION_MANAGE,
        Permission.AUDIT_READ,
        Permission.EVIDENCE_READ,
        Permission.MEMBERS_REVOKE,
    }
)
_APPROVER = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.APPROVALS_READ,
        Permission.APPROVALS_WRITE,
    }
)
_DEVELOPER = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.ENV_READ,
        Permission.API_KEYS_READ,
        Permission.API_KEYS_CREATE,
        Permission.API_KEYS_ROTATE,
        Permission.USAGE_READ,
    }
)
_ANALYST = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.ENV_READ,
        Permission.API_KEYS_READ,
        Permission.EVIDENCE_READ,
        Permission.USAGE_READ,
        Permission.AUDIT_READ,
    }
)
_AUDITOR = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.ENV_READ,
        Permission.API_KEYS_READ,
        Permission.SA_READ,
        Permission.EVIDENCE_READ,
        Permission.AUDIT_READ,
        Permission.VERIFICATION_READ,
        Permission.USAGE_READ,
        Permission.SESSIONS_READ,
    }
)
_BILLING = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.BILLING_MANAGE,
        Permission.USAGE_READ,
    }
)
_VIEWER = frozenset(
    {
        Permission.ORG_VIEW,
        Permission.ENV_READ,
    }
)

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.OWNER: _OWNER,
    Role.ADMIN: _ADMIN,
    Role.SECURITY_ADMIN: _SECURITY_ADMIN,
    Role.APPROVER: _APPROVER,
    Role.DEVELOPER: _DEVELOPER,
    Role.ANALYST: _ANALYST,
    Role.AUDITOR: _AUDITOR,
    Role.BILLING_ADMIN: _BILLING,
    Role.VIEWER: _VIEWER,
}

CANONICAL_SCOPES: frozenset[str] = frozenset(
    {
        "governance:read",
        "governance:execute",
        "evidence:read",
        "approvals:read",
        "approvals:write",
        "connections:read",
        "connections:write",
        "usage:read",
        "agents:read",
        "agents:write",
        "governance:write",
    }
)

# Role rank for privilege-escalation comparisons (service-account creation).
# OWNER is never grantable to machine identities.
_ROLE_PRIVILEGE: dict[Role, int] = {
    Role.OWNER: 100,
    Role.ADMIN: 80,
    Role.SECURITY_ADMIN: 70,
    Role.DEVELOPER: 40,
    Role.ANALYST: 30,
    Role.APPROVER: 25,
    Role.AUDITOR: 20,
    Role.BILLING_ADMIN: 20,
    Role.VIEWER: 10,
}


def has_rbac_permission(role: Role | str | None, permission: Permission) -> bool:
    if role is None:
        return False
    try:
        resolved = role if isinstance(role, Role) else Role(str(role).upper())
    except ValueError:
        return False
    return permission in ROLE_PERMISSIONS.get(resolved, frozenset())


def role_privilege(role: Role | str) -> int:
    try:
        resolved = role if isinstance(role, Role) else Role(str(role).upper())
    except ValueError:
        return 0
    return _ROLE_PRIVILEGE.get(resolved, 0)
