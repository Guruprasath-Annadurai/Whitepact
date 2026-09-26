# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.graph.elements import GraphEdge, GraphNode
from responsibleai.formula.version import FORMULA_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class GraphVersion:
    tenant_id: str
    version_number: int
    schema_version: str = FORMULA_SCHEMA_VERSION


@dataclass(frozen=True, slots=True)
class GraphSnapshot:
    version: GraphVersion
    tenant_id: str
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    content_hash: str
