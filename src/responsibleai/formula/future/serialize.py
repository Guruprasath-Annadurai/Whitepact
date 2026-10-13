# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import json
from typing import Any

from responsibleai.formula.capability.closure import CapabilityClosureResult
from responsibleai.formula.capability.serialize import serialize_closure_result
from responsibleai.formula.future.envelope import SafeFutureEnvelope
from responsibleai.formula.future.facts import ConsequenceFact
from responsibleai.formula.future.provenance import CausalDerivation
from responsibleai.formula.future.rules import CausalRule
from responsibleai.formula.serialization import canonical_encode


def closure_fingerprint(closure: CapabilityClosureResult) -> str:
    payload = serialize_closure_result(closure)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def causal_rules_fingerprint(rules: tuple[CausalRule, ...]) -> str:
    encoded = [
        {
            "rule_id": r.rule_id,
            "tenant_id": r.tenant_id,
            "family": r.family.value,
            "prerequisite_patterns": list(r.prerequisite_patterns),
            "output_kind": r.output_kind.value,
            "output_subject_id": r.output_subject_id,
            "output_target_id": r.output_target_id,
            "output_scope": r.output_scope,
            "reversibility": r.reversibility.value,
            "epistemic_status": r.epistemic_status.value,
            "graph_edge_id": r.graph_edge_id,
            "capability_action": r.capability_action,
            "capability_target_node_id": r.capability_target_node_id,
            "recovery_rule": r.recovery_rule,
            "persistence": r.persistence,
            "information_sensitive": r.information_sensitive,
        }
        for r in sorted(rules, key=lambda x: x.rule_id)
    ]
    blob = json.dumps(canonical_encode(encoded), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()


def serialize_consequence_fact(f: ConsequenceFact) -> dict[str, Any]:
    return {
        "tenant_id": f.tenant_id,
        "subject_id": f.subject_id,
        "target_id": f.target_id,
        "consequence_kind": f.consequence_kind.value,
        "scope": f.scope,
        "reversibility": f.reversibility.value,
        "persistence": f.persistence,
        "information_sensitive": f.information_sensitive,
        "epistemic_status": f.epistemic_status.value,
        "reachability": f.reachability.value,
        "magnitude_class": f.magnitude_class,
    }


def serialize_derivation(d: CausalDerivation) -> dict[str, Any]:
    return {
        "rule_id": d.rule_id,
        "output_key": list(d.output_key),
        "prerequisite_keys": [list(k) for k in d.prerequisite_keys],
        "prerequisite_witness_fingerprints": [
            list(fp) for fp in d.prerequisite_witness_fingerprints
        ],
        "graph_edge_ids": list(d.graph_edge_ids),
        "trajectory_depth": d.trajectory_depth,
        "causal_depth": d.causal_depth,
        "epistemic_status": d.epistemic_status.value,
        "reversibility": d.reversibility.value,
        "information_sensitive": d.information_sensitive,
        "subject_id": d.subject_id,
        "persistence": d.persistence,
        "capability_semantic_key": list(d.capability_semantic_key)
        if d.capability_semantic_key
        else None,
    }


def serialize_envelope(envelope: SafeFutureEnvelope) -> dict[str, Any]:
    return canonical_encode(
        {
            "tenant_id": envelope.tenant_id,
            "snapshot_id": envelope.snapshot_id,
            "graph_content_hash": envelope.graph_content_hash,
            "capability_closure_fingerprint": envelope.capability_closure_fingerprint,
            "capability_closure_status": envelope.capability_closure_status,
            "capability_unresolved_notes": list(envelope.capability_unresolved_notes),
            "causal_rules_fingerprint": envelope.causal_rules_fingerprint,
            "budget": {
                "max_horizon_steps": envelope.budget.max_horizon_steps,
                "max_states": envelope.budget.max_states,
                "max_consequences": envelope.budget.max_consequences,
                "max_derivations": envelope.budget.max_derivations,
                "max_rule_applications": envelope.budget.max_rule_applications,
                "max_trajectories": envelope.budget.max_trajectories,
                "max_frontier": envelope.budget.max_frontier,
                "max_path_depth": envelope.budget.max_path_depth,
            },
            "blast_radius": {
                "affected_actors": sorted(envelope.blast_radius.affected_actors),
                "affected_resources": sorted(envelope.blast_radius.affected_resources),
                "affected_systems": sorted(envelope.blast_radius.affected_systems),
                "affected_data_objects": sorted(envelope.blast_radius.affected_data_objects),
                "external_targets": sorted(envelope.blast_radius.external_targets),
                "propagation_depth": envelope.blast_radius.propagation_depth,
            },
            "horizon": envelope.horizon,
            "status": envelope.status.value,
            "consequence_facts": [
                serialize_consequence_fact(f) for f in envelope.consequence_facts
            ],
            "causal_derivations": [serialize_derivation(d) for d in envelope.causal_derivations],
            "reachable_states": [
                {"step": s.step, "active_keys": [list(k) for k in sorted(s.active_keys)]}
                for s in envelope.reachable_states
            ],
            "blocked_frontier": list(envelope.blocked_frontier),
            "budget_usage": envelope.budget_usage,
            "epistemic_summary": envelope.epistemic_summary.value,
            "schema_version": envelope.schema_version,
        }
    )


def compute_envelope_hash(envelope: SafeFutureEnvelope) -> str:
    payload = serialize_envelope(envelope)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode()).hexdigest()
