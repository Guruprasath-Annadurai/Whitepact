# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Effective authority derived from canonical delegation + ceiling truth."""

from __future__ import annotations

from pydantic import BaseModel, Field

from responsibleai.sovereign.sources import SovereignCanonicalStore


class EffectiveAuthoritySnapshot(BaseModel):
    organization_id: str
    environment: str
    capability_ids: list[str] = Field(default_factory=list)
    delegation_identity_ids: list[str] = Field(default_factory=list)
    require_approval_for: list[str] = Field(default_factory=list)
    policy_version: int | None = None
    governance_epoch: int | None = None
    provenance: list[str] = Field(default_factory=list)
    unknown_fields: list[str] = Field(default_factory=list)


async def load_effective_authority(
    store: SovereignCanonicalStore,
    organization_id: str,
    *,
    environment: str = "development",
) -> EffectiveAuthoritySnapshot:
    caps: set[str] = set()
    identities: set[str] = set()
    approval_actions: set[str] = set()
    provenance: list[str] = []

    graph = await store.delegations.get_org_graph(organization_id)
    for root in graph.roots:
        _walk_delegation_node(root, caps, identities, approval_actions)
    if caps:
        provenance.append("delegation_repository.get_org_graph")

    ceiling = await store.ceilings.get(organization_id)
    if ceiling is not None and ceiling.allowed_action_types:
        allowed = set(ceiling.allowed_action_types)
        caps &= allowed
        provenance.append("org_authority_ceiling_repository.get")
        approval_actions.update(ceiling.require_approval_for)

    policy_version = await store.policies.get_policy_version(organization_id)
    provenance.append("policy_repository.get_policy_version")

    epoch_row = await store.revocation_epochs.current(organization_id)
    epoch_val = epoch_row.epoch
    unknown: list[str] = []
    provenance.append("revocation_epoch_repository.current")

    return EffectiveAuthoritySnapshot(
        organization_id=organization_id,
        environment=environment,
        capability_ids=sorted(caps),
        delegation_identity_ids=sorted(identities),
        require_approval_for=sorted(approval_actions),
        policy_version=policy_version,
        governance_epoch=epoch_val,
        provenance=provenance,
        unknown_fields=unknown,
    )


def _walk_delegation_node(
    node, caps: set[str], identities: set[str], approval_actions: set[str]
) -> None:
    identities.add(node.identity_id)
    if node.delegation is not None and node.delegation.is_active():
        caps.update(node.delegation.granted_action_types)
        approval_actions.update(node.delegation.require_approval_for)
    for child in node.children:
        _walk_delegation_node(child, caps, identities, approval_actions)
