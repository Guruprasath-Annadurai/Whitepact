# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Cloud — internal privileged-access control plane (not customer-facing)."""

from responsibleai.whitepact_cloud.admin_grant import (
    AdminExecutionGrant,
    GrantDecision,
    issue_admin_grant,
    verify_admin_grant,
)
from responsibleai.whitepact_cloud.roles import CloudRole, role_allows

__all__ = [
    "AdminExecutionGrant",
    "CloudRole",
    "GrantDecision",
    "issue_admin_grant",
    "role_allows",
    "verify_admin_grant",
]
