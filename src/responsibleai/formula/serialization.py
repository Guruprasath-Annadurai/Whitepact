# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic canonical serialization and hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from responsibleai.formula.authority.algebra import EffectiveAuthorityEvaluator
from responsibleai.formula.authority.atoms import AuthorityTuple
from responsibleai.formula.authority.models import AuthorityGrant, OrgAuthorityCeilingModel
from responsibleai.formula.graph.snapshot import GraphSnapshot
from responsibleai.formula.trace.trace import FormulaTrace, FormulaTraceEvent


def utc_iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC).isoformat().replace("+00:00", "Z")
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def canonical_encode(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if value != value or value in (float("inf"), float("-inf")):
            raise TypeError("non-finite float in canonical encoding")
        return value
    if isinstance(value, datetime):
        return utc_iso(value)
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, set):
        return sorted(canonical_encode(v) for v in value)
    if isinstance(value, frozenset):
        return sorted(canonical_encode(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [canonical_encode(v) for v in value]
    if isinstance(value, dict):
        return {str(k): canonical_encode(v) for k, v in sorted(value.items())}
    if hasattr(value, "_pairs"):
        return canonical_encode(dict(value._pairs))  # type: ignore[attr-defined]
    if hasattr(value, "_condition_pairs"):
        return canonical_encode(dict(value._condition_pairs))  # type: ignore[attr-defined]
    raise TypeError(f"unsupported canonical type: {type(value)!r}")


def canonical_json_dumps(obj: Any) -> str:
    return json.dumps(
        canonical_encode(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def canonical_sha256(obj: Any) -> str:
    payload = canonical_json_dumps(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _serialize_ceiling(ceiling: OrgAuthorityCeilingModel | None) -> Any:
    if ceiling is None:
        return None
    return canonical_encode(
        {
            "tenant_id": ceiling.tenant_id,
            "org_id": ceiling.org_id,
            "allowed_actions": ceiling.allowed_actions,
            "allowed_resources": ceiling.allowed_resources,
            "max_risk_class": ceiling.max_risk_class,
            "max_delegation_depth": ceiling.max_delegation_depth,
        }
    )


def serialize_grant(grant: AuthorityGrant) -> dict[str, Any]:
    return canonical_encode(
        {
            "grant_id": grant.grant_id,
            "tenant_id": grant.tenant_id,
            "subject": {
                "subject_id": grant.subject.subject_id,
                "tenant_id": grant.subject.tenant_id,
                "kind": grant.subject.kind,
            },
            "issuer_id": grant.issuer_id,
            "delegator_id": grant.delegator_id,
            "actions": grant.actions,
            "resources": grant.resources,
            "purposes": grant.purposes,
            "context": grant.context,
            "not_before": grant.not_before,
            "expires_at": grant.expires_at,
            "risk_ceiling": grant.risk_ceiling,
            "constraints": grant.constraints,
            "lifecycle": grant.lifecycle,
            "evidence_ref": grant.evidence_ref,
            "epistemic_status": grant.epistemic_status,
            "schema_version": grant.schema_version,
            "version": grant.version,
        }
    )


def _serialize_trace_event(e: FormulaTraceEvent) -> dict[str, Any]:
    return {
        "event_id": e.event_id,
        "tenant_id": e.tenant_id,
        "subject_id": e.subject_id,
        "action": e.action,
        "resource": e.resource,
        "timestamp": e.timestamp,
        "graph_version": e.graph_version,
        "policy_version": e.policy_version,
        "grant_refs": e.grant_refs,
        "evidence_refs": e.evidence_refs,
        "transition_class": e.transition_class,
        "before_state_hash": e.before_state_hash,
        "after_state_hash": e.after_state_hash,
    }


def serialize_trace(trace: FormulaTrace) -> dict[str, Any]:
    return canonical_encode(
        {
            "tenant_id": trace.tenant_id,
            "formula_version": trace.formula_version,
            "schema_version": trace.schema_version,
            "events": [_serialize_trace_event(e) for e in trace.events],
        }
    )


def serialize_authority_evaluation(
    tuples: frozenset[AuthorityTuple],
    evaluator: EffectiveAuthorityEvaluator,
    subject_id: str,
    tenant_id: str,
    *,
    at: datetime | None = None,
    hard_proof: bool = False,
) -> dict[str, Any]:
    return canonical_encode(
        {
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            "at": at,
            "hard_proof": hard_proof,
            "ceiling": _serialize_ceiling(evaluator.ceiling),
            "tuples": sorted(
                [
                    {
                        "action": t.action,
                        "resource": t.resource,
                        "purpose": t.purpose,
                        "risk_ceiling": t.risk_ceiling,
                        "grant_id": t.grant_id,
                    }
                    for t in tuples
                ],
                key=lambda x: (x["action"], x["resource"], x["purpose"], x["grant_id"]),
            ),
        }
    )


def serialize_graph_snapshot(snapshot: GraphSnapshot) -> dict[str, Any]:
    return canonical_encode(
        {
            "tenant_id": snapshot.tenant_id,
            "content_hash": snapshot.content_hash,
            "version": snapshot.version.version_number,
        }
    )
