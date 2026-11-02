"""Async repository for ``OrgAuthorityCeiling`` (v3 authority-layer
work) -- one row per org, the structural ceiling
``mcp/governance_integration.py`` fetches on every hosted MCP tool call
and passes to ``WhitePactRuntimeGateway.evaluate()`` as
``parent_authority``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import DatabaseEngine, org_authority_ceilings
from responsibleai.governance.ceiling import OrgAuthorityCeiling


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_ceiling(row: Any) -> OrgAuthorityCeiling:
    return OrgAuthorityCeiling(
        org_id=row.org_id,
        max_value_usd=row.max_value_usd,
        allowed_targets=json.loads(row.allowed_targets) if row.allowed_targets else None,
        denied_targets=json.loads(row.denied_targets) if row.denied_targets else None,
        max_delegation_depth=row.max_delegation_depth,
        allowed_action_types=json.loads(row.allowed_action_types)
        if row.allowed_action_types
        else None,
        require_approval_for=frozenset(json.loads(row.require_approval_for))
        if row.require_approval_for
        else frozenset(),
    )


class OrgAuthorityCeilingRepository:
    """CRUD over one ceiling row per organization."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def get(self, org_id: str) -> OrgAuthorityCeiling | None:
        """``None`` for an org with no ceiling configured -- the caller
        (``mcp/governance_integration.py``) treats that as "no
        ``parent_authority`` to pass," identical to pre-ceiling
        behavior."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(org_authority_ceilings).where(org_authority_ceilings.c.org_id == org_id)
                )
            ).fetchone()
        return _row_to_ceiling(row) if row is not None else None

    async def set(self, ceiling: OrgAuthorityCeiling) -> None:
        """Upserts the org's ceiling wholesale -- a ceiling is a single
        coherent envelope, not a set of independently-added rules
        (contrast ``PolicyRepository.add_rule``), so replace-in-full is
        the correct operation, not an incremental one."""
        now = _now()
        values = {
            "max_value_usd": ceiling.max_value_usd,
            "allowed_targets": json.dumps(ceiling.allowed_targets)
            if ceiling.allowed_targets is not None
            else None,
            "denied_targets": json.dumps(ceiling.denied_targets)
            if ceiling.denied_targets is not None
            else None,
            "max_delegation_depth": ceiling.max_delegation_depth,
            "allowed_action_types": json.dumps(ceiling.allowed_action_types)
            if ceiling.allowed_action_types is not None
            else None,
            "require_approval_for": json.dumps(sorted(ceiling.require_approval_for))
            if ceiling.require_approval_for
            else None,
            "updated_at": now,
        }
        async with self._engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(org_authority_ceilings.c.org_id).where(
                        org_authority_ceilings.c.org_id == ceiling.org_id
                    )
                )
            ).scalar()
            if existing is None:
                await conn.execute(
                    insert(org_authority_ceilings).values(org_id=ceiling.org_id, **values)
                )
            else:
                await conn.execute(
                    update(org_authority_ceilings)
                    .where(org_authority_ceilings.c.org_id == ceiling.org_id)
                    .values(**values)
                )

    async def delete(self, org_id: str) -> None:
        """Removes the ceiling entirely -- distinct from ``set()`` with
        all-``None`` fields, though both leave the org unrestricted;
        this also drops the row so ``get()`` returns ``None`` again."""
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                delete(org_authority_ceilings).where(org_authority_ceilings.c.org_id == org_id)
            )
