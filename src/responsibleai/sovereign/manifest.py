# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""whitepact.yaml — expected authority declarations only (never grants)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from responsibleai.sovereign.errors import SovereignValidationError

_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|token|api[_-]?key|private[_-]?key|credential|authorization)",
    re.IGNORECASE,
)


class ManifestActor(BaseModel):
    actor_id: str
    kind: str = Field(description="human | agent | service_account | application")
    display_name: str | None = None


class ManifestCapabilityExpectation(BaseModel):
    capability_id: str
    description: str | None = None
    requires_approval: bool = False


class ManifestDelegationExpectation(BaseModel):
    from_actor_id: str
    to_actor_id: str
    capability_ids: list[str] = Field(default_factory=list)


class ManifestPolicyReference(BaseModel):
    policy_id: str
    version: str | None = None


class WhitepactManifest(BaseModel):
    """Declarative expected authority — not runtime authority."""

    schema_version: str = "1.0"
    organization_id: str
    environment: str = "development"
    actors: list[ManifestActor] = Field(default_factory=list)
    capabilities: list[ManifestCapabilityExpectation] = Field(default_factory=list)
    delegations: list[ManifestDelegationExpectation] = Field(default_factory=list)
    policies: list[ManifestPolicyReference] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    mcp_servers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("metadata", mode="before")
    @classmethod
    def _reject_secret_keys(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        for key in value:
            if _SECRET_KEY_PATTERN.search(str(key)):
                raise ValueError(f"Manifest metadata key '{key}' looks like a secret field")
        return value


def load_manifest(path: Path) -> WhitepactManifest:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SovereignValidationError(f"Cannot read manifest: {exc}") from exc
    except yaml.YAMLError as exc:
        raise SovereignValidationError(f"Invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise SovereignValidationError("Manifest root must be a mapping")
    try:
        return WhitepactManifest.model_validate(raw)
    except Exception as exc:
        raise SovereignValidationError(str(exc)) from exc


def validate_manifest_dict(data: dict[str, Any]) -> WhitepactManifest:
    try:
        return WhitepactManifest.model_validate(data)
    except Exception as exc:
        raise SovereignValidationError(str(exc)) from exc
