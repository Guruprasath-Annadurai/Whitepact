# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Delegation Graph as a first-class object (Authority Everywhere
Phase 6) — a queryable representation of the *whole* delegation
structure (who delegated to whom, transitively, right now), not just
the pairwise checks `governance/delegation.py`'s `DelegationRecord`
and `db/delegation_repository.py`'s per-call `validate_attenuation()`
already perform correctly at decision time.

**What already existed before this phase** (per
`docs/architecture/AUTHORITY_EVERYWHERE.md`'s own lifecycle table, row
4): `validate_attenuation()` enforcing `CHILD ⊆ PARENT` at grant time,
`get_authority_chain()` (backward: one identity's own root-first
ancestor chain), and `revoke_branch()` (forward BFS, but only to
*mutate* — it never returned the shape of what it walked). This was
already "a working delegation graph," just never assembled into
something you could query as *a graph*, independent of one specific
identity's decision.

**What this phase adds**: `DelegationGraph`/`DelegationGraphNode` —
the org-wide forest (every root grant and all of its descendants,
recursively), and `DelegationRepository.get_descendants()` — the
public, non-mutating counterpart to `revoke_branch()`'s internal BFS.
Both are read-only exports of state that was always computable from
the existing table; this phase adds no new invariant, no new
migration, and changes no existing behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from responsibleai.governance.delegation import DelegationRecord


@dataclass(frozen=True)
class DelegationGraphNode:
    """One identity's position in the graph: its own current
    delegation (if it has ever been granted one via this graph) plus
    every direct/transitive child, recursively. `delegation` is `None`
    only for a synthetic node representing an identity that appears as
    a `from_identity_id` but has no delegation record of its own
    within this graph slice (shouldn't happen in practice, since every
    `from_identity_id` must itself hold an active delegation to grant
    from — see `DelegationRepository.grant()` — but represented rather
    than assumed impossible)."""

    identity_id: str
    delegation: DelegationRecord | None
    children: tuple[DelegationGraphNode, ...] = field(default_factory=tuple)

    def is_active(self) -> bool:
        return self.delegation is not None and self.delegation.is_active()

    def descendant_count(self) -> int:
        return len(self.children) + sum(c.descendant_count() for c in self.children)

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "delegation_id": self.delegation.delegation_id if self.delegation else None,
            "granted_action_types": (
                sorted(self.delegation.granted_action_types) if self.delegation else []
            ),
            "purpose": self.delegation.purpose if self.delegation else None,
            "granted_by": self.delegation.granted_by if self.delegation else None,
            "is_active": self.is_active(),
            "children": [c.to_dict() for c in self.children],
        }


@dataclass(frozen=True)
class DelegationGraph:
    """The full, org-wide delegation forest — every root grant
    (`from_identity_id is None`) and everything transitively delegated
    from it. Deliberately a snapshot, not a live view: rebuild via
    `DelegationRepository.get_org_graph()` whenever a fresh read is
    needed, the same "recompute, don't cache" posture every other
    authority-layer read in this codebase already uses."""

    organization_id: str
    roots: tuple[DelegationGraphNode, ...]
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def all_identity_ids(self) -> set[str]:
        seen: set[str] = set()

        def _walk(node: DelegationGraphNode) -> None:
            seen.add(node.identity_id)
            for child in node.children:
                _walk(child)

        for root in self.roots:
            _walk(root)
        return seen

    def find(self, identity_id: str) -> DelegationGraphNode | None:
        def _search(node: DelegationGraphNode) -> DelegationGraphNode | None:
            if node.identity_id == identity_id:
                return node
            for child in node.children:
                found = _search(child)
                if found is not None:
                    return found
            return None

        for root in self.roots:
            found = _search(root)
            if found is not None:
                return found
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "generated_at": self.generated_at.isoformat(),
            "root_count": len(self.roots),
            "total_identity_count": len(self.all_identity_ids()),
            "roots": [r.to_dict() for r in self.roots],
        }
