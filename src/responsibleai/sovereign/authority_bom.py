# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authority bill of materials — inventory, not certification."""

from __future__ import annotations

from pydantic import BaseModel, Field

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.effective import load_effective_authority
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation


class AuthorityBOM(BaseModel):
    organization_id: str
    capabilities: list[str] = Field(default_factory=list)
    delegation_identity_ids: list[str] = Field(default_factory=list)
    policy_version: int | None = None
    approval_dependencies: list[str] = Field(default_factory=list)
    notes: list[str] = Field(
        default_factory=lambda: ["Inventory only — not a certification or grant"]
    )


@zero_effect_operation
async def build_authority_bom(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
) -> AuthorityBOM:
    effective = await load_effective_authority(
        store, ctx.organization_id, environment=ctx.environment
    )
    graph = await store.delegations.get_org_graph(ctx.organization_id)
    identities: set[str] = set()

    def walk(node) -> None:
        identities.add(node.identity_id)
        for child in node.children:
            walk(child)

    for root in graph.roots:
        walk(root)
    policy = await store.policies.get_policy(ctx.organization_id)
    return AuthorityBOM(
        organization_id=ctx.organization_id,
        capabilities=sorted(effective.capability_ids),
        delegation_identity_ids=sorted(identities),
        policy_version=policy.version,
        approval_dependencies=sorted(effective.require_approval_for),
    )
