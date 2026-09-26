# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.derivation import CapabilityDerivation
from responsibleai.formula.capability.facts import CapabilityFact
from responsibleai.formula.serialization import canonical_encode


def serialize_capability_fact(fact: CapabilityFact) -> dict[str, Any]:
    return {
        "tenant_id": fact.tenant_id,
        "actor_members": list(fact.actor.member_ids),
        "action": fact.action,
        "target_node_id": fact.target_node_id,
        "kind": fact.kind.value,
        "epistemic_status": fact.epistemic_status.value,
        "is_direct": fact.is_direct,
    }


def serialize_derivation(d: CapabilityDerivation) -> dict[str, Any]:
    return {
        "rule_id": d.rule_id,
        "output_semantic_key": list(d.output_semantic_key),
        "prerequisite_keys": [list(k) for k in d.prerequisite_keys],
        "prerequisite_witness_fingerprints": [
            list(fp) for fp in d.prerequisite_witness_fingerprints
        ],
        "graph_node_ids": list(d.graph_node_ids),
        "graph_edge_ids": list(d.graph_edge_ids),
        "epistemic_status": d.epistemic_status.value,
        "derivation_depth": d.derivation_depth,
        "route_node_ids": list(d.route_node_ids),
        "support_kind": d.support_kind.value,
        "support_is_direct": d.support_is_direct,
    }


def serialize_closure_result(result: CapabilityClosureResult) -> dict[str, Any]:
    return canonical_encode(
        {
            "tenant_id": result.tenant_id,
            "graph_version_number": result.graph_version_number,
            "graph_content_hash": result.graph_content_hash,
            "status": result.status.value,
            "iterations": result.iterations,
            "rule_applications": result.rule_applications,
            "budget": {
                "max_iterations": result.budget.max_iterations,
                "max_facts": result.budget.max_facts,
                "max_derivations": result.budget.max_derivations,
                "max_rule_applications": result.budget.max_rule_applications,
                "max_path_depth": result.budget.max_path_depth,
            },
            "facts": [serialize_capability_fact(f) for f in result.facts],
            "derivations": [serialize_derivation(d) for d in result.derivations],
            "unresolved_notes": list(result.unresolved_notes),
            "schema_version": result.schema_version,
        }
    )
