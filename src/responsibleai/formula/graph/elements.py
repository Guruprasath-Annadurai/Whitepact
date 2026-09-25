# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    tenant_id: str
    kind: NodeKind
    attributes: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    epistemic_status: EpistemicStatus = EpistemicStatus.DECLARED
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schema_version: str = "0.1.0"


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_id: str
    tenant_id: str
    kind: EdgeKind
    source_id: str
    target_id: str
    attributes: dict[str, Any] = field(default_factory=dict)
    source: str = ""
    epistemic_status: EpistemicStatus = EpistemicStatus.DECLARED
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schema_version: str = "0.1.0"
