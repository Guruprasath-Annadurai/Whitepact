# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Bind a governed call to a registered agent without granting authority.

The API credential remains the caller. This only selects an active AI agent
principal in that credential's organization. It does not verify agent key
possession, write IDENTITY_VERIFIED, or create an execution grant.
"""

from __future__ import annotations

import re
from dataclasses import replace

from sqlalchemy import select

from responsibleai.db.engine import trust_fabric_principals
from responsibleai.rbac.models import OrgContext
from responsibleai.trust_fabric.enums import PrincipalState, PrincipalType

_AGENT_ID = re.compile(r"agent_[0-9a-f]{12}")


async def admit_registered_agent(connection, auth: OrgContext, agent_id: str | None) -> OrgContext:
    """Return auth unchanged, or the same credential pointed at one tenant agent."""
    if agent_id is None:
        return auth
    if type(agent_id) is not str or _AGENT_ID.fullmatch(agent_id) is None:
        raise ValueError("AGENT_ID_MALFORMED")
    if not auth.org_id or auth.is_legacy:
        raise ValueError("ORG_SCOPED_CREDENTIAL_REQUIRED")
    row = (
        await connection.execute(
            select(
                trust_fabric_principals.c.id,
                trust_fabric_principals.c.display_name,
                trust_fabric_principals.c.lifecycle_state,
            ).where(
                trust_fabric_principals.c.id == agent_id,
                trust_fabric_principals.c.org_id == auth.org_id,
                trust_fabric_principals.c.principal_type == PrincipalType.AI_AGENT.value,
            )
        )
    ).first()
    if row is None or row.lifecycle_state != PrincipalState.ACTIVE.value:
        raise LookupError("AGENT_NOT_ACTIVE_IN_ORGANIZATION")
    return replace(auth, key_id=row.id, key_name=row.display_name or row.id)
