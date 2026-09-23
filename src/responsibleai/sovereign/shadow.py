# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Shadow evaluation — non-authoritative, zero persisted execution truth."""

from __future__ import annotations

from pydantic import BaseModel, Field

from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
)
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.zero_effect import zero_effect_operation


class ShadowObservation(BaseModel):
    non_authoritative: bool = True
    organization_id: str
    decision: str
    reason_codes: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


@zero_effect_operation
def evaluate_shadow(
    ctx: SovereignContext,
    *,
    agent_id: str,
    action_type: str,
    target: str = "shadow:target",
    granted_action_types: frozenset[str] | None = None,
) -> ShadowObservation:
    """Runs gateway evaluation in-process only — does not persist evidence or execute."""
    identity = IdentityContext(identity_id=agent_id, kind="agent", org_id=ctx.organization_id)
    agent = AgentContext(identity=identity, organization_id=ctx.organization_id, agent_id=agent_id)
    action = ActionRequest(
        agent=agent,
        action_type=action_type,
        target=target,
        arguments={},
        purpose="sovereign-shadow",
    )
    authority = AuthorityContext(
        delegated_by=agent_id,
        granted_action_types=granted_action_types or frozenset({action_type}),
    )
    result = WhitePactRuntimeGateway().evaluate(action, authority)
    return ShadowObservation(
        organization_id=ctx.organization_id,
        decision=result.decision.value,
        reason_codes=[str(c) for c in result.reason_codes],
        notes=["Shadow observation is not authorization and is not persisted as execution truth"],
    )
