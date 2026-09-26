# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.graph.kinds import EdgeKind, NodeKind
from responsibleai.formula.immutability import freeze_mapping


@dataclass(frozen=True, slots=True)
class GraphNode:
    node_id: str
    tenant_id: str
    kind: NodeKind
    _attribute_pairs: tuple[tuple[str, Any], ...] = ()
    source: str = ""
    epistemic_status: EpistemicStatus = EpistemicStatus.DECLARED
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schema_version: str = "0.1.0"

    @classmethod
    def build(
        cls,
        node_id: str,
        tenant_id: str,
        kind: NodeKind,
        attributes: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> GraphNode:
        pairs = freeze_mapping(attributes) if attributes else ()
        return cls(node_id, tenant_id, kind, pairs, **kwargs)

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(self._attribute_pairs)


@dataclass(frozen=True, slots=True)
class GraphEdge:
    edge_id: str
    tenant_id: str
    kind: EdgeKind
    source_id: str
    target_id: str
    _attribute_pairs: tuple[tuple[str, Any], ...] = ()
    source: str = ""
    epistemic_status: EpistemicStatus = EpistemicStatus.DECLARED
    created_at: datetime | None = None
    updated_at: datetime | None = None
    schema_version: str = "0.1.0"

    @classmethod
    def build(
        cls,
        edge_id: str,
        tenant_id: str,
        kind: EdgeKind,
        source_id: str,
        target_id: str,
        attributes: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> GraphEdge:
        pairs = freeze_mapping(attributes) if attributes else ()
        return cls(edge_id, tenant_id, kind, source_id, target_id, pairs, **kwargs)

    @property
    def attributes(self) -> dict[str, Any]:
        return dict(self._attribute_pairs)
