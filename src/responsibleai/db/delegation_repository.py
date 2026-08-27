"""Async repository for the Delegation Graph (v3 authority-layer work,
Core Invariant #2) -- persists ``DelegationRecord``s, enforces
attenuation at grant time, and implements the graph operations the
spec calls for: ``get_authority_chain()``, ``get_effective_authority()``,
``validate_delegation()``, ``revoke_branch()`` (cascading revocation),
and ``explain_authority()``.

**One active delegation per identity, by design.** A second ``grant()``
for the same ``to_identity_id`` doesn't overwrite or auto-revoke the
prior row -- both are preserved (a real audit trail: what did this
identity hold last month vs. now) -- but only the most recently granted
row counts as "current" (``get_active_delegation()``). This matches the
concrete requirement ("what does this identity currently hold"), not a
more general multi-simultaneous-grant algebra nothing here needs.

**Continuous re-authorization's real source**: ``mcp/governance_integration.py``
calls ``get_latest_delegation()`` (not ``get_active_delegation()``) on
every dispatched call -- ``None`` means "this identity has never been
explicitly delegated authority via this graph," identical to behavior
before this feature existed; a non-``None``-but-inactive result means a
previously valid grant has since expired or been revoked, and the call
is denied fresh, not because it was denied at grant time (it wasn't).
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, governance_delegations
from responsibleai.governance.delegation import DelegationRecord
from responsibleai.governance.delegation_graph import DelegationGraph, DelegationGraphNode
from responsibleai.governance.models import validate_attenuation


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(row: Any) -> DelegationRecord:
    return DelegationRecord(
        delegation_id=row.id,
        org_id=row.org_id,
        from_identity_id=row.from_identity_id,
        to_identity_id=row.to_identity_id,
        granted_action_types=frozenset(json.loads(row.granted_action_types)),
        constraints=json.loads(row.constraints) if row.constraints else {},
        require_approval_for=frozenset(json.loads(row.require_approval_for))
        if row.require_approval_for
        else frozenset(),
        purpose=row.purpose,
        granted_by=row.granted_by,
        granted_at=datetime.fromisoformat(row.granted_at),
        expires_at=datetime.fromisoformat(row.expires_at) if row.expires_at else None,
        revoked_at=datetime.fromisoformat(row.revoked_at) if row.revoked_at else None,
        revoked_by=row.revoked_by,
        revoke_reason=row.revoke_reason,
    )


class DelegationEscalationError(Exception):
    """Raised by ``grant()`` when the proposed authority would exceed
    what ``from_identity_id`` currently holds -- the attenuation
    invariant enforced at grant time, not just checked ad hoc per call."""


class DelegationNotFoundError(Exception):
    pass


class DelegationRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def grant(
        self,
        org_id: str,
        to_identity_id: str,
        *,
        granted_action_types: frozenset[str],
        constraints: dict[str, Any] | None = None,
        require_approval_for: frozenset[str] = frozenset(),
        purpose: str,
        granted_by: str,
        from_identity_id: str | None = None,
        expires_at: datetime | None = None,
    ) -> DelegationRecord:
        """Grants *to_identity_id* the given authority. When
        *from_identity_id* is set, this is checked against what that
        identity currently, actively holds (``validate_attenuation()``)
        -- raises ``DelegationEscalationError`` rather than silently
        creating an invalid grant. A root grant (``from_identity_id=None``)
        skips this check -- there's no parent in the graph to compare
        against; an org's authority ceiling, if configured, is the real
        root-level constraint (see ``OrgAuthorityCeiling``)."""
        constraints = constraints or {}
        if from_identity_id is not None:
            parent = await self.get_active_delegation(org_id, from_identity_id)
            if parent is None or not parent.is_active():
                raise DelegationEscalationError(
                    f"{from_identity_id!r} has no active delegation to delegate from."
                )
            from responsibleai.governance.models import AuthorityContext

            proposed = AuthorityContext(
                delegated_by=from_identity_id,
                granted_action_types=granted_action_types,
                constraints=constraints,
                require_approval_for=require_approval_for,
            )
            escalation = validate_attenuation(parent.to_authority_context(), proposed)
            if escalation is not None:
                raise DelegationEscalationError(escalation)

        now = _now()
        delegation_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_delegations).values(
                    id=delegation_id,
                    org_id=org_id,
                    from_identity_id=from_identity_id,
                    to_identity_id=to_identity_id,
                    granted_action_types=json.dumps(sorted(granted_action_types)),
                    constraints=json.dumps(constraints) if constraints else None,
                    require_approval_for=json.dumps(sorted(require_approval_for))
                    if require_approval_for
                    else None,
                    purpose=purpose,
                    granted_by=granted_by,
                    granted_at=now,
                    expires_at=expires_at.isoformat() if expires_at else None,
                )
            )
        record = await self.get(delegation_id)
        assert record is not None
        return record

    async def get(self, delegation_id: str) -> DelegationRecord | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_delegations).where(
                        governance_delegations.c.id == delegation_id
                    )
                )
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    async def get_for_org(self, org_id: str, delegation_id: str) -> DelegationRecord | None:
        """Tenant-scoped lookup for authorization decisions."""
        record = await self.get(delegation_id)
        return record if record is not None and record.org_id == org_id else None

    async def get_latest_delegation(self, org_id: str, identity_id: str) -> DelegationRecord | None:
        """The most recently granted delegation for *identity_id*,
        regardless of whether it's still active -- ``None`` means this
        identity has never been delegated authority via this graph at
        all (the case every live MCP caller was in before this feature
        existed)."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_delegations)
                    .where(governance_delegations.c.org_id == org_id)
                    .where(governance_delegations.c.to_identity_id == identity_id)
                    .order_by(governance_delegations.c.granted_at.desc())
                    .limit(1)
                )
            ).fetchone()
        return _row_to_record(row) if row is not None else None

    async def get_active_delegation(self, org_id: str, identity_id: str) -> DelegationRecord | None:
        latest = await self.get_latest_delegation(org_id, identity_id)
        if latest is None or not latest.is_active():
            return None
        return latest

    async def get_effective_authority(self, org_id: str, identity_id: str):  # noqa: ANN201
        record = await self.get_active_delegation(org_id, identity_id)
        return record.to_authority_context() if record is not None else None

    async def get_authority_chain(self, org_id: str, identity_id: str) -> list[DelegationRecord]:
        """Root-first: [root_grant, ..., identity_id's own grant].
        Walks ``from_identity_id`` pointers up via each ancestor's own
        *active* delegation -- if an ancestor has no active delegation
        (revoked/expired/never granted), the chain stops there, since
        there's nothing further up to reconstruct."""
        chain: list[DelegationRecord] = []
        current_id: str | None = identity_id
        seen: set[str] = set()
        while current_id is not None:
            if current_id in seen:
                break  # defensive: a cycle should never exist, but never loop forever if one did
            seen.add(current_id)
            record = await self.get_active_delegation(org_id, current_id)
            if record is None:
                break
            chain.append(record)
            current_id = record.from_identity_id
        chain.reverse()
        return chain

    async def validate_delegation(
        self,
        org_id: str,
        from_identity_id: str,
        granted_action_types: frozenset[str],
        constraints: dict[str, Any] | None = None,
        require_approval_for: frozenset[str] = frozenset(),
    ) -> str | None:
        """Dry-run of the attenuation check ``grant()`` performs --
        lets a caller check "would this delegation be valid" before
        committing to it. Returns the escalation reason, or ``None`` if
        it would be valid."""
        from responsibleai.governance.models import AuthorityContext

        parent = await self.get_active_delegation(org_id, from_identity_id)
        if parent is None:
            return f"{from_identity_id!r} has no active delegation to delegate from."
        proposed = AuthorityContext(
            delegated_by=from_identity_id,
            granted_action_types=granted_action_types,
            constraints=constraints or {},
            require_approval_for=require_approval_for,
        )
        return validate_attenuation(parent.to_authority_context(), proposed)

    async def _direct_children(self, org_id: str, identity_id: str) -> list[DelegationRecord]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_delegations)
                    .where(governance_delegations.c.org_id == org_id)
                    .where(governance_delegations.c.from_identity_id == identity_id)
                )
            ).fetchall()
        return [_row_to_record(r) for r in rows]

    async def revoke_branch(
        self, org_id: str, identity_id: str, *, revoked_by: str, reason: str
    ) -> list[str]:
        """Cascading revocation (Core Invariant #11): revokes
        *identity_id*'s own active delegation, then every descendant's
        active delegation, transitively -- a revoked parent's authority
        can never remain valid for anyone it delegated to. Returns the
        list of ``delegation_id``s actually revoked (already-inactive
        ones are skipped, not re-touched). BFS over the graph, not
        recursion, so depth is bounded by actual data, not the call
        stack."""
        now = _now()
        revoked_ids: list[str] = []
        queue = [identity_id]
        seen: set[str] = set()
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)

            active = await self.get_active_delegation(org_id, current)
            if active is not None:
                async with self._engine.raw.begin() as conn:
                    await conn.execute(
                        update(governance_delegations)
                        .where(governance_delegations.c.id == active.delegation_id)
                        .values(revoked_at=now, revoked_by=revoked_by, revoke_reason=reason)
                    )
                revoked_ids.append(active.delegation_id)

            children = await self._direct_children(org_id, current)
            queue.extend(child.to_identity_id for child in children)

        return revoked_ids

    async def explain_authority(self, org_id: str, identity_id: str) -> dict[str, Any]:
        """A deterministic, structured explanation of *identity_id*'s
        authority -- no LLM call, same "prefer deterministic security
        controls" rule as the rest of this codebase. Every hop in the
        chain, who granted it, why, and whether it's currently valid."""
        chain = await self.get_authority_chain(org_id, identity_id)
        latest = await self.get_latest_delegation(org_id, identity_id)
        return {
            "identity_id": identity_id,
            "currently_active": latest is not None and latest.is_active(),
            "chain": [
                {
                    "delegation_id": hop.delegation_id,
                    "from_identity_id": hop.from_identity_id,
                    "to_identity_id": hop.to_identity_id,
                    "granted_action_types": sorted(hop.granted_action_types),
                    "constraints": hop.constraints,
                    "purpose": hop.purpose,
                    "granted_by": hop.granted_by,
                    "granted_at": hop.granted_at.isoformat(),
                    "expires_at": hop.expires_at.isoformat() if hop.expires_at else None,
                    "is_active": hop.is_active(),
                }
                for hop in chain
            ],
        }

    async def _all_to_identity_ids(self, org_id: str) -> set[str]:
        """Every identity that has ever received a delegation via this
        graph for *org_id* -- the complete node set a graph query needs
        to walk, regardless of how many times each was re-granted."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_delegations.c.to_identity_id).where(
                        governance_delegations.c.org_id == org_id
                    )
                )
            ).fetchall()
        return {r.to_identity_id for r in rows}

    async def _current_parent_map(
        self, org_id: str
    ) -> tuple[dict[str | None, list[str]], dict[str, DelegationRecord]]:
        """Builds the graph from *current* state, not raw historical
        rows: for every identity that has ever received a delegation,
        resolves its `get_latest_delegation()` (regardless of whether
        it's still active -- an inactive node still belongs in the
        graph, just flagged inactive) and groups children by their
        latest record's `from_identity_id`. Self-correcting for
        history: an identity re-delegated from a new parent after its
        original grant shows up under its *current* parent only, not
        both -- `_direct_children()`'s raw-row walk (used by
        `revoke_branch()`, which cares about historical rows for
        cascading revocation) would not have this property, which is
        why this is a separate implementation rather than a reuse."""
        identity_ids = await self._all_to_identity_ids(org_id)
        latest_by_id: dict[str, DelegationRecord] = {}
        parent_map: dict[str | None, list[str]] = {}
        for identity_id in identity_ids:
            latest = await self.get_latest_delegation(org_id, identity_id)
            if latest is None:
                continue
            latest_by_id[identity_id] = latest
            parent_map.setdefault(latest.from_identity_id, []).append(identity_id)
        return parent_map, latest_by_id

    def _build_node(
        self,
        identity_id: str,
        parent_map: dict[str | None, list[str]],
        latest_by_id: dict[str, DelegationRecord],
        seen: set[str],
    ) -> DelegationGraphNode:
        seen.add(identity_id)
        children = []
        for child_id in parent_map.get(identity_id, []):
            if child_id in seen:
                continue  # defensive: a cycle should never exist in valid data
            children.append(self._build_node(child_id, parent_map, latest_by_id, seen))
        return DelegationGraphNode(
            identity_id=identity_id,
            delegation=latest_by_id.get(identity_id),
            children=tuple(children),
        )

    async def get_org_graph(self, org_id: str) -> DelegationGraph:
        """The full, org-wide delegation forest (Authority Everywhere
        Phase 6) -- every root grant and everything transitively
        delegated from it, built from each identity's *current* state,
        not a raw historical-row walk. A snapshot at call time; rebuild
        for a fresh read rather than caching."""
        parent_map, latest_by_id = await self._current_parent_map(org_id)
        seen: set[str] = set()
        roots = [
            self._build_node(root_id, parent_map, latest_by_id, seen)
            for root_id in parent_map.get(None, [])
        ]
        return DelegationGraph(organization_id=org_id, roots=tuple(roots))

    async def get_descendants(self, org_id: str, identity_id: str) -> list[DelegationRecord]:
        """Every identity currently, transitively delegated-from
        *identity_id* -- the public, read-only counterpart to
        ``revoke_branch()``'s internal traversal, built from current
        parentage (see ``_current_parent_map()``) rather than raw
        historical rows. Returns each descendant's own latest
        delegation record (active or not -- callers filter on
        ``.is_active()`` themselves, matching every other read method
        in this repository)."""
        parent_map, latest_by_id = await self._current_parent_map(org_id)
        descendants: list[DelegationRecord] = []
        seen: set[str] = {identity_id}
        queue = list(parent_map.get(identity_id, []))
        while queue:
            current = queue.pop(0)
            if current in seen:
                continue
            seen.add(current)
            record = latest_by_id.get(current)
            if record is not None:
                descendants.append(record)
            queue.extend(parent_map.get(current, []))
        return descendants
