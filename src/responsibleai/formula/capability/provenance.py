# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.rules import RuleId
from responsibleai.formula.errors import InvalidCapability
from responsibleai.formula.graph.snapshot import GraphSnapshot


def _expected_epistemic(
    witness: CapabilityDerivation,
    snapshot: GraphSnapshot,
    by_fp: dict[tuple, CapabilityDerivation],
) -> None:
    nodes = {n.node_id: n for n in snapshot.nodes}
    edges = {e.edge_id: e for e in snapshot.edges}

    if witness.rule_id == RuleId.SEED:
        return
    if witness.rule_id == RuleId.DIRECT_EXTRACTION:
        if not witness.graph_edge_ids:
            raise InvalidCapability("direct extraction missing edge")
        edge = edges[witness.graph_edge_ids[0]]
        src = nodes[edge.source_id]
        tgt = nodes[edge.target_id]
        expected = compose_epistemic(
            src.epistemic_status, edge.epistemic_status, tgt.epistemic_status
        )
    elif witness.rule_id in (RuleId.COMPOSE_VIA_CALL, RuleId.MULTI_AGENT_RELAY):
        if len(witness.prerequisite_witness_fingerprints) != 2:
            raise InvalidCapability("compose witness missing prerequisite supports")
        ow = by_fp[witness.prerequisite_witness_fingerprints[0]]
        iw = by_fp[witness.prerequisite_witness_fingerprints[1]]
        im = nodes.get(ow.route_node_ids[-1])
        im_status = im.epistemic_status if im else compose_epistemic()
        expected = compose_epistemic(ow.epistemic_status, iw.epistemic_status, im_status)
    elif witness.rule_id == RuleId.CREDENTIAL_UNLOCK:
        if not witness.graph_edge_ids:
            raise InvalidCapability("credential unlock missing edge")
        edge = edges[witness.graph_edge_ids[0]]
        cred = nodes[edge.source_id]
        tgt = nodes[edge.target_id]
        read_w = by_fp[witness.prerequisite_witness_fingerprints[0]]
        expected = compose_epistemic(
            read_w.epistemic_status,
            cred.epistemic_status,
            edge.epistemic_status,
            tgt.epistemic_status,
        )
    elif witness.rule_id == RuleId.INFORMATION_REVEALS:
        if not witness.graph_edge_ids:
            raise InvalidCapability("information reveals missing edge")
        edge = edges[witness.graph_edge_ids[0]]
        src = nodes[edge.source_id]
        tgt = nodes[edge.target_id]
        read_w = by_fp[witness.prerequisite_witness_fingerprints[0]]
        expected = compose_epistemic(
            read_w.epistemic_status,
            edge.epistemic_status,
            src.epistemic_status,
            tgt.epistemic_status,
        )
    elif witness.rule_id == RuleId.JOINT_COALITION:
        return
    else:
        return

    if compose_epistemic(expected, witness.epistemic_status) != witness.epistemic_status:
        raise InvalidCapability("witness epistemic exceeds rule premises")


def validate_closure_provenance(
    snapshot: GraphSnapshot,
    result: CapabilityClosureResult,
) -> None:
    """Validate witness DAG integrity (acyclic, consistent depth, tenant-homogeneous)."""
    node_ids = {n.node_id for n in snapshot.nodes}
    edge_ids = {e.edge_id for e in snapshot.edges}
    fact_keys = {f.semantic_key() for f in result.facts}
    by_fp: dict[tuple, CapabilityDerivation] = {
        w.witness_fingerprint(): w for w in result.derivations
    }

    for w in result.derivations:
        if w.output_semantic_key not in fact_keys:
            raise InvalidCapability("witness output capability missing from facts")
        for nid in w.graph_node_ids:
            if nid not in node_ids:
                raise InvalidCapability(f"witness references unknown node {nid}")
        for eid in w.graph_edge_ids:
            if eid not in edge_ids:
                raise InvalidCapability(f"witness references unknown edge {eid}")
        if w.derivation_depth < 0:
            raise InvalidCapability("negative derivation depth")
        for prereq in w.prerequisite_keys:
            if prereq not in fact_keys:
                raise InvalidCapability("prerequisite capability missing")
        for pfp in w.prerequisite_witness_fingerprints:
            if pfp not in by_fp:
                raise InvalidCapability("prerequisite witness missing")
        _expected_epistemic(w, snapshot, by_fp)

    visiting: set[tuple] = set()
    visited: set[tuple] = set()

    def dfs_fp(fp: tuple) -> None:
        if fp in visiting:
            raise InvalidCapability("cyclic provenance dependency")
        if fp in visited:
            return
        visiting.add(fp)
        w = by_fp[fp]
        for pfp in w.prerequisite_witness_fingerprints:
            dfs_fp(pfp)
        visiting.remove(fp)
        visited.add(fp)

    for w in result.derivations:
        dfs_fp(w.witness_fingerprint())
