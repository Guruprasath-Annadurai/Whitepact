# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign diagnostic capsule — redacted export with tamper detection."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.protocol import PROTOCOL_VERSION, SOVEREIGN_VERSION
from responsibleai.sovereign.redaction import redact_for_debugger
from responsibleai.sovereign.zero_effect import zero_effect_operation

CAPSULE_SCHEMA_VERSION = "1.0.0"


class SovereignCapsule(BaseModel):
    schema_version: str = CAPSULE_SCHEMA_VERSION
    capsule_id: str
    created_at: str
    organization_id: str
    environment: str | None = None
    protocol_version: str = PROTOCOL_VERSION
    sovereign_version: str = SOVEREIGN_VERSION
    manifest_ref: str | None = None
    authority_subset: dict[str, Any] = Field(default_factory=dict)
    policy_refs: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)
    evidence_metadata: list[dict[str, Any]] = Field(default_factory=list)
    digest: str
    labels: list[str] = Field(default_factory=lambda: ["DIAGNOSTIC", "REDACTED"])


def _digest_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@zero_effect_operation
def create_capsule(
    ctx: SovereignContext,
    *,
    authority_subset: dict[str, Any] | None = None,
    timeline: list[dict[str, Any]] | None = None,
) -> SovereignCapsule:
    capsule_id = f"capsule-{uuid.uuid4().hex}"
    safe_authority = redact_for_debugger(authority_subset or {})
    safe_timeline = [redact_for_debugger(item) for item in (timeline or [])]
    body = {
        "capsule_id": capsule_id,
        "organization_id": ctx.organization_id,
        "environment": ctx.environment,
        "authority_subset": safe_authority,
        "timeline": safe_timeline,
    }
    return SovereignCapsule(
        capsule_id=capsule_id,
        created_at=datetime.now(UTC).isoformat(),
        organization_id=ctx.organization_id,
        environment=ctx.environment,
        authority_subset=safe_authority,
        timeline=safe_timeline,
        digest=_digest_payload(body),
    )


@zero_effect_operation
def validate_capsule(capsule: SovereignCapsule) -> bool:
    body = {
        "capsule_id": capsule.capsule_id,
        "organization_id": capsule.organization_id,
        "environment": capsule.environment,
        "authority_subset": capsule.authority_subset,
        "timeline": capsule.timeline,
    }
    return capsule.digest == _digest_payload(body)


@zero_effect_operation
def reproduce_capsule(capsule: SovereignCapsule) -> dict[str, Any]:
    """Zero-effect reproduction — returns metadata only, never executes."""
    if not validate_capsule(capsule):
        raise ValueError("Capsule digest mismatch — possible tampering")
    return {
        "capsule_id": capsule.capsule_id,
        "organization_id": capsule.organization_id,
        "reproduced_at": datetime.now(UTC).isoformat(),
        "zero_effect": True,
        "labels": capsule.labels + ["REPRODUCED"],
    }
