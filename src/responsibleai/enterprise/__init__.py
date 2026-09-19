# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise SaaS Layer 1 — administrative identity and access control.

This package never grants WhitePact execution authority.
"""

from __future__ import annotations

from responsibleai.enterprise.roles import Permission, ROLE_PERMISSIONS, has_rbac_permission
from responsibleai.enterprise.service import Actor, EnterpriseIAM

__all__ = [
    "Actor",
    "EnterpriseIAM",
    "Permission",
    "ROLE_PERMISSIONS",
    "has_rbac_permission",
]
