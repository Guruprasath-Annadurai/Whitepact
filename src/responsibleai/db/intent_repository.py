# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Async repository for Intent Contracts (Authority Everywhere Phase 4)
-- persists ``IntentContract``s declared via
``POST /api/governance/intent-contracts`` and resolves, per agent, the
one currently active contract ``mcp/governance_integration.py`` should
pass into ``WhitePactRuntimeGateway.evaluate()``.

**Latest active contract wins**, the same resolution
``DelegationRepository.get_latest_delegation()`` already uses for "what
authority does this identity currently hold": a new declaration doesn't
delete or overwrite an old one (both are preserved -- a real audit
trail of what an agent committed to over time), but only the most
recently declared, still-active-at-lookup-time row is consulted.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select

from responsibleai.db.engine import DatabaseEngine, governance_intent_contracts
from responsibleai.governance.intent import IntentContract


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_record(row: Any) -> IntentContract:
    return IntentContract(
        contract_id=row.id,
        organization_id=row.org_id,
        agent_id=row.agent_id,
        goal=row.goal,
        max_value_usd=row.max_value_usd,
        allowed_targets=tuple(json.loads(row.allowed_targets)) if row.allowed_targets else None,
        denied_targets=tuple(json.loads(row.denied_targets)) if row.denied_targets else None,
        allowed_action_types=(
            tuple(json.loads(row.allowed_action_types)) if row.allowed_action_types else None
        ),
        declared_at=datetime.fromisoformat(row.declared_at),
        valid_from=datetime.fromisoformat(row.valid_from),
        expires_at=datetime.fromisoformat(row.expires_at) if row.expires_at else None,
    )


class IntentContractRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def declare(self, contract: IntentContract) -> IntentContract:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(governance_intent_contracts).values(
                    id=contract.contract_id,
                    org_id=contract.organization_id,
                    agent_id=contract.agent_id,
                    goal=contract.goal,
                    max_value_usd=contract.max_value_usd,
                    allowed_targets=(
                        json.dumps(list(contract.allowed_targets))
                        if contract.allowed_targets
                        else None
                    ),
                    denied_targets=(
                        json.dumps(list(contract.denied_targets))
                        if contract.denied_targets
                        else None
                    ),
                    allowed_action_types=(
                        json.dumps(list(contract.allowed_action_types))
                        if contract.allowed_action_types
                        else None
                    ),
                    declared_at=contract.declared_at.isoformat(),
                    valid_from=contract.valid_from.isoformat(),
                    expires_at=contract.expires_at.isoformat() if contract.expires_at else None,
                )
            )
        return contract

    async def get_active_for_agent(self, org_id: str, agent_id: str) -> IntentContract | None:
        """The most recently declared contract for this agent, or
        `None` if it's never declared one or its latest declaration has
        since expired -- callers treat both the same way (no intent
        gate applied), matching `get_latest_delegation()`'s "absence and
        expiry both mean skip this check" convention."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_intent_contracts)
                    .where(
                        governance_intent_contracts.c.org_id == org_id,
                        governance_intent_contracts.c.agent_id == agent_id,
                    )
                    .order_by(governance_intent_contracts.c.declared_at.desc())
                    .limit(1)
                )
            ).fetchone()
        if row is None:
            return None
        contract = _row_to_record(row)
        return contract if contract.is_active() else None

    async def get(self, contract_id: str) -> IntentContract | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_intent_contracts).where(
                        governance_intent_contracts.c.id == contract_id
                    )
                )
            ).fetchone()
        return _row_to_record(row) if row else None
