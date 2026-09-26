# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.epistemic_compose import compose_epistemic
from responsibleai.formula.capability.rules import RuleId
from responsibleai.formula.errors import InvalidCapability
from responsibleai.formula.graph.snapshot import GraphSnapshot


def validate_closure_provenance(
    snapshot: GraphSnapshot,
    result: CapabilityClosureResult,
) -> None:
    """Validate witness DAG integrity (acyclic, consistent depth, tenant-homogeneous)."""
    node_ids = {n.node_id for n in snapshot.nodes}
    edge_ids = {e.edge_id for e in snapshot.edges}
    fact_keys = {f.semantic_key() for f in result.facts}
    by_output: dict[tuple, CapabilityDerivation] = {}
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
        if w.rule_id != RuleId.SEED:
            for prereq in w.prerequisite_keys:
                if prereq not in fact_keys:
                    raise InvalidCapability("prerequisite capability missing")
        if w.rule_id != RuleId.SEED and w.prerequisite_keys:
            premise_statuses: list = []
            for prereq in w.prerequisite_keys:
                for other in result.derivations:
                    if other.output_semantic_key == prereq:
                        premise_statuses.append(other.epistemic_status)
                        break
                else:
                    for f in result.facts:
                        if f.semantic_key() == prereq:
                            premise_statuses.append(f.epistemic_status)
                            break
            expected = compose_epistemic(*premise_statuses)
            if expected != w.epistemic_status:
                raise InvalidCapability("witness epistemic exceeds premises")
        by_output.setdefault(w.output_semantic_key, w)

    visiting: set[tuple] = set()
    visited: set[tuple] = set()

    def dfs(key: tuple) -> None:
        if key in visiting:
            raise InvalidCapability("cyclic provenance dependency")
        if key in visited:
            return
        visiting.add(key)
        for w in result.derivations:
            if w.output_semantic_key != key:
                continue
            for prereq in w.prerequisite_keys:
                dfs(prereq)
        visiting.remove(key)
        visited.add(key)

    for f in result.facts:
        dfs(f.semantic_key())
