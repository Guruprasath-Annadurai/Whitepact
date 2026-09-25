# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic canonical serialization and hashing."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from responsibleai.formula.authority.algebra import AuthorityTuple, EffectiveAuthorityEvaluator
from responsibleai.formula.authority.models import AuthorityGrant
from responsibleai.formula.graph.snapshot import GraphSnapshot
from responsibleai.formula.trace.trace import FormulaTrace


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
    if isinstance(value, frozenset):
        return sorted(canonical_encode(v) for v in value)
    if isinstance(value, (list, tuple)):
        return [canonical_encode(v) for v in value]
    if isinstance(value, dict):
        return {str(k): canonical_encode(v) for k, v in sorted(value.items())}
    if hasattr(value, "_pairs"):
        return canonical_encode(dict(value._pairs))  # type: ignore[attr-defined]
    raise TypeError(f"unsupported canonical type: {type(value)!r}")


def canonical_json_dumps(obj: Any) -> str:
    return json.dumps(
        canonical_encode(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )


def canonical_sha256(obj: Any) -> str:
    payload = canonical_json_dumps(obj).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def serialize_grant(grant: AuthorityGrant) -> dict[str, Any]:
    return canonical_encode(
        {
            "grant_id": grant.grant_id,
            "tenant_id": grant.tenant_id,
            "subject_id": grant.subject.subject_id,
            "actions": grant.actions,
            "resources": grant.resources,
            "purposes": grant.purposes,
            "context": grant.context.attributes,
            "not_before": grant.not_before,
            "expires_at": grant.expires_at,
            "risk_ceiling": grant.risk_ceiling,
            "lifecycle": grant.lifecycle,
        }
    )


def serialize_trace(trace: FormulaTrace) -> dict[str, Any]:
    return canonical_encode(
        {
            "tenant_id": trace.tenant_id,
            "formula_version": trace.formula_version,
            "events": [
                {
                    "event_id": e.event_id,
                    "subject_id": e.subject_id,
                    "action": e.action,
                    "resource": e.resource,
                    "timestamp": e.timestamp,
                    "graph_version": e.graph_version,
                }
                for e in trace.events
            ],
        }
    )


def serialize_authority_evaluation(
    tuples: frozenset[AuthorityTuple],
    evaluator: EffectiveAuthorityEvaluator,
    subject_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    return canonical_encode(
        {
            "subject_id": subject_id,
            "tenant_id": tenant_id,
            "tuples": sorted(
                [
                    {
                        "action": t.action,
                        "resource": t.resource,
                        "purpose": t.purpose,
                        "risk": t.risk_ceiling,
                        "grant_id": t.grant_id,
                    }
                    for t in tuples
                ],
                key=lambda x: (x["action"], x["resource"], x["purpose"]),
            ),
            "has_ceiling": evaluator.ceiling is not None,
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
