# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereign request context — tenant scope and correlation metadata."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class SovereignContext:
    """Read/simulation context. Does not carry execution grants."""

    organization_id: str
    environment: str = "development"
    principal_id: str | None = None
    request_id: str | None = None
    trace_id: str | None = None
    sandbox: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def with_correlation(self, **kwargs: Any) -> SovereignContext:
        return SovereignContext(
            organization_id=str(kwargs.get("organization_id", self.organization_id)),
            environment=str(kwargs.get("environment", self.environment)),
            principal_id=kwargs.get("principal_id", self.principal_id),
            request_id=kwargs.get("request_id", self.request_id),
            trace_id=kwargs.get("trace_id", self.trace_id),
            sandbox=bool(kwargs.get("sandbox", self.sandbox)),
            metadata=dict(kwargs.get("metadata", self.metadata)),
        )
