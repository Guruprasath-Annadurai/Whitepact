# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Resource-level roles for WhitePact Cloud (distinct from org dashboard RBAC)."""

from __future__ import annotations

from enum import StrEnum


class CloudRole(StrEnum):
    OWNER = "OWNER"
    SECURITY_ADMIN = "SECURITY_ADMIN"
    PLATFORM_ENGINEER = "PLATFORM_ENGINEER"
    DEVELOPER = "DEVELOPER"
    SECURITY_AUDITOR = "SECURITY_AUDITOR"
    BACKUP_OPERATOR = "BACKUP_OPERATOR"


# Permission strings are enforced at grant issue time and re-checked at execution.
_ROLE_PERMISSIONS: dict[CloudRole, frozenset[str]] = {
    CloudRole.OWNER: frozenset({"*"}),
    CloudRole.SECURITY_ADMIN: frozenset(
        {
            "cloud.iam.read",
            "cloud.iam.write",
            "cloud.firewall.write",
            "cloud.audit.read",
            "cloud.monitoring.write",
            "cloud.secrets.rotate",
            "cloud.admin.grant.approve",
        }
    ),
    CloudRole.PLATFORM_ENGINEER: frozenset(
        {
            "cloud.infra.read",
            "cloud.infra.write",
            "cloud.deploy.write",
            "cloud.dns.read",
            "cloud.admin.grant.request",
        }
    ),
    CloudRole.DEVELOPER: frozenset(
        {
            "cloud.infra.read",
            "cloud.staging.write",
            "cloud.admin.grant.request",
        }
    ),
    CloudRole.SECURITY_AUDITOR: frozenset({"cloud.audit.read", "cloud.infra.read"}),
    CloudRole.BACKUP_OPERATOR: frozenset(
        {"cloud.backup.write", "cloud.backup.read", "cloud.backup.restore.request"}
    ),
}

_SENSITIVE_PERMISSIONS = frozenset(
    {
        "cloud.iam.write",
        "cloud.firewall.write",
        "cloud.secrets.rotate",
        "cloud.backup.delete",
        "cloud.monitoring.write",
        "cloud.admin.grant.approve",
    }
)


def role_allows(role: CloudRole, permission: str) -> bool:
    perms = _ROLE_PERMISSIONS.get(role, frozenset())
    if "*" in perms:
        return True
    return permission in perms


def is_sensitive_permission(permission: str) -> bool:
    return permission in _SENSITIVE_PERMISSIONS
