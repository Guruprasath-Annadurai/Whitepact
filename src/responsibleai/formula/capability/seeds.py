# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.capability.rules import RuleId
from responsibleai.formula.capability.state import CapabilityClosureState
from responsibleai.formula.errors import CapabilityTenantMismatch, InvalidCapability
from responsibleai.formula.graph.snapshot import GraphSnapshot


def validate_and_ingest_seeds(
    snapshot: GraphSnapshot,
    seeds: tuple[CapabilityFact, ...],
    state: CapabilityClosureState,
) -> None:
    node_ids = {n.node_id for n in snapshot.nodes}
    for seed in sorted(seeds, key=lambda s: (s.semantic_key(), s.epistemic_status.value)):
        if seed.tenant_id != snapshot.tenant_id:
            raise CapabilityTenantMismatch("seed tenant mismatch")
        seed.actor.assert_tenant(snapshot.tenant_id)
        if seed.target_node_id not in node_ids:
            raise InvalidCapability(f"seed target {seed.target_node_id} not in snapshot")
        for member in seed.actor.member_ids:
            if member not in node_ids:
                raise InvalidCapability(f"seed actor {member} not in snapshot")
        witness = CapabilityDerivation(
            rule_id=RuleId.SEED,
            output_semantic_key=seed.semantic_key(),
            prerequisite_keys=(),
            graph_node_ids=(seed.actor.member_ids[0], seed.target_node_id),
            graph_edge_ids=(),
            epistemic_status=seed.epistemic_status,
            derivation_depth=1,
            route_node_ids=(seed.actor.member_ids[0], seed.target_node_id),
        )
        state.add_witness(seed, witness, is_direct=seed.is_direct)
        # duplicate semantic seeds merge epistemic via state.add_witness
